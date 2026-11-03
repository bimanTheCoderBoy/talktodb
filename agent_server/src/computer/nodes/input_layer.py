
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime
from computer.state import AgentState, ctx_schema_State
from computer.config.logger import get_computer_logger
logger = get_computer_logger(__name__)


async def input_layer_node(state: AgentState, runtime: Runtime[ctx_schema_State]):
    thread_id = getattr(runtime.context, "thread_id", None)
    user_email = getattr(runtime.context, "user_email", None)

    if state.input_message is None:
        logger.error("Input message is required")
        raise ValueError("Input message is required")

    user_msg = HumanMessage(content=state.input_message.content)
   
    logger.info(f"Input message: {state.input_message.content}")

    return {
        "internal_messages": state.internal_messages + [user_msg],
        "ui_messages": state.ui_messages + [user_msg],
        "user_email": user_email,
        "thread_id": thread_id,
    }
