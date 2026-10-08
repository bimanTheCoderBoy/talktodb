from pydantic import BaseModel
from typing import Callable, Any

class DynamicTool(BaseModel):
    name: str
    description: str
    callable: Callable[..., Any]
    input_schema: type[BaseModel]