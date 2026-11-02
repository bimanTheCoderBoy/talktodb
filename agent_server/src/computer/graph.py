from langgraph.graph import StateGraph, END, START

from computer.nodes.executor import executor_node
from computer.nodes.frontend_tool_runner import frontend_tool_runner
from computer.nodes.input_layer import input_layer_node
from computer.nodes.tool_runner import tool_node_wrapper
from computer.state import AgentState, ctx_schema_State
from computer.utils.tool_call_utils import (
    has_pending_frontend_tool_calls,
    has_pending_server_tool_calls,
)


workflow = StateGraph(AgentState, context_schema=ctx_schema_State)

workflow.add_node("input_layer", input_layer_node)
workflow.add_node("executor", executor_node)
workflow.add_node("tools", tool_node_wrapper)
workflow.add_node("frontend_tools", frontend_tool_runner)


def should_continue(state: AgentState):
    if has_pending_server_tool_calls(state):
        return "tools"
    if has_pending_frontend_tool_calls(state):
        return "frontend_tools"
    return END


def after_server_tools(state: AgentState):
    if has_pending_frontend_tool_calls(state):
        return "frontend_tools"
    return "executor"


workflow.add_edge(START, "input_layer")
workflow.add_edge("input_layer", "executor")
workflow.add_conditional_edges(
    "executor",
    should_continue,
    ["tools", "frontend_tools", END],
)
workflow.add_conditional_edges(
    "tools",
    after_server_tools,
    ["frontend_tools", "executor"],
)
workflow.add_edge("frontend_tools", "executor")

graph = workflow.compile(name="Computer Agent Graph").with_config({"recursion_limit": 50})
