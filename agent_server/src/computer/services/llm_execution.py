from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.types import StreamWriter
import asyncio
from computer.config.logger import get_computer_logger
logger = get_computer_logger(__name__)
from computer.schema.langgraph_event import LanggraphEvent
from computer.utils.emit_event import emit_langgraph_event
from langchain_core.tools import Tool
from computer.config.openrouter import ComputerLLMConfig


class LLMExecutionService:
    def __init__(self, llm: ChatOpenAI, tools: list[Tool]):
        self.llm = llm
        self.tools = tools
        self.llm_with_tools = self.llm.bind_tools(self.tools)


    async def execute(self, messages: list[AnyMessage]) -> str:
        error_message = None
        error = None
        result = None
        for i in range(3):
            try:
                if error_message is not None and error_message in messages:
                    messages.remove(error_message)
                    error_message = None

                if error:
                    emit_langgraph_event(LanggraphEvent(step=f"{i+1}/3", status="LLM Error", message="Retrying..."))
                    error_message = HumanMessage(content=error)
                    messages.append(error_message)

                try:
                    result = await asyncio.wait_for(
                        self.llm_with_tools.ainvoke(messages), timeout=ComputerLLMConfig().llm_call_timeout
                    )
                except asyncio.TimeoutError:
                    logger.error(f"[COMPUTER_EXECUTOR] LLM timed out after {ComputerLLMConfig().llm_call_timeout}s (attempt {i+1}/3)")
                    error = "The AI model took too long to respond. Retrying..."
                    emit_langgraph_event(LanggraphEvent(step=f"{i+1}/3", status="LLM Error", message="Model timed out, retrying..."))
                    continue

                if not result:
                    error = "Failed to generate response"
                    continue

                # --- Tool calls ---
                if hasattr(result, "tool_calls") and result.tool_calls:
                    internal_response = AIMessage(content=result.content or "", tool_calls=result.tool_calls)
                    internal_response.name = "computer_agent"
                    emit_langgraph_event(LanggraphEvent(step=f"{i+1}/3", status="completed", message="Calling Tool..."))

                    return ("tool_calls", internal_response)

                # --- Final answer ---
                content = result.content or ""
                if not content.strip():
                    error = "Empty response. Please provide a tool call or final answer."
                    continue

                internal_response = AIMessage(content=content, tool_calls=[])
                internal_response.name = "computer_agent"

                emit_langgraph_event(LanggraphEvent(step=f"{i+1}/3", status="completed", message="Response generated"))

                return ("final_answer", internal_response)
          

            except Exception as e:
                error = f"Exception during LLM invocation: {str(e)}"
                continue

        # All retries exhausted
        if result is None:
            emit_langgraph_event(LanggraphEvent(step="3/3", status="failed", message=f"Failed to generate response after 3 retries. {error}"))
            raise Exception(f"Failed to generate response after 3 retries. {error}")

        content = result.content or "Failed to generate response. Please try again."
        internal_response = AIMessage(content=content, tool_calls=[])
        internal_response.name = "computer_agent"

        return ("final_answer", internal_response)
