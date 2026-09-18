from collections import Counter
from langchain_core.messages import ToolMessage, AIMessage, HumanMessage
from langgraph.types import Command
from db_agent_v2.state import AgentState
from db_agent_v2.config.agent_config import MAXIMUM_TOOL_RECURSION_LIMIT

MAX_TURN_TOOL_CALLS = 2 * MAXIMUM_TOOL_RECURSION_LIMIT


def _get_current_turn_tool_counts(messages: list) -> Counter:
    """Count ToolMessage executions per tool in the current turn (since last HumanMessage)."""
    counts = Counter()
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            break
        if isinstance(msg, ToolMessage):
            counts[msg.name] += 1
    return counts


def loop_detector(state: AgentState):
    """
    Guards against runaway tool execution. Three checks:
    1. Total tool calls in the current turn.
    2. Any single tool called too many times total (even if not consecutive).
    3. Consecutive same-tool recursion.
    """
    messages = state.internal_messages
    if not messages:
        return Command(goto="executor_react_agent")

    tool_counts = _get_current_turn_tool_counts(messages)
    total = sum(tool_counts.values())

    # --- Check 1: total tool calls in current turn ---
    if total >= MAX_TURN_TOOL_CALLS:
        raise Exception(
            f"Tool call limit reached: {total} tool calls this turn (max {MAX_TURN_TOOL_CALLS})."
        )

    # --- Check 2: any single tool called too many times total ---
    for tool_name, count in tool_counts.items():
        if count >= MAXIMUM_TOOL_RECURSION_LIMIT:
            raise Exception(
                f"Loop detected: '{tool_name}' called {count} times this turn "
                f"(max {MAXIMUM_TOOL_RECURSION_LIMIT}). Stopping."
            )

    # --- Check 3: consecutive same-tool recursion ---
    recent_tool_messages = []
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            recent_tool_messages.append(msg)
        elif isinstance(msg, AIMessage) and msg.tool_calls is not None and len(msg.tool_calls) > 0:
            continue
        else:
            break

    if recent_tool_messages:
        last_tool_name = recent_tool_messages[0].name
        consecutive_count = 0
        for msg in recent_tool_messages:
            if msg.name == last_tool_name:
                consecutive_count += 1
            else:
                break

        
        if consecutive_count >= MAXIMUM_TOOL_RECURSION_LIMIT:
            raise Exception(
                f"Loop detected: '{last_tool_name}' called {consecutive_count} times "
                f"consecutively. Stopping."
            )

    return Command(goto="executor_react_agent")
