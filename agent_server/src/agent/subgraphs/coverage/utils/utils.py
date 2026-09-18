from typing import List
from langchain_core.messages import ToolMessage, AnyMessage

def update_last_tool_message_of_master_graph(main_message_context: List[AnyMessage], message: str):
    if not main_message_context:
        return None
    
    last_tool_message = main_message_context[-1]
    if isinstance(last_tool_message, ToolMessage):
        last_tool_message.content = last_tool_message.content +"\n↓\n" + message
        return main_message_context[:-1] + [last_tool_message]
    else:
        return None
