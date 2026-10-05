from lancedb.pydantic import LanceModel, Vector
from pydantic import Field


class CatalogColumnLanceModel(LanceModel):
    """Full table row as written at ingestion time."""

    column_id: str
    table_name: str
    column_name: str
    data_type: str
    description: str
    example_use_cases: str
    enriched_text: str
    vector: Vector(768)


class CatalogColumnVectorResult(LanceModel):
    """Row returned by LanceDB vector search on catalog_columns."""

    column_id: str
    table_name: str
    column_name: str
    data_type: str
    description: str
    example_use_cases: str
    enriched_text: str
    distance: float = Field(alias="_distance")


class CatalogColumnKeywordResult(LanceModel):
    """Row returned by LanceDB FTS on catalog_columns (fts_column=enriched_text)."""

    column_id: str
    table_name: str
    column_name: str
    data_type: str
    description: str
    example_use_cases: str
    enriched_text: str
    score: float = Field(alias="_score")
