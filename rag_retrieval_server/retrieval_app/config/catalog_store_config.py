from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

storage_base_path = os.getenv("STORAGE_BASE_PATH")


class CatalogStoreConfig(BaseModel):
    """LanceDB store for semantic catalog columns (ingested from manage_db_context)."""

    path: Path = Field(default=Path(storage_base_path + "/document_rag/catalog_store"))
    columns_table: str = Field(default="catalog_columns")
    vector_column: str = Field(default="vector")
    fts_column: str = Field(default="enriched_text")
    max_num_results: int = Field(default=25)
    embed_dim: int = Field(default=768)


@lru_cache(maxsize=1)
def get_catalog_store_config() -> CatalogStoreConfig:
    return CatalogStoreConfig()
