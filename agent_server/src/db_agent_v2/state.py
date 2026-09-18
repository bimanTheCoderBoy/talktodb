from langchain_core.messages import AnyMessage, HumanMessage
from langchain_core.messages import ToolCall

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional



# class PlanningSteps(BaseModel):
#     steps:List[str]=Field(description="List of steps in detailed description to be executed in the order of execution")



class AgentState(BaseModel):
    # Internal messages are the messages that are sent to the LLM
    internal_messages: List[AnyMessage] = []
    #An trick to pass the input message to the other fields of the state
    input_message: HumanMessage|None=None
    # UI messages are the messages that are displayed to the user
    ui_messages: List[AnyMessage] = []

    #Tool can use it directly
    project_name:Optional[str]=None
    # LangGraph conversation thread identifier (when available).
    thread_id: Optional[str] = None

    helper:Optional[Dict[str, Any]]=None

    interrupt_data:Optional[Dict[str, Any]]=None

    # Stores the most recent asset_db_rag_tool result (columns + rows)
    # so dependent tools can resolve data_refs without re-executing SQL.
    last_rag_result: Optional[Dict[str, Any]] = None

    # Encryption: accumulated hash-to-value entries for decrypt
    encryption_entries: List[Dict[str, Any]] = []
    user_email: Optional[str] = None


class ctx_schema_State(BaseModel):
    # Context schema is the context of the project
    project_name: str
    thread_id: Optional[str] = None
    user_email: str
