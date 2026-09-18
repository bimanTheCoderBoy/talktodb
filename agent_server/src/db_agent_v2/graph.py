from langgraph.graph import StateGraph, END, START
from db_agent_v2.state import AgentState, ctx_schema_State
from db_agent_v2.nodes.exeutor_react_agent import executor_react_agent
from db_agent_v2.nodes.tool_runner import tool_runner
from db_agent_v2.nodes.loop_detector import loop_detector
from db_agent_v2.nodes.input_layer import input_layer_node
from db_agent_v2.nodes.ask_user_tool_helper import  ask_user_tool_helper
from db_agent_v2.tools.update_eds.tool import update_eds_tool_helper
from db_agent_v2.tools.eds_fixer.tool import eds_fixer_tool_helper







# Define the graph
workflow = StateGraph(AgentState, context_schema=ctx_schema_State)

# Add nodes
workflow.add_node("input_layer", input_layer_node)
workflow.add_node("executor_react_agent", executor_react_agent)
workflow.add_node("tools", tool_runner) 
workflow.add_node("loop_detector", loop_detector)
#helper nodes
workflow.add_node("ask_user_tool_helper", ask_user_tool_helper)
workflow.add_node("update_eds_tool_helper", update_eds_tool_helper)
workflow.add_node("eds_fixer_tool_helper", eds_fixer_tool_helper)

# Define the entry point
workflow.add_edge(START, "input_layer")

# Define conditional logic for the agent
def should_continue(state: AgentState):
    last_message = state.internal_messages[-1]
    
    # If the LLM made tool calls, go to 'tools'
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    # Otherwise, we are done
    return END

workflow.add_conditional_edges(
    "executor_react_agent",
    should_continue,
    ["tools", END]
)

# Connect input layer to executor react agent
workflow.add_edge("input_layer", "executor_react_agent")

# Connect tools to loop detector
# workflow.add_edge("tools", "loop_detector")

# Note: 'loop_detector' returns a Command object that directs the flow 


# Compile the graph
graph = workflow.compile(name="DB Agent Graph").with_config({"recursion_limit": 50})
