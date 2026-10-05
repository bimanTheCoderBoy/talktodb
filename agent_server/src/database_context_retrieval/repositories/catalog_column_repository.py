from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from database_context_retrieval.domain.catalog_keys import similar_column_names
from database_context_retrieval.domain.entity import CatalogColumn
from database_context_retrieval.domain.interface.i_catalog_column_repository import (
    ICatalogColumnRepository,
)
from database_context_retrieval.domain.schema.catalog_column import (
    CatalogColumnInfo,
    CatalogColumnLookupResult,
)


class CatalogColumnRepository(ICatalogColumnRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_column_info(
        self,
        table_name: str,
        column_name: str,
    ) -> CatalogColumnLookupResult:
        column_row = await self._session.get(
            CatalogColumn,
            (table_name, column_name),
        )
        if column_row is not None:
            return CatalogColumnLookupResult(
                found=True,
                queried_table_name=table_name,
                queried_column_name=column_name,
                column=self._to_column_info(column_row),
            )

        similar_columns = await similar_column_names(self._session, column_name)
        return CatalogColumnLookupResult(
            found=False,
            queried_table_name=table_name,
            queried_column_name=column_name,
            similar_column_names=similar_columns,
        )

    @staticmethod
    def _to_column_info(row: CatalogColumn) -> CatalogColumnInfo:
        return CatalogColumnInfo(
            table_name=row.table_name,
            column_name=row.column_name,
            data_type=row.data_type,
            description=row.description,
            example_use_cases=row.example_use_cases,
        )
