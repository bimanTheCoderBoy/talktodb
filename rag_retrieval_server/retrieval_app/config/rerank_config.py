from pydantic import BaseModel, Field
from pathlib import Path
from functools import lru_cache
import os

storage_base_path = os.getenv("STORAGE_BASE_PATH")
class RerankConfig(BaseModel):
    name: str = Field(default=str("jinaai/jina-reranker-v1-tiny-en"))
    is_offline_model: bool = Field(default=True)
    top_n: int = Field(default=5)
    local_path: str = Field(default=str( storage_base_path+ "/document_rag/raw_embedding_models"))


@lru_cache(maxsize=1)
def get_rerank_config() -> RerankConfig:
    return RerankConfig()
