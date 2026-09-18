from pydantic import BaseModel, Field
from typing import Annotated
import os
from pydantic.dataclasses import dataclass

class SQLGeneratorLLMConfig(BaseModel):
    """LLM configuration for SQL Generator."""
    api_key: Annotated[str, Field(default=os.getenv("OPENROUTER_API_KEY"))]
    base_url: Annotated[str, Field(default=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))]
    model: Annotated[str, Field(default=os.getenv("OPENROUTER_MODEL_SQL_GENERATOR", "google/gemini-2.0-flash-001"))]
    temperature: Annotated[float, Field(default=float(os.getenv("DB_AGENT_LLM_TEMPERATURE", "0.1")))]
    disable_streaming: Annotated[bool, Field(default=True)]

@dataclass
class AssetDBRagToolConfig :
    MAX_RETRIES:Annotated[int, Field(default=int(os.getenv("ASSET_DB_RAG_MAX_RETRIES", "3")))]
    llm:Annotated[dict, Field(default=SQLGeneratorLLMConfig().model_dump())]