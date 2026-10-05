from unittest.mock import AsyncMock

import pytest

from database_context_retrieval.domain.exception.catalog_column import (
    CatalogColumnLookupFailedError,
    CatalogColumnValidationError,
)
from database_context_retrieval.domain.schema.catalog_column import CatalogColumnLookupResult
from database_context_retrieval.services.catalog_column_service import CatalogColumnService


@pytest.mark.asyncio
async def test_column_service_delegates_to_repository():
    repo = AsyncMock()
    repo.get_column_info.return_value = CatalogColumnLookupResult(
        found=True,
        queried_table_name="cell_lte",
        queried_column_name="iid",
    )
    service = CatalogColumnService(repo)

    await service.get_column_info("  cell_lte  ", "  iid  ")

    repo.get_column_info.assert_awaited_once_with("cell_lte", "iid")


@pytest.mark.asyncio
async def test_column_service_rejects_empty_names():
    service = CatalogColumnService(AsyncMock())
    with pytest.raises(CatalogColumnValidationError):
        await service.get_column_info("cell_lte", "   ")
    with pytest.raises(CatalogColumnValidationError):
        await service.get_column_info("   ", "iid")


@pytest.mark.asyncio
async def test_column_service_wraps_repository_errors():
    repo = AsyncMock()
    repo.get_column_info.side_effect = RuntimeError("db down")
    service = CatalogColumnService(repo)

    with pytest.raises(CatalogColumnLookupFailedError) as exc_info:
        await service.get_column_info("cell_lte", "iid")

    assert exc_info.value.queried_table_name == "cell_lte"
    assert exc_info.value.queried_column_name == "iid"
