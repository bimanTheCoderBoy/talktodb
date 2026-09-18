from langchain_core.tools import tool
from langgraph.types import Command
from pydantic import BaseModel, Field


def create_ask_user_tool():

    class AskUserArgs(BaseModel):
        message: str = Field(description="The question or clarification to present to the user. Be polite, specific, and concise.")

    @tool("ask_user_tool", args_schema=AskUserArgs, parse_docstring=False)
    async def ask_user(message:str) -> Command:
        """
        Pause execution to request clarification or approval from the human user.

        ## How the tool works [Summary]
        This tool interrupts the automated agent flow and presents a message to the user in the chat interface.
        1.  It takes a text `message` from the agent.
        2.  It halts the agent's execution.
        3.  It waits for the user to type a response.
        4.  The user's response is then fed back to the agent as the result of this tool call.

        ## When to use
        -   **MANDATORY**: Before calling `run_eds_fixer_tool` (unless the user already explicitly confirmed).
        """
        return Command(goto="ask_user_tool_helper")
    return ask_user