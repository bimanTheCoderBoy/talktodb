from langchain_core.messages import ToolMessage, AIMessage
from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from computer.state import AgentState, ctx_schema_State
from computer.tools import get_computer_tools_for_user
from computer.config.logger import get_computer_logger
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig

logger = get_computer_logger(__name__)

async def tool_node_wrapper(state: AgentState, runtime: Runtime[ctx_schema_State]):
    user_email = getattr(runtime.context, "user_email", None) or getattr(state, "user_email", None)
    if not user_email:
        logger.error("No user email found in runtime context or in the state. provide a user email in the runtime context or in the state.")
        raise ValueError("No user email found in runtime context or in the state. provide a user email in the runtime context or in the state.")
    else:
        fs_tools = await get_computer_tools_for_user(user_email)
    tool_node = ToolNode(tools=fs_tools)
    last_message = state.internal_messages[-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"internal_messages": state.internal_messages}

    tool_calls = last_message.tool_calls
    tool_outputs = await tool_node.ainvoke(tool_calls)
    if isinstance(tool_outputs, dict):
        tool_outputs = tool_outputs.get("messages", [])
    logger.info(f"Tool outputs: {tool_outputs}")

    internal_messages_to_add = []
    ui_messages_to_add=[]
    compiled_updates = {}
    compiled_goto = []
    is_a_command = False
    """Here We are mergeing if we get multiple Commands from parallel Tool Call"""


    for item in tool_outputs:
        if isinstance(item, Command):
            is_a_command = True
            # Track and merge dynamic routing destinations
            if item.goto:
                if isinstance(item.goto, list):
                    compiled_goto.extend(item.goto)
                else:
                    compiled_goto.append(item.goto)
            
            # Unpack and merge state dictionaries
            if item.update:
                for key, val in item.update.items():
                    if key == "internal_messages":
                        internal_messages_to_add.extend(val if isinstance(val, list) else [val])
                    elif key == "ui_messages":
                        ui_messages_to_add.extend(val if isinstance(val, list) else [val])
                    else:
                        # Non-reducer updates: later items overwrite earlier ones
                        compiled_updates[key] = val
        else:
            # Handle standard ToolMessage returns
            internal_messages_to_add.append(item)
            ui_messages_to_add.append(item)

    # logger.info(f"{compiled_updates}")
    logger.info(internal_messages_to_add)
    logger.info(ui_messages_to_add)
    
    compiled_updates["internal_messages"]=state.internal_messages+internal_messages_to_add
    compiled_updates["ui_messages"]=state.ui_messages+ui_messages_to_add

    if is_a_command:
        return Command(
            goto=compiled_goto,
            update=compiled_updates
        )
    else:
        return compiled_updates




