from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from database_context_retrieval.domain.entity import CatalogColumn, CatalogTable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SIMILAR_TABLE_LIMIT = 10
SIMILAR_COLUMN_LIMIT = 10


async def similar_table_names(session: AsyncSession, query: str) -> list[str]:
    if not query:
        return []
    try:
        similarity_score = func.similarity(CatalogTable.name, query)
        stmt = (
            select(CatalogTable.name)
            .where(similarity_score > 0)
            .order_by(similarity_score.desc())
            .limit(SIMILAR_TABLE_LIMIT)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    except DBAPIError:
        logger.warning(
            "pg_trgm similarity failed for catalog table search; falling back to ILIKE",
            exc_info=True,
        )
        await session.rollback()
        pattern = f"%{query}%"
        stmt = (
            select(CatalogTable.name)
            .where(CatalogTable.name.ilike(pattern))
            .order_by(CatalogTable.name)
            .limit(SIMILAR_TABLE_LIMIT)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def similar_column_names(session: AsyncSession, query: str) -> list[str]:
    """Fuzzy match on column_name across all catalog columns (returns table.column)."""
    if not query:
        return []
    try:
        similarity_score = func.similarity(CatalogColumn.column_name, query)
        stmt = (
            select(CatalogColumn.table_name, CatalogColumn.column_name)
            .where(similarity_score > 0)
            .order_by(similarity_score.desc())
            .limit(SIMILAR_COLUMN_LIMIT)
        )
        result = await session.execute(stmt)
        return _format_qualified_columns(result.all())
    except DBAPIError:
        logger.warning(
            "pg_trgm similarity failed for catalog column search; falling back to ILIKE",
            exc_info=True,
        )
        await session.rollback()
        pattern = f"%{query}%"
        stmt = (
            select(CatalogColumn.table_name, CatalogColumn.column_name)
            .where(CatalogColumn.column_name.ilike(pattern))
            .order_by(CatalogColumn.table_name, CatalogColumn.column_name)
            .limit(SIMILAR_COLUMN_LIMIT)
        )
        result = await session.execute(stmt)
        return _format_qualified_columns(result.all())


def _format_qualified_columns(rows: list[tuple[str, str]]) -> list[str]:
    seen: set[str] = set()
    qualified: list[str] = []
    for table_name, column_name in rows:
        key = f"{table_name}.{column_name}"
        if key not in seen:
            seen.add(key)
            qualified.append(key)
    return qualified
