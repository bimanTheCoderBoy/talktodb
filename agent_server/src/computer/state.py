from langchain_core.messages import AnyMessage, HumanMessage
from pydantic import BaseModel
from typing import List, Optional


class AgentState(BaseModel):
    internal_messages: List[AnyMessage] = []
    input_message: HumanMessage | None = None
    ui_messages: List[AnyMessage] = []
    thread_id: Optional[str] = None
    user_email: Optional[str] = None


class ctx_schema_State(BaseModel):
    thread_id: Optional[str] = None
    user_email: str
