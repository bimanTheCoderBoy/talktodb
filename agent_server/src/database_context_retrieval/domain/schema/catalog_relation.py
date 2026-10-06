from __future__ import annotations

from pydantic import BaseModel, Field


class CatalogRelationInfo(BaseModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    relationship_type: str
    semantic_meaning: str
    related_tables: list[str]
    columns_attached: list[str]
    notes: list[str]


class CatalogRelationLookupResult(BaseModel):
    success: bool = Field(
        default=True,
        description="False when lookup failed due to validation or system errors.",
    )
    error: str | None = Field(
        default=None,
        description="Error message when success is false.",
    )
    found: bool
    queried_table_a: str
    queried_table_b: str
    relations: list[CatalogRelationInfo] = Field(default_factory=list)
    similar_table_a_names: list[str] = Field(default_factory=list)
    similar_table_b_names: list[str] = Field(default_factory=list)

    @classmethod
    def failure(
        cls,
        *,
        error: str,
        queried_table_a: str,
        queried_table_b: str,
    ) -> CatalogRelationLookupResult:
        return cls(
            success=False,
            error=error,
            found=False,
            queried_table_a=queried_table_a,
            queried_table_b=queried_table_b,
        )
