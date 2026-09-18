"""
Executor React Agent — Core LLM node for the DB Agent V2 graph.

Responsibilities:
1. Build context from conversation history (preprocessed by input layer)
2. Invoke LLM with tools bound
3. Return tool calls or cleaned final answers
4. Guard against hallucination (no-tool answers)
5. Deduplicate UI responses
6. Clean conversational endings from output
"""

import asyncio
import datetime
import logging
import re
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.config import get_stream_writer
from langgraph.types import StreamWriter
from db_agent_v2.state import AgentState, ctx_schema_State
from db_agent_v2.config.agent_config import LLM_CALL_TIMEOUT
from db_agent_v2.utils.llm import executor_llm
from db_agent_v2.tool_registry.registry import tool_registry
from db_agent_v2.prompts import database_agent_executer_prompt
from langgraph.runtime import Runtime
from security.encryption import EncryptionManager
from security.encryption.iid_hash_utils import HASHING_ENABLED as IID_HASHING_ENABLED, reverse_map_hashes
from db_agent_v2.db.DatabaseManager import global_db_manager

logger = logging.getLogger(__name__)

logger.info(f"[EXECUTOR_REACT_AGENT] IID_HASHING_ENABLED: {IID_HASHING_ENABLED}")


# ===========================================================================
# 2. OUTPUT CLEANING — strip reasoning, endings, tool names
# ===========================================================================
def _clean_final_answer(content: str) -> str:
    """Clean LLM output for UI display. Strips reasoning text and conversational endings."""
    if not content:
        return ""

    text = content.strip()

    # Extract content after "Final Answer:" if present
    match = re.search(r'Final\s+Answer\s*:', text, re.IGNORECASE)
    if match:
        text = text[match.end():].strip()

    # Remove JSON blobs
    text = re.sub(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', '', text, flags=re.DOTALL)

    # Remove ```json blocks
    text = re.sub(r'```json\s*', '', text)

    # Filter reasoning lines
    skip = [
        r'^\s*Thought\s*:', r'^\s*STEP\s*\d+', r'^\s*Action\s*:',
        r'^\s*Observation\s*:', r'^\s*Final\s+Answer:', r'^\s*-?\s*STEP',
        r'^\s*\[Final\s+Answer',
    ]
    lines = [l for l in text.split('\n') if not any(re.match(p, l, re.IGNORECASE) for p in skip)]
    text = '\n'.join(lines).strip()

    # Remove leftover "Final Answer:" prefix
    if text.lower().startswith('final answer:'):
        text = text[13:].strip()

    # Strip tool names AND internal parameter names from user-facing output
    strip_terms = [
        # Tool names
        'asset_db_rag_tool', 'audit_engine_tool', 'discrepancy_engine_tool',
        'run_eds_fixer_tool', 'update_eds_tool', 'ask_user_tool',
        'eds_fixer_tool', 'eds_fixer', 'update_eds',
        # Internal parameter names
        'need_latest_data', 'audit_execute_for', 'data_refs',
        'all=True', 'all=true', 'all=False', 'all=false',
    ]
    for term in strip_terms:
        text = text.replace(f'`{term}`', '')
        text = re.sub(rf'\b{re.escape(term)}\b', '', text, flags=re.IGNORECASE)
    # Clean up leftover artifacts
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r',\s*,', ',', text)
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # triple newlines → double
    text = text.strip()

    # Strip conversational endings (both newline-separated and inline)
    endings = [
        r'Would you like\b.*', r'Let me know\b.*', r'Feel free\b.*',
        r'If you (?:need|want|would|like)\b.*', r'Please (?:confirm|let me|feel)\b.*',
        r'Shall I\b.*', r'Do you want\b.*', r'Is there anything\b.*',
        r'For (?:more|further|any)\b.*', r"I'?m ready to\b.*", r"I'?m here to\b.*",
        r'Happy to\b.*', r'Ready to\b.*',
    ]
    for e in endings:
        text = re.sub(rf'\n\s*{e}$', '', text, flags=re.IGNORECASE | re.DOTALL).strip()
        text = re.sub(rf'[.,;!]\s*{e}$', '.', text, flags=re.IGNORECASE | re.DOTALL).strip()

    return text


# ===========================================================================
# 3. ANTI-HALLUCINATION — check current turn only
# ===========================================================================
def _has_tool_result_in_current_turn(messages: list) -> bool:
    """Check if any tool was called in the current turn (after last HumanMessage)."""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return False  # reached turn boundary, no tool found
        if isinstance(m, ToolMessage):
            return True
    return False


# ===========================================================================
# 4. DEDUP — check if this answer already exists in UI
# ===========================================================================
def _is_duplicate_answer(ui_messages: list, content: str) -> bool:
    """Check if the same answer text already exists in recent UI messages."""
    if not content:
        return False
    for m in reversed(ui_messages[-5:]):
        if isinstance(m, AIMessage) and m.content and m.content == content:
            return True
    return False


# ===========================================================================
# MAIN EXECUTOR
# ===========================================================================
async def executor_react_agent(state: AgentState, runtime: Runtime[ctx_schema_State]):
    """Core agent node — invokes LLM, returns tool calls or final answer."""

    tools = tool_registry.get_all_tools()
    llm_with_tools = executor_llm.bind_tools(tools)

    # Build message history
    date_time = datetime.datetime.now().strftime('%Y-%m-%d')
    project_name = runtime.context.project_name
    messages = [SystemMessage(content=database_agent_executer_prompt.format(
        project_name=project_name, date_time=date_time
    ))]

    messages.extend(state.internal_messages)

    # Retry loop
    result = None
    error = None
    error_message = None
    stream_writer: StreamWriter = get_stream_writer()

    for i in range(3):
        try:
            # Clean previous error message
            if error_message is not None and error_message in messages:
                messages.remove(error_message)
                error_message = None

            if error:
                logger.warning(f"[EXECUTOR] Retry {i+1}/3 — {error}")
                stream_writer({"step": f"{i+1}/3", "status": "LLM Error", "message": "Retrying..."})
                error_message = HumanMessage(content=error)
                messages.append(error_message)

            try:
                result = await asyncio.wait_for(llm_with_tools.ainvoke(messages), timeout=LLM_CALL_TIMEOUT)
            except asyncio.TimeoutError:
                logger.error(f"[EXECUTOR] LLM call TIMED OUT after {LLM_CALL_TIMEOUT}s on attempt {i+1}/3")
                error = "The AI model took too long to respond. Retrying..."
                stream_writer({"step": f"{i+1}/3", "status": "LLM Error", "message": "Model timed out, retrying..."})
                continue

            if not result:
                error = "Failed to generate response"
                continue

            logger.info(f"[EXECUTOR] LLM result (tool_calls={bool(getattr(result, 'tool_calls', None))})")

            # --- Tool call ---
            if hasattr(result, "tool_calls") and result.tool_calls:
                internal_response = AIMessage(content=result.content or "", tool_calls=result.tool_calls)
                internal_response.name = "db_agent"
                stream_writer({"step": f"{i+1}/3", "status": "completed", "message": "Calling Tool..."})
                return {
                    "internal_messages": state.internal_messages + [internal_response],
                    "ui_messages": state.ui_messages  # tool_runner adds UI msgs on execution
                }

            # --- Final answer ---
            content = result.content or ""
            if not content.strip():
                error = "Empty response. Please provide a tool call or final answer."
                continue

            # Anti-hallucination: no tool called this turn = likely fabrication
            # EXCEPTION: educational/conversational questions don't need tools
            # user_query = ""
            # for m in reversed(state.internal_messages):
            #     if isinstance(m, HumanMessage):
            #         user_query = (m.content or "").lower().strip()
            #         break

            # is_educational = bool(re.search(
            #     r'\b(what is|what are|explain|define|describe|tell me about|how does|how do|meaning of|difference between)\b',
            #     user_query
            # ))
            # is_greeting = bool(re.search(
            #     r'^(hi|hello|hey|thanks|thank you|ok|okay|good|great|bye|morning|good morning|evening|good evening|afternoon|good afternoon|welcome|sup|yo|cheers)\b',
            #     user_query
            # ))

            # is_short_casual = len(user_query) < 20 and '?' not in user_query

            # Check if the query contains any data-requesting keywords
            # If not, it's likely conversational — don't force tool call
            # has_data_intent = bool(re.search(
            #     r'\b(how many|count|list|show|find|get|give|display|retrieve|fetch|query|search|'
            #     r'cells?|sites?|tilt|azimuth|height|pci|tac|earfcn|mimo|power|'
            #     r'audit|discrepanc|mismatch|fix|update|check|run|compare)\b',
            #     user_query
            # ))

            # if not _has_tool_result_in_current_turn(state.internal_messages) and i == 0 and has_data_intent and not is_educational and not is_greeting and not is_short_casual:
            #     error = (
            #         "You provided an answer without calling any tool. "
            #         "You MUST call a tool to retrieve data before answering. "
            #         "Do NOT use training knowledge for network data. Call the appropriate tool now."
            #     )
            #     logger.warning("[EXECUTOR] Anti-hallucination: answer without tool call, forcing retry")
            #     continue

            cleaned = _clean_final_answer(content)
            if not cleaned:
                error = "Response contains only reasoning text. Provide a final answer."
                continue

            # Build response
            internal_response = AIMessage(content=content, tool_calls=[])
            internal_response.name = "db_agent"
            ui_response = AIMessage(content=cleaned, tool_calls=[])
            ui_response.name = "db_agent"

            # Decrypt hash tokens in the UI response before it reaches the user
            enc_manager = EncryptionManager.instance()
            if enc_manager.enabled and state.encryption_entries:
                try:
                    ui_response = enc_manager.decrypt_message(ui_response, state.encryption_entries)
                    logger.info("[EXECUTOR] Decrypted UI response")
                except Exception as e:
                    logger.warning(f"[EXECUTOR] Decryption failed: {e}")

            # Catch-all: reverse-map any IID hashes that leaked into the LLM's response text
            if IID_HASHING_ENABLED and ui_response.content and global_db_manager:
                try:
                    import re as _re
                    _hash_pat = _re.compile(r'\b[0-9a-f]{32}\b')
                    found_hashes = set(_hash_pat.findall(ui_response.content))
                    if found_hashes:
                        async with global_db_manager.connection(state.project_name) as conn:
                            rmap = await reverse_map_hashes(conn, found_hashes)
                        if rmap:
                            fixed = ui_response.content
                            for h, orig in rmap.items():
                                fixed = fixed.replace(h, orig)
                            ui_response = AIMessage(content=fixed, tool_calls=[])
                            ui_response.name = "db_agent"
                            logger.info(f"[EXECUTOR] Reverse-mapped {len(rmap)} IID hashes in final response")
                except Exception as e:
                    logger.warning(f"[EXECUTOR] IID reverse-map failed: {e}")

            stream_writer({"step": f"{i+1}/3", "status": "completed", "message": "Response generated"})

            logger.info(f"[EXECUTOR] Final answer: {len(ui_response.content)} chars")
            return {
                "internal_messages": state.internal_messages + [internal_response],
                "ui_messages": state.ui_messages + [ui_response]
            }

        except Exception as e:
            error = f"Exception during LLM invocation: {str(e)}"
            continue

    # All retries failed
    if result is None:
        stream_writer({"step": "3/3", "status": "failed", "message": f"Error: {error}"})
        raise Exception(f"Failed to generate response after 3 retries. {error}")

    # Last resort: use raw content
    content = result.content or ""
    cleaned = _clean_final_answer(content) if content else "Failed to generate response. Please try again."

    internal_response = AIMessage(content=content, tool_calls=[])
    internal_response.name = "db_agent"
    ui_response = AIMessage(content=cleaned, tool_calls=[])
    ui_response.name = "db_agent"

    # Decrypt hash tokens in fallback response
    enc_manager = EncryptionManager.instance()
    if enc_manager.enabled and state.encryption_entries:
        try:
            ui_response = enc_manager.decrypt_message(ui_response, state.encryption_entries)
        except Exception as e:
            logger.warning(f"[EXECUTOR] Fallback decryption failed: {e}")

    stream_writer({"step": "3/3", "status": "completed", "message": "Response generated"})

    return {
        "internal_messages": state.internal_messages + [internal_response],
        "ui_messages": state.ui_messages + [ui_response]
    }
