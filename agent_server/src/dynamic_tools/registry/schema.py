from pydantic import BaseModel
from typing import Dict, List, Any


class DynamicToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]

class DynamicToolDefinitionResult(BaseModel):
    success: bool
    error: str | None = None
    tools: List[DynamicToolDefinition] | None = None

class DynamicToolCallResult(BaseModel):
    success: bool
    error: str | None = None
    result: Any | None = None
