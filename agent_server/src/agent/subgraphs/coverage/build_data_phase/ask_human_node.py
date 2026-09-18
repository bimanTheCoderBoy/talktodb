import uuid
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command, interrupt
from agent.utils.state import State


def ask_human_node(state: State):
    message = state.coverage_message_context[-1]
    if isinstance(message, AIMessage) and message.tool_calls:
        ask_message = message.tool_calls[0].get("args", {}).get(
            "detail_task",
            "Plz provide the region (address, state, town, postcode), site/tower IIDs or cell IIDs to run the Coverage",
        )
    else:
        ask_message = "Plz provide the region (address, state, town, postcode), site/tower IIDs or cell IIDs to run the Coverage"

    result = interrupt({"type": "ASK_HUMAN", "content": ask_message})

    if isinstance(message, AIMessage) and message.tool_calls:
        tool_call_id = message.tool_calls[0].get("id", uuid.uuid4())
        response = ToolMessage(content=result, tool_call_id=tool_call_id, name="ask_human")
    else:
        response = ToolMessage(content=result, tool_call_id=uuid.uuid4(), name="ask_human")

    return Command(
        update={
            "messages": [response],
            "coverage_message_context": state.coverage_message_context + [response],
        },
        goto="coverage_get_cell_iids_node",
    )
