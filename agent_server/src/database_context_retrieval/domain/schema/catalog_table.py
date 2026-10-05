from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CatalogColumnSummary(BaseModel):
    table_name: str
    column_name: str
    data_type: str
    description: str
    example_use_cases: str
    # created_at: datetime
    # updated_at: datetime


class CatalogTableInfo(BaseModel):
    name: str
    description: str
    primary_key_columns: list[str]
    important_columns: list[str] | None
    notes: list[str]
    created_at: datetime
    updated_at: datetime


class CatalogTableLookupResult(BaseModel):
    success: bool = Field(
        default=True,
        description="False when lookup failed due to validation or system errors.",
    )
    error: str | None = Field(
        default=None,
        description="Error message when success is false.",
    )
    found: bool
    queried_name: str
    table: CatalogTableInfo | None = None
    related_table_names: list[str] = Field(default_factory=list)
    columns: list[CatalogColumnSummary] = Field(default_factory=list)
    total_column_count: int = 0
    similar_table_names: list[str] = Field(default_factory=list)

    @classmethod
    def failure(cls, queried_name: str, error: str) -> CatalogTableLookupResult:
        return cls(
            success=False,
            error=error,
            found=False,
            queried_name=queried_name,
        )
