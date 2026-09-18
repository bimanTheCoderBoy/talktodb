import asyncio
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from langgraph.config import get_stream_writer
from langgraph.types import StreamWriter
import datetime
import logging
from db_agent_v2.config.agent_config import LLM_CALL_TIMEOUT
from agent.tools.handoff import transfer_to_coverage_agent
from agent.tools.report_tools import list_coverage_reports, get_report_data
from agent.utils.state import State, ctx_schema_State
from agent.utils.llm import llm
from agent.utils.response_utils import clean_final_answer
from agent.constants.prompt_registry.master_agent_prompt import master_agent_system_prompt
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt import tools_condition
from security.encryption import EncryptionManager
from langchain_core.messages import ToolCall
import re
import uuid
logger = logging.getLogger(__name__)

async def input_handler_node(state: State, runtime:Runtime[ctx_schema_State]):
    project_name = runtime.context.project_name
    user_email = runtime.context.user_email
    input_message = state.input_message
    if isinstance(input_message, HumanMessage) and project_name:
        # Encrypt user message before it reaches the LLM
        enc_manager = EncryptionManager.instance()
        msg_for_ui = input_message  # plaintext for UI
        msg_for_llm = HumanMessage(content=input_message.content)
        new_entries = []

        if enc_manager.enabled:
            try:
                msg_for_llm, new_entries = await enc_manager.encrypt_message(
                    msg_for_llm, project_name
                )
                if new_entries:
                    logger.info(f"[COVERAGE INPUT] Encrypted {len(new_entries)} entities")
            except Exception as e:
                logger.warning(f"[COVERAGE INPUT] Encryption failed: {e}")
                msg_for_llm = HumanMessage(content=input_message.content)
                new_entries = []

        return {
            "messages": [msg_for_ui],
            "main_message_context": state.main_message_context + [msg_for_llm],
            "project_name": project_name,
            "user_email": user_email,
            "encryption_entries": state.encryption_entries + new_entries,
        }
    else:
        raise ValueError("Input message is not a human message or project name is not provided")


async def master_node(state: State, runtime: Runtime[ctx_schema_State]):
    """
    Core master agent node that decides the next action using the LLM.
    Returns tool calls if present, otherwise returns cleaned markdown response.
    """
    
    # Bind tools to the LLM
    llm_with_tools = llm.bind(stop=["\nObservation:", "Observation:"]).bind_tools([transfer_to_coverage_agent, list_coverage_reports, get_report_data])

    # Construct the message history
    date_time = f"{datetime.datetime.now().strftime('%Y-%m-%d')}"
    project_name = runtime.context.project_name
    messages = [SystemMessage(content=master_agent_system_prompt.format(
        project_name=project_name,
        date_time=date_time
    ))]
    
    # Add internal history
    messages.extend(state.main_message_context)
    
    # Invoke the LLM with retry logic
    result = None
    error = None
    stream_writer: StreamWriter = get_stream_writer()

    #--------------------------------------------------------
    # Check if the user wants to skip the coverage agent
    #--------------------------------------------------------
    SKIP_PATTERN = r"`<cell_iids>`\[(.*?)\]`<\\cell_iids>`"
    match = re.search(SKIP_PATTERN, messages[-1].content)
    if match:
        raw_list_string = match.group(1)
        if len(raw_list_string.strip()) > 0:
            #generate coverage run tool fake tool call
            coverage_run_tool_call = ToolCall(
                name="transfer_to_run_coverage_agent",
                args={
                    "detail_task":messages[-1].content
                },
                id= str(uuid.uuid4())
            )
            ai_message = AIMessage(name="master_agent", content="", tool_calls=[coverage_run_tool_call])

            return {
                    "messages": [ai_message],
                    "main_message_context": state.main_message_context + [ai_message]
                }

    #------------------------------------------------------------------------------------
        

    for i in range(3):
        try:
            # If there is an error, add it to the messages for retry
            if error:
                print(f"Error: {error}")
                stream_writer({"step": f"{i+1}/3", "status": "LLM Error", "message": f"Retrying..."})
                messages.append(HumanMessage(content=error))
            
            try:
                result = await asyncio.wait_for(llm_with_tools.ainvoke(messages), timeout=LLM_CALL_TIMEOUT)
            except asyncio.TimeoutError:
                logger.error(f"[COVERAGE MASTER] LLM call TIMED OUT after {LLM_CALL_TIMEOUT}s on attempt {i+1}/3")
                #error = "The AI model took too long to respond. Retrying..."
                stream_writer({"step": f"{i+1}/3", "status": "LLM Error", "message": "Model timed out, retrying..."})
                continue

            if not result:
                error = "Failed to generate response"
                continue
            
            # CHECK: Is it a Tool Call?
            if hasattr(result, "tool_calls") and result.tool_calls:
                # Return tool calls directly
                internal_response = AIMessage(content=result.content or "", tool_calls=result.tool_calls)
                internal_response.name = "master_agent"
                
                # Clear content for UI message
                ui_response = AIMessage(content="", tool_calls=result.tool_calls)
                ui_response.name = "master_agent"
                
                stream_writer({"step": f"{i+1}/3", "status": "completed", "message": "Calling Tool..."})
                
                if len(internal_response.tool_calls) > 1:
                    error = f"Multiple tool calls detected ({len(internal_response.tool_calls)}). Only one tool call is allowed at a time. Your previous tool calls were {internal_response.tool_calls}. Please call one tool at a time."
                    continue 

                return {
                    "messages": [ui_response],
                    "main_message_context": state.main_message_context + [internal_response]
                }
            
            # It's a final answer - clean and return
            content = result.content or ""
            if not content.strip():
                error = "Empty response received. Please provide a tool call or final answer."
                messages.append(HumanMessage(content=error))
                continue
            
            # Clean the content to remove reasoning text
            cleaned_content = clean_final_answer(content)
            
            if not cleaned_content:
                error = "Response contains only reasoning text. Please provide a final answer."
                messages.append(HumanMessage(content=error))
                continue
            
            # Success - return cleaned markdown
            internal_response = AIMessage(content=content, tool_calls=[])
            internal_response.name = "master_agent"

            ui_response = AIMessage(content=cleaned_content, tool_calls=[])
            ui_response.name = "master_agent"

            # Decrypt hash tokens in the UI response
            enc_manager = EncryptionManager.instance()
            if enc_manager.enabled and state.encryption_entries:
                try:
                    ui_response = enc_manager.decrypt_message(ui_response, state.encryption_entries)
                    logger.info("[COVERAGE MASTER] Decrypted UI response")
                except Exception as e:
                    logger.warning(f"[COVERAGE MASTER] Decryption failed: {e}")

            stream_writer({"step": f"{i+1}/3", "status": "completed", "message": "Response generated successfully"})

            return {
                "messages": [ui_response],
                "main_message_context": state.main_message_context + [internal_response]
            }
                    
        except Exception as e:
            error = f"Exception during LLM invocation: {str(e)}"
            messages.append(HumanMessage(content=error))
            continue
    
    # Handle complete failure after retries
    if result is None:
        stream_writer({"step": "3/3", "status": "failed", "message": f"Error: Failed to generate response. {error}"})
        # System/graph failure: do not persist this as an AIMessage in state.
        # Raise so the server marks the run as failed and the frontend can render it.
        raise Exception(f"Error: Failed to generate response. {error}")
    
    # Last attempt: use raw content if available
    content = result.content or ""
    cleaned_content = clean_final_answer(content) if content else "Failed to generate response. Please try again."

    internal_response = AIMessage(content=content, tool_calls=[])
    internal_response.name = "master_agent"

    ui_response = AIMessage(content=cleaned_content, tool_calls=[])
    ui_response.name = "master_agent"

    # Decrypt hash tokens in fallback response
    enc_manager = EncryptionManager.instance()
    if enc_manager.enabled and state.encryption_entries:
        try:
            ui_response = enc_manager.decrypt_message(ui_response, state.encryption_entries)
        except Exception as e:
            logger.warning(f"[COVERAGE MASTER] Fallback decryption failed: {e}")

    stream_writer({"step": "3/3", "status": "completed", "message": "Response generated"})

    return {
        "messages": [ui_response],
        "main_message_context": state.main_message_context + [internal_response]
    }
    



tool_node = ToolNode([transfer_to_coverage_agent, list_coverage_reports, get_report_data], messages_key="main_message_context")
