from __future__ import annotations

from database_context_retrieval.domain.exception.catalog_column import (
    CatalogColumnLookupFailedError,
    CatalogColumnValidationError,
)
from database_context_retrieval.domain.interface.i_catalog_column_repository import (
    ICatalogColumnRepository,
)
from database_context_retrieval.domain.schema.catalog_column import CatalogColumnLookupResult


class CatalogColumnService:
    def __init__(self, repository: ICatalogColumnRepository) -> None:
        self._repository = repository

    async def get_column_info(
        self,
        table_name: str,
        column_name: str,
    ) -> CatalogColumnLookupResult:
        normalized_table = table_name.strip()
        normalized_column = column_name.strip()
        self._validate_lookup_args(normalized_table, normalized_column)

        try:
            return await self._repository.get_column_info(
                normalized_table,
                normalized_column,
            )
        except CatalogColumnValidationError:
            raise
        except Exception as exc:
            raise CatalogColumnLookupFailedError(
                normalized_table,
                normalized_column,
                str(exc),
            ) from exc

    @staticmethod
    def _validate_lookup_args(table_name: str, column_name: str) -> None:
        if not table_name:
            raise CatalogColumnValidationError("table_name must not be empty.")
        if not column_name:
            raise CatalogColumnValidationError("column_name must not be empty.")
