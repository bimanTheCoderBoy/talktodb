import datetime
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import StreamWriter
from langgraph.runtime import Runtime
from computer.state import AgentState, ctx_schema_State
from computer.infra.llm import computer_llm
from computer.tools import get_computer_tools_for_user
from computer.prompts import computer_agent_system_prompt
from computer.skills.skill_registry import SkillRegistry
from computer.services.llm_execution import LLMExecutionService
from computer.config.logger import get_computer_logger

logger = get_computer_logger(__name__)


async def executor_node(state: AgentState, runtime: Runtime[ctx_schema_State]):
   
    date_time = datetime.datetime.now().strftime("%Y-%m-%d")
    project_name = runtime.context.project_name
    
    user_email = getattr(runtime.context, "user_email", None) or getattr(state, "user_email", None)
    if not user_email:
        logger.error("No user email found in runtime context or in the state. provide a user email in the runtime context or in the state.")
        raise ValueError("No user email found in runtime context. provide a user email in the runtime context or in the state.")
    else:
        try:
            tools_to_use = await get_computer_tools_for_user(user_email)

            logger.info(f"Loaded user-scoped filesystem tools for {user_email}")
        except ValueError as e:
            logger.error(f"Failed to load user-scoped tools: {e}; falling back to unrestricted.")
            raise RuntimeError("Failed to Load Tools Try again..")
    
    messages = [
        SystemMessage(
            content=computer_agent_system_prompt.format(
                project_name=project_name,
                date_time=date_time,
                user_email=user_email,
                available_skills=SkillRegistry.get().available_skills_xml,
            )
        )
    ]
    messages.extend(state.internal_messages)

    
    llm_execution_service = LLMExecutionService(llm=computer_llm, tools=tools_to_use)

    result_type, result_message = await llm_execution_service.execute(messages)

    if result_type == "tool_calls":
        return {
            "internal_messages": state.internal_messages + [result_message],
            # "ui_messages": state.ui_messages,
        }

    return {
        "internal_messages": state.internal_messages + [result_message],
        "ui_messages": state.ui_messages + [result_message],
    }
