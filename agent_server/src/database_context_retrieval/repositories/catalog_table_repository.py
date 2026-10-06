from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database_context_retrieval.domain.catalog_keys import similar_table_names
from database_context_retrieval.domain.entity import CatalogColumn, CatalogRelation, CatalogTable
from database_context_retrieval.domain.interface.i_catalog_table_repository import (
    ICatalogTableRepository,
)
from database_context_retrieval.domain.schema.catalog_table import (
    CatalogColumnSummary,
    CatalogTableInfo,
    CatalogTableLookupResult,
)

DEFAULT_COLUMN_LIMIT = 5
DEFAULT_COLUMN_OFFSET = 0


class CatalogTableRepository(ICatalogTableRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _normalize_table_name(table_name: str) -> str:
        return table_name.strip()

    async def get_table_info(
        self,
        table_name: str,
        *,
        column_limit: int | None = DEFAULT_COLUMN_LIMIT,
        column_offset: int | None = DEFAULT_COLUMN_OFFSET,
    ) -> CatalogTableLookupResult:
        queried = self._normalize_table_name(table_name)
        limit = DEFAULT_COLUMN_LIMIT if column_limit is None else column_limit
        offset = DEFAULT_COLUMN_OFFSET if column_offset is None else column_offset

        table_row = await self._session.get(CatalogTable, queried)
        if table_row is None:
            similar = await similar_table_names(self._session, queried)
            return CatalogTableLookupResult(
                found=False,
                queried_name=queried,
                similar_table_names=similar,
            )

        related_table_names = await self._related_table_names(queried)
        total_column_count = await self._count_columns(queried)
        column_rows = await self._fetch_columns(queried, limit=limit, offset=offset)

        return CatalogTableLookupResult(
            found=True,
            queried_name=queried,
            table=CatalogTableInfo(
                name=table_row.name,
                description=table_row.description,
                primary_key_columns=list(table_row.primary_key_columns or []),
                important_columns=(
                    list(table_row.important_columns)
                    if table_row.important_columns is not None
                    else None
                ),
                notes=list(table_row.notes or []),
            ),
            related_table_names=related_table_names,
            columns=[self._to_column_summary(row) for row in column_rows],
            total_column_count=total_column_count,
        )

    async def _related_table_names(self, table_name: str) -> list[str]:
        stmt = select(CatalogRelation.source_table, CatalogRelation.target_table).where(
            or_(
                CatalogRelation.source_table == table_name,
                CatalogRelation.target_table == table_name,
            )
        )
        result = await self._session.execute(stmt)
        related: set[str] = set()
        for source_table, target_table in result.all():
            if source_table != table_name:
                related.add(source_table)
            if target_table != table_name:
                related.add(target_table)
        return sorted(related)

    async def _count_columns(self, table_name: str) -> int:
        stmt = (
            select(func.count())
            .select_from(CatalogColumn)
            .where(CatalogColumn.table_name == table_name)
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def _fetch_columns(
        self,
        table_name: str,
        *,
        limit: int,
        offset: int,
    ) -> list[CatalogColumn]:
        stmt = (
            select(CatalogColumn)
            .where(CatalogColumn.table_name == table_name)
            .order_by(CatalogColumn.column_name)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _to_column_summary(row: CatalogColumn) -> CatalogColumnSummary:
        return CatalogColumnSummary(
            table_name=row.table_name,
            column_name=row.column_name,
            data_type=row.data_type,
            description=row.description,
            example_use_cases=row.example_use_cases,
        )
