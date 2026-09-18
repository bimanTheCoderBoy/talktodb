import os
from pydantic import BaseModel, Field
from typing import Annotated

IS_LOCAL_LLM_PROVIDER = os.getenv("IS_LOCAL_LLM_PROVIDER", "false") == "true"


class ComputerLLMConfig(BaseModel):
    """LLM configuration for Computer Agent (OpenRouter)."""
    api_key: Annotated[str, Field(default=os.getenv("OPENROUTER_API_KEY"))]
    base_url: Annotated[str, Field(default=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))]
    model: Annotated[str, Field(default=os.getenv("OPENROUTER_MODEL_COMPUTER", "google/gemini-2.0-flash-001"))]
    temperature: Annotated[float, Field(default=float(os.getenv("COMPUTER_LLM_TEMPERATURE", "0.0")))]
    if not IS_LOCAL_LLM_PROVIDER:
            extra_body: Annotated[dict, Field(default={
        "chat_template_kwargs": {"enable_thinking": False},
        "provider": {"order": os.getenv("PROVIDER_ORDER", "deepinfra,google-vertex,parasail,atlas-cloud,novita").split(","), "allow_fallbacks": True},
    })]
    llm_retry_count: Annotated[int, Field(default=int(os.getenv("LLM_RETRY_COUNT", "3")))]
    llm_call_timeout: Annotated[float, Field(default=float(os.getenv("LLM_CALL_TIMEOUT", "90")))]
