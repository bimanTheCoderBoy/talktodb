from langchain_core.messages import AIMessage, HumanMessage
from db_agent_v2.state import AgentState
from langgraph.types import interrupt, Command
from langchain_core.messages import ToolMessage
import uuid
async def ask_user_tool_helper(state:AgentState):

    last_message = state.ui_messages[-1]
    if not isinstance(last_message, AIMessage) and last_message.tool_calls is None or len(last_message.tool_calls) == 0:
        raise ValueError("No Valid Message to ask human for feedback")
    message_to_ask_user = last_message.tool_calls[0].get("args",{}).get("message", "Give me more info, so that i can understand the task better")

    #create an interrupt to ask human for feedback
    human_feedback = interrupt({"type":"ASK_HUMAN", "content":message_to_ask_user})
    #constracting fake tool message to return to the llm
    fake_tool_message = ToolMessage(
        tool_call_id=last_message.tool_calls[0].get("id",uuid.uuid4()),
        name=last_message.tool_calls[0].get("name","ask_user_tool"),
        content=human_feedback,
    )

    return Command(goto="executor_react_agent", update={"internal_messages":state.internal_messages + [fake_tool_message], "ui_messages": state.ui_messages + [fake_tool_message]}) 