from pydantic import BaseModel, Field
from functools import lru_cache
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()
import os
storage_base_path = os.getenv("STORAGE_BASE_PATH")
class EmbeddingModelConfig(BaseModel):
    model_name: str = Field(default=str("BAAI/bge-base-en-v1.5"))
    is_offline_model: bool = Field(default=False)
    dim: int = Field(default=768)
    local_path: str = Field(default=str(storage_base_path + "/document_rag/raw_embedding_models"))


@lru_cache(maxsize=1)
def get_embedding_model_config() -> EmbeddingModelConfig:
    return EmbeddingModelConfig()

