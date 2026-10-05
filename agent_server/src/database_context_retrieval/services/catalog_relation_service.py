from __future__ import annotations

from database_context_retrieval.domain.exception.catalog_relation import (
    CatalogRelationLookupFailedError,
    CatalogRelationValidationError,
)
from database_context_retrieval.domain.interface.i_catalog_relation_repository import (
    ICatalogRelationRepository,
)
from database_context_retrieval.domain.schema.catalog_relation import CatalogRelationLookupResult


class CatalogRelationService:
    def __init__(self, repository: ICatalogRelationRepository) -> None:
        self._repository = repository

    async def get_relation_info(
        self,
        *,
        table_a: str,
        table_b: str,
    ) -> CatalogRelationLookupResult:
        """Look up catalog relations between two tables (either direction)."""
        normalized_a = table_a.strip()
        normalized_b = table_b.strip()
        self._validate_lookup_args(normalized_a, normalized_b)

        try:
            return await self._repository.get_relation_info(
                table_a=normalized_a,
                table_b=normalized_b,
            )
        except CatalogRelationValidationError:
            raise
        except Exception as exc:
            raise CatalogRelationLookupFailedError(str(exc)) from exc

    @staticmethod
    def _validate_lookup_args(table_a: str, table_b: str) -> None:
        if not table_a:
            raise CatalogRelationValidationError("table_a must not be empty.")
        if not table_b:
            raise CatalogRelationValidationError("table_b must not be empty.")
