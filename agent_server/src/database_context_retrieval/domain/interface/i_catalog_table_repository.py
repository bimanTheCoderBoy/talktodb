from __future__ import annotations

from typing import Protocol

from database_context_retrieval.domain.schema.catalog_table import CatalogTableLookupResult


class ICatalogTableRepository(Protocol):
    async def get_table_info(
        self,
        table_name: str,
        *,
        column_limit: int | None = 15,
        column_offset: int | None = 0,
    ) -> CatalogTableLookupResult: ...
