from __future__ import annotations

from pydantic import BaseModel, Field

from database_context_retrieval.domain.schema.catalog_table import CatalogTableLookupResult


class CatalogRetrievalColumnHit(BaseModel):
    column_id: str
    table_name: str
    column_name: str
    data_type: str
    description: str
    example_use_cases: str
    value: float = Field(
        default=0.0,
        description="Rerank score from catalog hybrid search.",
    )


class CatalogTableEnrichedContext(BaseModel):
    table_name: str
    retrieval_score: float
    matched_columns: list[CatalogRetrievalColumnHit] = Field(default_factory=list)
    lookup: CatalogTableLookupResult


class CatalogContextSearchResult(BaseModel):
    success: bool = Field(default=True)
    error: str | None = Field(default=None)
    query: str
    column_hits: list[CatalogRetrievalColumnHit] = Field(default_factory=list)
    tables: list[CatalogTableEnrichedContext] = Field(default_factory=list)

    @classmethod
    def failure(cls, query: str, error: str) -> CatalogContextSearchResult:
        return cls(success=False, error=error, query=query)
