from langchain_core.messages import HumanMessage, ToolMessage
from agent.utils.state import State, RESET_SENTINEL


def input_handler_node(state: State):
    project_name = state.project_name

    if not state.main_message_context:
        raise ValueError("main_message_context is empty")

    last_tool_message = state.main_message_context[-1]
    if isinstance(last_tool_message, ToolMessage):

        input_message = HumanMessage(content=last_tool_message.artifact)
        initial_messages = [input_message] if state.coverage_message_context_clean_flag else  state.coverage_message_context + [input_message]
        return {
            "coverage_message_context": initial_messages,
            "tech_results": [RESET_SENTINEL],
            "coverage_message_context_clean_flag": False,
            "coverage_state": {
                "iids": None,
                "boundaries": None,
                "parameters": None,
                "output": None,
                "url_parameter_settings": None,
                "user_approved": None,
                "lte": None,
                "nr": None,
                "coverage_map_result": None,
                "coverage_report_result": None,
                "error": None,
            },
        }
    else:
        raise ValueError("Last message in the message context is not a tool message")
