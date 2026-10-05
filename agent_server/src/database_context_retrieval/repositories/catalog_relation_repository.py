from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database_context_retrieval.domain.catalog_keys import similar_table_names
from database_context_retrieval.domain.entity import CatalogRelation
from database_context_retrieval.domain.interface.i_catalog_relation_repository import (
    ICatalogRelationRepository,
)
from database_context_retrieval.domain.schema.catalog_relation import (
    CatalogRelationInfo,
    CatalogRelationLookupResult,
)


class CatalogRelationRepository(ICatalogRelationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_relation_info(
        self,
        *,
        table_a: str,
        table_b: str,
    ) -> CatalogRelationLookupResult:
        stmt = (
            select(CatalogRelation)
            .where(
                or_(
                    and_(
                        CatalogRelation.source_table == table_a,
                        CatalogRelation.target_table == table_b,
                    ),
                    and_(
                        CatalogRelation.source_table == table_b,
                        CatalogRelation.target_table == table_a,
                    ),
                )
            )
            .order_by(
                CatalogRelation.source_table,
                CatalogRelation.target_table,
                CatalogRelation.source_column,
            )
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        if rows:
            return CatalogRelationLookupResult(
                found=True,
                queried_table_a=table_a,
                queried_table_b=table_b,
                relations=[self._to_relation_info(row) for row in rows],
            )

        similar_a = await similar_table_names(self._session, table_a)
        similar_b = await similar_table_names(self._session, table_b)
        return CatalogRelationLookupResult(
            found=False,
            queried_table_a=table_a,
            queried_table_b=table_b,
            similar_table_a_names=similar_a,
            similar_table_b_names=similar_b,
        )

    @staticmethod
    def _to_relation_info(row: CatalogRelation) -> CatalogRelationInfo:
        return CatalogRelationInfo(
            source_table=row.source_table,
            source_column=row.source_column,
            target_table=row.target_table,
            target_column=row.target_column,
            relationship_type=row.relationship_type,
            semantic_meaning=row.semantic_meaning,
            related_tables=list(row.related_tables or []),
            columns_attached=list(row.columns_attached or []),
            notes=list(row.notes or []),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
