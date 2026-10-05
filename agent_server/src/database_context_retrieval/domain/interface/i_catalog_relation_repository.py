from __future__ import annotations

from typing import Protocol

from database_context_retrieval.domain.schema.catalog_relation import CatalogRelationLookupResult


class ICatalogRelationRepository(Protocol):
    async def get_relation_info(
        self,
        *,
        table_a: str,
        table_b: str,
    ) -> CatalogRelationLookupResult: ...
