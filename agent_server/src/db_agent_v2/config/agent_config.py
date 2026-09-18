import os
from pydantic import BaseModel, Field
from typing import Annotated

# Maximum number of times a tool can be called consecutively
# Keep this strict to avoid long-running retry loops.
MAXIMUM_TOOL_RECURSION_LIMIT = int(os.getenv("DB_AGENT_MAX_TOOL_RECURSION_LIMIT", "4"))

# Maximum size of tool result content before truncation
MAXIMUM_TOOL_RESULT_SIZE = int(os.getenv("DB_AGENT_MAX_TOOL_RESULT_SIZE", "5000"))

# Global LLM call timeout (seconds). Applies to all LLM invocations across both agents.
LLM_CALL_TIMEOUT = float(os.getenv("LLM_CALL_TIMEOUT", "90"))
IS_LOCAL_LLM_PROVIDER = os.getenv("IS_LOCAL_LLM_PROVIDER", "false") == "true"
class SummaryLLMConfig(BaseModel):
    """LLM configuration for DB Agent V2 Summary."""
    api_key: Annotated[str, Field(default=os.getenv("OPENROUTER_API_KEY"))]
    base_url: Annotated[str, Field(default=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))]
    model: Annotated[str, Field(default=os.getenv("OPENROUTER_MODEL_SUMMARY", "google/gemini-2.0-flash-001"))]
    temperature: Annotated[float, Field(default=float(os.getenv("DB_AGENT_LLM_TEMPERATURE", "0.0")))]
    if not IS_LOCAL_LLM_PROVIDER:
            extra_body: Annotated[dict, Field(default={
        "chat_template_kwargs": {"enable_thinking": False},
        "provider": {"order": os.getenv("PROVIDER_ORDER", "google-vertex,deepinfra,parasail,atlas-cloud,novita").split(","), "allow_fallbacks": True},
    })]

class ExecutorLLMConfig(BaseModel):
    """LLM configuration for DB Agent V2 Executor."""
    api_key: Annotated[str, Field(default=os.getenv("OPENROUTER_API_KEY"))]
    base_url: Annotated[str, Field(default=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))]
    model: Annotated[str, Field(default=os.getenv("OPENROUTER_MODEL_DB", "google/gemini-2.0-flash-001"))]
    temperature: Annotated[float, Field(default=float(os.getenv("DB_AGENT_LLM_TEMPERATURE", "0.0")))]
    if not IS_LOCAL_LLM_PROVIDER:
            extra_body: Annotated[dict, Field(default={
        "chat_template_kwargs": {"enable_thinking": False},
        "provider": {"order": os.getenv("PROVIDER_ORDER", "google-vertex,deepinfra,parasail,atlas-cloud,novita").split(","), "allow_fallbacks": True},
    })]
    model_kwargs: Annotated[dict, Field(default={
        # "stop": [
        #     "\n\nNote:", "\n\nAdditional", "\n\nFor reference",
        #     "\n\nRecommendation", "\n\nPlease note", "\n\nKeep in mind",
        #     "\n\nFor your reference", "\n\nWould you like", "\n\nLet me know",
        #     "\n\nFeel free", "\n\nIf you need", "\n\nIf you want",
        #     "\n\nIf you would", "\n\nShall I",
        # ]
    })]
