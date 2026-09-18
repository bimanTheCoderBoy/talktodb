"""
DB dictionary store for known telecom entity values (Layer 2).

Loads all known site names and cell IDs from the PostgreSQL database
into memory for O(1) substring matching against user messages.
"""

import logging
import time
import re
from typing import List, Dict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# Default refresh interval: 30 minutes
DEFAULT_REFRESH_SECONDS = 1800

_SITE_QUERY = text(
    "SELECT DISTINCT iid FROM location "
    "WHERE imported_at = (SELECT MAX(imported_at) FROM location)"
)

_CELL_LTE_QUERY = text(
    "SELECT DISTINCT cell_iid FROM cell_lte "
    "WHERE imported_at = (SELECT MAX(imported_at) FROM cell_lte)"
)

_CELL_NR_QUERY = text(
    "SELECT DISTINCT cell_iid FROM cell_nr "
    "WHERE imported_at = (SELECT MAX(imported_at) FROM cell_nr)"
)


class KnownValuesStore:
    """
    In-memory store of known site names and cell IDs loaded from the database.

    Usage:
        store = KnownValuesStore()
        await store.load(engine)        # call once at startup or on first use
        matches = store.find_in_text("check site ARRANHO please")
    """

    def __init__(self, refresh_seconds: int = DEFAULT_REFRESH_SECONDS):
        self._site_names: set[str] = set()
        self._cell_ids: set[str] = set()
        self._all_values: set[str] = set()
        self._loaded = False
        self._last_load_time: float = 0.0
        self._refresh_seconds = refresh_seconds
        self._word_boundary_re = re.compile(r'\b(' + r'placeholder' + r')\b')
        self._compiled = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def needs_refresh(self) -> bool:
        if not self._loaded:
            return True
        return (time.time() - self._last_load_time) > self._refresh_seconds

    async def _run_query(self, session_maker, query, label: str) -> set[str]:
        values: set[str] = set()
        try:
            async with session_maker() as session:
                result = await session.execute(query)
                for row in result:
                    if row[0]:
                        values.add(row[0].strip())
        except Exception as e:
            logger.warning(f"[KnownValuesStore] Failed to load {label}: {e}")
        return values

    async def load(self, engine: AsyncEngine) -> None:
        session_maker = async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        # Each query runs in its own session — one failure won't break others
        site_names = await self._run_query(session_maker, _SITE_QUERY, "site names")
        cell_ids = await self._run_query(session_maker, _CELL_LTE_QUERY, "LTE cell IDs")
        cell_ids |= await self._run_query(session_maker, _CELL_NR_QUERY, "NR cell IDs")

        # Atomic swap
        self._site_names = site_names
        self._cell_ids = cell_ids
        self._all_values = site_names | cell_ids
        self._loaded = True
        self._last_load_time = time.time()

        # Pre-compile regex for efficient multi-pattern matching
        self._compile_pattern()

        logger.info(
            f"[KnownValuesStore] Loaded {len(site_names)} sites, "
            f"{len(cell_ids)} cell IDs"
        )

    def _compile_pattern(self) -> None:
        if not self._all_values:
            self._compiled = False
            return
        # Sort by length descending so longer matches take priority
        sorted_vals = sorted(self._all_values, key=len, reverse=True)
        escaped = [re.escape(v) for v in sorted_vals]
        pattern = r'\b(' + '|'.join(escaped) + r')\b'
        self._word_boundary_re = re.compile(pattern)
        self._compiled = True

    async def refresh_if_needed(self, engine: AsyncEngine) -> None:
        if self.needs_refresh:
            await self.load(engine)

    def find_in_text(self, text: str) -> List[Dict]:
        if not self._compiled or not self._all_values:
            return []

        results = []
        for m in self._word_boundary_re.finditer(text):
            results.append({
                "start_index": m.start(1),
                "original_value": m.group(1),
            })
        return results

    def load_from_sets(self, site_names: set[str], cell_ids: set[str]) -> None:
        """Load values directly from sets (useful for testing without DB)."""
        self._site_names = site_names
        self._cell_ids = cell_ids
        self._all_values = site_names | cell_ids
        self._loaded = True
        self._last_load_time = time.time()
        self._compile_pattern()
