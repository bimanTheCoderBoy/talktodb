"""Unit tests for catalog table repository/service wiring."""

from unittest.mock import AsyncMock

import pytest

from database_context_retrieval.domain.exception.catalog_table import (
    CatalogTableLookupFailedError,
    CatalogTableValidationError,
)
from database_context_retrieval.domain.schema.catalog_table import CatalogTableLookupResult
from database_context_retrieval.services.catalog_table_service import CatalogTableService


@pytest.mark.asyncio
async def test_service_delegates_to_repository():
    repo = AsyncMock()
    repo.get_table_info.return_value = CatalogTableLookupResult(
        found=False,
        queried_name="missing",
        similar_table_names=["cell_lte"],
    )
    service = CatalogTableService(repo)

    result = await service.get_table_info("  missing  ")

    repo.get_table_info.assert_awaited_once_with(
        "missing",
        column_limit=15,
        column_offset=0,
    )
    assert result.similar_table_names == ["cell_lte"]


@pytest.mark.asyncio
async def test_service_rejects_empty_table_name():
    service = CatalogTableService(AsyncMock())
    with pytest.raises(CatalogTableValidationError):
        await service.get_table_info("   ")


@pytest.mark.asyncio
async def test_service_wraps_repository_errors():
    repo = AsyncMock()
    repo.get_table_info.side_effect = RuntimeError("db down")
    service = CatalogTableService(repo)

    with pytest.raises(CatalogTableLookupFailedError) as exc_info:
        await service.get_table_info("cell_lte")

    assert exc_info.value.queried_name == "cell_lte"
    assert "db down" in str(exc_info.value)
