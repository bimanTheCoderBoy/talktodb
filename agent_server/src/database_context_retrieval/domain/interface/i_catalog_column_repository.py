from __future__ import annotations

from typing import Protocol

from database_context_retrieval.domain.schema.catalog_column import CatalogColumnLookupResult


class ICatalogColumnRepository(Protocol):
    async def get_column_info(
        self,
        table_name: str,
        column_name: str,
    ) -> CatalogColumnLookupResult: ...
