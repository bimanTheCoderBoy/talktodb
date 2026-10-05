from pydantic import BaseModel, Field


class CatalogColumn(BaseModel):
    """DTO for a catalog column hit from vector or keyword search."""

    column_id: str
    table_name: str
    column_name: str
    data_type: str
    description: str
    example_use_cases: str
    value: float = Field(
        default=0.0,
        description="Rerank score in API responses; vector distance or FTS score before fusion.",
    )
