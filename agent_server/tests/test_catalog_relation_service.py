from unittest.mock import AsyncMock

import pytest

from database_context_retrieval.domain.exception.catalog_relation import (
    CatalogRelationLookupFailedError,
    CatalogRelationValidationError,
)
from database_context_retrieval.domain.schema.catalog_relation import CatalogRelationLookupResult
from database_context_retrieval.services.catalog_relation_service import CatalogRelationService


@pytest.mark.asyncio
async def test_relation_service_by_table_pair():
    repo = AsyncMock()
    repo.get_relation_info.return_value = CatalogRelationLookupResult(
        found=True,
        queried_table_a="cell_lte",
        queried_table_b="location",
    )
    service = CatalogRelationService(repo)

    await service.get_relation_info(table_a="  cell_lte  ", table_b="  location  ")

    repo.get_relation_info.assert_awaited_once_with(
        table_a="cell_lte",
        table_b="location",
    )


@pytest.mark.asyncio
async def test_relation_service_validation():
    service = CatalogRelationService(AsyncMock())
    with pytest.raises(CatalogRelationValidationError):
        await service.get_relation_info(table_a="", table_b="location")
    with pytest.raises(CatalogRelationValidationError):
        await service.get_relation_info(table_a="cell_lte", table_b="   ")


@pytest.mark.asyncio
async def test_relation_service_wraps_repository_errors():
    repo = AsyncMock()
    repo.get_relation_info.side_effect = RuntimeError("db down")
    service = CatalogRelationService(repo)

    with pytest.raises(CatalogRelationLookupFailedError):
        await service.get_relation_info(table_a="cell_lte", table_b="location")
