from dynamic_tools.registry import dynamicTool
from pydantic import BaseModel

class TestToolInput(BaseModel):
    message: str

@dynamicTool(name="test", description="test tool", input_schema=TestToolInput)
def test_tool(message: str) -> str:
    return message