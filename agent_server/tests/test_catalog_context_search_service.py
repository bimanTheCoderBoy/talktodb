"""Unit tests for catalog context search orchestration."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from database_context_retrieval.domain.exception.catalog_context_search import (
    CatalogContextSearchValidationError,
    CatalogRetrievalRequestFailedError,
)
from database_context_retrieval.domain.exception.catalog_table import CatalogTableLookupFailedError
from database_context_retrieval.domain.schema.catalog_context_search import CatalogRetrievalColumnHit
from database_context_retrieval.domain.schema.catalog_table import CatalogTableLookupResult
from database_context_retrieval.services.catalog_context_search_service import (
    CatalogContextSearchService,
)


def _hit(
    *,
    column_id: str,
    table_name: str,
    column_name: str,
    value: float,
) -> CatalogRetrievalColumnHit:
    return CatalogRetrievalColumnHit(
        column_id=column_id,
        table_name=table_name,
        column_name=column_name,
        data_type="text",
        description="desc",
        example_use_cases="example",
        value=value,
    )


@pytest.mark.asyncio
async def test_search_rejects_empty_query():
    service = CatalogContextSearchService(AsyncMock())
    with pytest.raises(CatalogContextSearchValidationError):
        await service.search("   ")


@pytest.mark.asyncio
async def test_search_returns_empty_tables_when_rag_has_no_hits():
    table_service = AsyncMock()
    service = CatalogContextSearchService(table_service)
    service._fetch_catalog_columns = AsyncMock(return_value=[])

    result = await service.search("azimuth")

    assert result.success is True
    assert result.query == "azimuth"
    assert result.column_hits == []
    assert result.tables == []
    table_service.get_table_info.assert_not_called()


@pytest.mark.asyncio
async def test_search_groups_hits_for_same_table():
    table_service = AsyncMock()
    table_service.get_table_info.return_value = CatalogTableLookupResult(
        found=True,
        queried_name="cell_lte",
    )
    service = CatalogContextSearchService(table_service)
    service._fetch_catalog_columns = AsyncMock(
        return_value=[
            _hit(column_id="1", table_name="cell_lte", column_name="azimuth", value=0.9),
            _hit(column_id="2", table_name="cell_lte", column_name="tilt", value=0.7),
        ]
    )

    result = await service.search("lte azimuth")

    assert len(result.tables) == 1
    assert result.tables[0].table_name == "cell_lte"
    assert len(result.tables[0].matched_columns) == 2
    assert result.tables[0].retrieval_score == 0.9
    table_service.get_table_info.assert_awaited_once_with(
        "cell_lte",
        column_limit=0,
        column_offset=0,
    )


@pytest.mark.asyncio
async def test_search_orders_tables_by_max_retrieval_score():
    table_service = AsyncMock()
    table_service.get_table_info.side_effect = lambda name, **_: CatalogTableLookupResult(
        found=True,
        queried_name=name,
    )
    service = CatalogContextSearchService(table_service)
    service._fetch_catalog_columns = AsyncMock(
        return_value=[
            _hit(column_id="1", table_name="low", column_name="a", value=0.2),
            _hit(column_id="2", table_name="high", column_name="b", value=0.95),
        ]
    )

    result = await service.search("columns")

    assert [t.table_name for t in result.tables] == ["high", "low"]


@pytest.mark.asyncio
async def test_search_partial_failure_when_table_lookup_raises():
    table_service = AsyncMock()

    async def lookup(name: str, **kwargs):
        if name == "bad":
            raise CatalogTableLookupFailedError(name, "db down")
        return CatalogTableLookupResult(found=True, queried_name=name)

    table_service.get_table_info.side_effect = lookup
    service = CatalogContextSearchService(table_service)
    service._fetch_catalog_columns = AsyncMock(
        return_value=[
            _hit(column_id="1", table_name="good", column_name="a", value=0.5),
            _hit(column_id="2", table_name="bad", column_name="b", value=0.4),
        ]
    )

    result = await service.search("tables")

    by_name = {t.table_name: t for t in result.tables}
    assert by_name["good"].lookup.found is True
    assert by_name["bad"].lookup.success is False
    assert "db down" in (by_name["bad"].lookup.error or "")


@pytest.mark.asyncio
async def test_fetch_catalog_columns_maps_http_errors():
    table_service = AsyncMock()
    service = CatalogContextSearchService(table_service)

    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.HTTPStatusError(
        "Server error",
        request=httpx.Request("POST", "http://test/api/v1/catalog-retrieval/"),
        response=httpx.Response(500),
    )
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client

    with patch(
        "database_context_retrieval.services.catalog_context_search_service.httpx.AsyncClient",
        return_value=mock_cm,
    ):
        with pytest.raises(CatalogRetrievalRequestFailedError) as exc_info:
            await service._fetch_catalog_columns("q")

    assert exc_info.value.query == "q"
