from pydantic import BaseModel, Field
import os
from functools import lru_cache
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

storage_base_path = os.getenv("STORAGE_BASE_PATH")
class LanceDBStoreConfig(BaseModel):
    path:Path  = Field(default=Path(storage_base_path + "/document_rag/store/ex_lancedb"))
    parent_table:str = Field(default="doc_parents")
    child_table:str = Field(default="doc_children")
    max_num_results:int = Field(default=25)


@lru_cache(maxsize=1)
def get_lancedb_store_config() -> LanceDBStoreConfig:
    return LanceDBStoreConfig()