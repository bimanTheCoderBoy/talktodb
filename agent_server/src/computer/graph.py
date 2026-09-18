from langgraph.graph import StateGraph, END, START
from computer.state import AgentState, ctx_schema_State
from computer.nodes.executor import executor_node
from computer.nodes.tool_runner import tool_node_wrapper
from computer.nodes.input_layer import input_layer_node



workflow = StateGraph(AgentState, context_schema=ctx_schema_State)

workflow.add_node("input_layer", input_layer_node)
workflow.add_node("executor", executor_node)
workflow.add_node("tools", tool_node_wrapper)


def should_continue(state: AgentState):
    last_message = state.internal_messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


workflow.add_edge(START, "input_layer")
workflow.add_edge("input_layer", "executor")
workflow.add_conditional_edges("executor", should_continue, ["tools", END])
workflow.add_edge("tools", "executor")

graph = workflow.compile(name="Computer Agent Graph").with_config({"recursion_limit": 50})
