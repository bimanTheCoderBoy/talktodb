import os
from pydantic import BaseModel, Field
from typing import Annotated



IS_LOCAL_LLM_PROVIDER = os.getenv("IS_LOCAL_LLM_PROVIDER", "false") == "true"


class CoverageLLMConfig(BaseModel):
    """LLM configuration for Coverage Agent."""
    api_key: Annotated[str, Field(default=os.getenv("OPENROUTER_API_KEY"))]
    base_url: Annotated[str, Field(default=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))]
    model: Annotated[str, Field(default=os.getenv("OPENROUTER_MODEL_COVERAGE", "google/gemini-2.0-flash-001"))]
    temperature: Annotated[float, Field(default=float(os.getenv("COVERAGE_LLM_TEMPERATURE", "0.2")))]
    max_retries: Annotated[int, Field(default=int(os.getenv("OPENROUTER_MAX_RETRIES", "3")))]
    request_timeout: Annotated[int, Field(default=int(os.getenv("OPENROUTER_REQUEST_TIMEOUT", "30")))]
    if not IS_LOCAL_LLM_PROVIDER:
            extra_body: Annotated[dict, Field(default={
            "include_reasoning": True,
            "provider": {"order": os.getenv("PROVIDER_ORDER", "google-vertex,deepinfra,parasail,atlas-cloud,novita").split(","), "allow_fallbacks": True},
            })]


