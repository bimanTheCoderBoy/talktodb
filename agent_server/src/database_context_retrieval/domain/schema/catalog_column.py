from __future__ import annotations

from pydantic import BaseModel, Field


class CatalogColumnInfo(BaseModel):
    table_name: str
    column_name: str
    data_type: str
    description: str
    example_use_cases: str


class CatalogColumnLookupResult(BaseModel):
    success: bool = Field(
        default=True,
        description="False when lookup failed due to validation or system errors.",
    )
    error: str | None = Field(
        default=None,
        description="Error message when success is false.",
    )
    found: bool
    queried_table_name: str
    queried_column_name: str
    column: CatalogColumnInfo | None = None
    similar_column_names: list[str] = Field(default_factory=list)

    @classmethod
    def failure(
        cls,
        queried_table_name: str,
        queried_column_name: str,
        error: str,
    ) -> CatalogColumnLookupResult:
        return cls(
            success=False,
            error=error,
            found=False,
            queried_table_name=queried_table_name,
            queried_column_name=queried_column_name,
        )
