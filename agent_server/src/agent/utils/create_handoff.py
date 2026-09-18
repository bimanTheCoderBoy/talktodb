from typing import Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from agent.utils.state import State
from langchain_core.messages import ToolMessage


def create_handoff_tool(agent_name: str, description: str, tool_name: str = None, goto_node: str = None):
    """Creates handoff tool that returns Command"""
    
    @tool(f"transfer_to_{agent_name}" if tool_name is None else tool_name, description=description)
    def handoff_tool(
        state: Annotated[State, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
        detail_task: Annotated[str,"based on the user's intention, provide a detailed and very fulfilled task and it's description in the user's voice"]
    ) -> Command:
        
        
        tool_message = ToolMessage(
            content=f"", 
            tool_call_id=tool_call_id,
            artifact=f"{detail_task}"
        )
        # Use custom goto_node if provided, otherwise use agent_name+"_node"
        goto = goto_node if goto_node is not None else agent_name+"_node"
        
        if (agent_name == "ask_human"):
            return Command( 
                goto=goto,
            )
        elif (tool_name == "return_to_master"):
            master_message_context = state.main_message_context
            master_message_context[-1].content = "user don't want to run coverage analysis any more."

            return Command( 
                goto=goto,
                update={"messages":[tool_message], "coverage_message_context":state.coverage_message_context+[tool_message], "main_message_context":master_message_context}
            )

        else:
            return Command( 
                goto=goto,
                update={"messages":[tool_message], "main_message_context":state.main_message_context+[tool_message]}
            )
    
    return handoff_tool

