from __future__ import annotations

from database_context_retrieval.domain.exception.catalog_table import (
    CatalogTableLookupFailedError,
    CatalogTableValidationError,
)
from database_context_retrieval.domain.interface.i_catalog_table_repository import (
    ICatalogTableRepository,
)
from database_context_retrieval.domain.schema.catalog_table import CatalogTableLookupResult
from database_context_retrieval.repositories.catalog_table_repository import (
    DEFAULT_COLUMN_LIMIT,
    DEFAULT_COLUMN_OFFSET,
)


class CatalogTableService:
    def __init__(self, repository: ICatalogTableRepository) -> None:
        self._repository = repository

    async def get_table_info(
        self,
        table_name: str,
        *,
        column_limit: int | None = DEFAULT_COLUMN_LIMIT,
        column_offset: int | None = DEFAULT_COLUMN_OFFSET,
    ) -> CatalogTableLookupResult:
        normalized = table_name.strip()
        self._validate_lookup_args(normalized, column_limit, column_offset)

        try:
            return await self._repository.get_table_info(
                normalized,
                column_limit=column_limit,
                column_offset=column_offset,
            )
        except CatalogTableValidationError:
            raise
        except Exception as exc:
            raise CatalogTableLookupFailedError(normalized, str(exc)) from exc

    @staticmethod
    def _validate_lookup_args(
        table_name: str,
        column_limit: int | None,
        column_offset: int | None,
    ) -> None:
        if not table_name:
            raise CatalogTableValidationError("table_name must not be empty.")
        if column_limit is not None and column_limit < 0:
            raise CatalogTableValidationError("column_limit must be >= 0.")
        if column_offset is not None and column_offset < 0:
            raise CatalogTableValidationError("column_offset must be >= 0.")
