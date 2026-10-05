import asyncio
from typing import Optional

import lancedb

from ..config.catalog_store_config import get_catalog_store_config
from ..core.logger import CustomLogger


class CatalogLanceDBClient:
    _instance: Optional["CatalogLanceDBClient"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        if CatalogLanceDBClient._instance is not None:
            raise RuntimeError("Use CatalogLanceDBClient.initialize() instead.")
        self.db: Optional[lancedb.AsyncConnection] = None

    @classmethod
    async def initialize(cls):
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    instance = cls()
                    db_path = get_catalog_store_config().path
                    instance.db = await lancedb.connect_async(db_path)
                    cls._instance = instance
                    logger = CustomLogger.get_instance()
                    logger.info(f"CatalogLanceDBClient initialized at {db_path}")

    @classmethod
    def get_connection(cls) -> lancedb.AsyncConnection:
        if cls._instance is None:
            raise RuntimeError(
                "CatalogLanceDBClient is not initialized! Call initialize() at startup."
            )
        return cls._instance.db
