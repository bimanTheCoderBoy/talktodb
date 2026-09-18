"""
EncryptionManager — singleton manager for per-project Encryptor instances.

Handles:
- Per-project KnownValuesStore with auto-refresh from DB
- Thread-safe lazy initialization
- Feature toggle via ENCRYPTION_ENABLED env var
"""

import asyncio
import os
import logging
from typing import Dict, Optional, List
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage, ToolMessage
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from .enc_pipeline import Encryptor
from .known_values import KnownValuesStore
from .enc_config import EncryptionConfig

logger = logging.getLogger(__name__)


class EncryptionManager:
    """
    Manages per-project Encryptor instances with DB-backed known values.

    Usage in LangGraph nodes:
        manager = EncryptionManager.instance()

        # Encrypt a message (returns msg + new entries)
        msg, new_entries = await manager.encrypt_message(msg, project_name)

        # Decrypt AI response (uses all accumulated entries)
        msg = manager.decrypt_message(msg, all_entries)
    """

    _instance: Optional['EncryptionManager'] = None

    def __init__(self):
        self._config = EncryptionConfig()
        self._stores: Dict[str, KnownValuesStore] = {}
        self._encryptors: Dict[str, Encryptor] = {}
        self._engines: Dict[str, AsyncEngine] = {}

    @classmethod
    def instance(cls) -> 'EncryptionManager':
        """Get or create the singleton EncryptionManager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def _get_engine(self, project_name: str) -> AsyncEngine:
        """Get or create a lightweight async engine for loading known values."""
        key = project_name.lower().strip()
        if key not in self._engines:
            db_host = os.getenv("DB_HOST", "localhost")
            db_port = os.getenv("DB_PORT", "5432")
            db_user = os.getenv("API_DB_USER", "csv_user")
            db_password = os.getenv("API_DB_PASSWORD", "csv_password")
            url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{key}"
            self._engines[key] = create_async_engine(
                url, pool_size=2, pool_pre_ping=True, connect_args={"ssl": False}
            )
        return self._engines[key]

    async def _get_encryptor(self, project_name: str) -> Encryptor:
        """Get or create an Encryptor for the given project, refreshing DB values if needed."""
        key = project_name.lower().strip()

        if key not in self._stores:
            store = KnownValuesStore(
                refresh_seconds=self._config.dict_refresh_seconds
            )
            self._stores[key] = store
            self._encryptors[key] = Encryptor(known_values=store)

        store = self._stores[key]

        # Load/refresh known values from DB if needed
        if store.needs_refresh:
            try:
                engine = self._get_engine(key)
                await store.load(engine)
                logger.info(f"[EncryptionManager] Refreshed known values for '{key}'")
            except Exception as e:
                logger.warning(
                    f"[EncryptionManager] Failed to load known values for '{key}': {e}. "
                    f"Continuing with Layer 1 + Layer 3 only."
                )

        return self._encryptors[key]

    async def encrypt_message(
        self, msg: AnyMessage, project_name: str
    ) -> tuple[AnyMessage, List[Dict]]:
        """
        Encrypt a single message. Returns (modified_msg, new_entries).
        If encryption is disabled, returns the message unchanged with empty entries.
        """
        if not self.enabled:
            return msg, []

        encryptor = await self._get_encryptor(project_name)
        return await encryptor.encrypt(msg)

    def decrypt_message(
        self, msg: AIMessage, all_entries: List[Dict]
    ) -> AIMessage:
        """
        Decrypt an AI message using all accumulated entries.
        If encryption is disabled, returns the message unchanged.
        """
        if not self.enabled or not all_entries:
            return msg

        # Use a bare Encryptor for decryption (no DB needed)
        encryptor = Encryptor()
        return encryptor.decrypt(msg, all_entries)
