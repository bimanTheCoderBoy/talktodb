from __future__ import annotations

import asyncio
from collections import defaultdict

import httpx

from database_context_retrieval.config import (
    CATALOG_CONTEXT_MAX_TABLES,
    CATALOG_RETRIEVAL_PATH,
    RAG_RETRIEVAL_SERVICE_URL,
    RAG_SERVICE_TIMEOUT,
)
from database_context_retrieval.domain.exception.catalog_context_search import (
    CatalogContextSearchValidationError,
    CatalogRetrievalRequestFailedError,
)
from database_context_retrieval.domain.exception.catalog_table import CatalogTableLookupFailedError
from database_context_retrieval.domain.schema.catalog_context_search import (
    CatalogContextSearchResult,
    CatalogRetrievalColumnHit,
    CatalogTableEnrichedContext,
)
from database_context_retrieval.domain.schema.catalog_table import CatalogTableLookupResult
from database_context_retrieval.services.catalog_table_service import CatalogTableService


class CatalogContextSearchService:
    def __init__(self, table_service: CatalogTableService) -> None:
        self._table_service = table_service
        self._base_url = RAG_RETRIEVAL_SERVICE_URL.rstrip("/")

    async def search(self, query: str) -> CatalogContextSearchResult:
        normalized = query.strip()
        if not normalized:
            raise CatalogContextSearchValidationError("query must not be empty.")

        column_hits = await self._fetch_catalog_columns(normalized)
        if not column_hits:
            return CatalogContextSearchResult(query=normalized, column_hits=[])

        grouped: dict[str, list[CatalogRetrievalColumnHit]] = defaultdict(list)
        for hit in column_hits:
            grouped[hit.table_name].append(hit)

        ranked_tables = sorted(
            grouped.items(),
            key=lambda item: max(col.value for col in item[1]),
            reverse=True,
        )
        selected = ranked_tables[:CATALOG_CONTEXT_MAX_TABLES]

        async def enrich_table(
            table_name: str,
            matched: list[CatalogRetrievalColumnHit],
        ) -> CatalogTableEnrichedContext:
            score = max(col.value for col in matched)
            try:
                lookup = await self._table_service.get_table_info(
                    table_name,
                    column_limit=0,
                    column_offset=0,
                )
            except CatalogTableLookupFailedError as exc:
                lookup = CatalogTableLookupResult.failure(table_name, str(exc))
            except Exception as exc:
                lookup = CatalogTableLookupResult.failure(
                    table_name,
                    f"Unexpected error during table lookup: {exc}",
                )
            return CatalogTableEnrichedContext(
                table_name=table_name,
                retrieval_score=score,
                matched_columns=matched,
                lookup=lookup,
            )

        tables = await asyncio.gather(
            *(enrich_table(name, matched) for name, matched in selected)
        )

        return CatalogContextSearchResult(
            query=normalized,
            column_hits=column_hits,
            tables=list(tables),
        )

    async def _fetch_catalog_columns(self, query: str) -> list[CatalogRetrievalColumnHit]:
        url = f"{self._base_url}{CATALOG_RETRIEVAL_PATH}"
        try:
            async with httpx.AsyncClient(timeout=RAG_SERVICE_TIMEOUT) as client:
                response = await client.post(url, json={"query": query})
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise CatalogRetrievalRequestFailedError(
                query,
                f"Catalog retrieval request failed: {exc}",
            ) from exc

        if not isinstance(payload, list):
            raise CatalogRetrievalRequestFailedError(
                query,
                "Catalog retrieval response must be a JSON array.",
            )

        return [CatalogRetrievalColumnHit.model_validate(item) for item in payload]
