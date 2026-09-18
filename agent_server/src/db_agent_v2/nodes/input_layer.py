import asyncio
import logging
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from db_agent_v2.state import AgentState, ctx_schema_State
from db_agent_v2.config.agent_config import LLM_CALL_TIMEOUT
from db_agent_v2.utils.llm import summary_llm
from db_agent_v2.utils.context_history import (
    compact_history,
    build_summarization_input,
    SUMMARIZATION_PROMPT,
    MAX_CONTEXT_CHARS,
    estimate_chars,
    doc_retrieval_tool_result_trim,
)
from langgraph.runtime import Runtime
from security.encryption import EncryptionManager
from opentelemetry import trace

logger = logging.getLogger(__name__)


async def input_layer_node(state: AgentState, runtime: Runtime[ctx_schema_State]):
    project_name = runtime.context.project_name
    thread_id = getattr(runtime.context, "thread_id", None)
    user_email = getattr(runtime.context, "user_email", None)

    if state.input_message is None:
        raise ValueError("Input message is required")

    # --- Context compaction ---
    #doc retrieval tool result trimming
    logger.info(f"[INPUT_LAYER] Trimming doc retrieval tool result current length {len(state.internal_messages)}")
    state.internal_messages = doc_retrieval_tool_result_trim(state.internal_messages)
    logger.info(f"[INPUT_LAYER] Trimming doc retrieval tool result new length {len(state.internal_messages)}")
    compacted = list(state.internal_messages)
    older_turns_to_summarize = None
    context_length = estimate_chars(state.internal_messages)
    logger.info(f"[INPUT_LAYER] Context length {context_length} Maximum allowed {MAX_CONTEXT_CHARS}")
    if context_length > MAX_CONTEXT_CHARS:
        logger.info(f"[INPUT_LAYER] Context length {context_length} exceeds MAX_CONTEXT_CHARS {MAX_CONTEXT_CHARS}")
        compacted, older_turns_to_summarize = compact_history(state.internal_messages)

    if older_turns_to_summarize is not None:
        stream_writer = get_stream_writer()
        stream_writer({
            "step": "context",
            "status": "running",
            "message": "Summarizing conversation history...",
        })

        raw_text = build_summarization_input(older_turns_to_summarize)
        logger.info(f"[INPUT_LAYER] Raw text {raw_text}")
        summary_input = (
            f"{SUMMARIZATION_PROMPT}\n\n"
            f"--- conversation history ---\n{raw_text}\n---"
        )

        max_retries = 2
        summary_text = ""
        for attempt in range(1, max_retries + 2):
            try:
                summary_result = await asyncio.wait_for(
                    summary_llm.ainvoke([
                        SystemMessage(content="You are a concise summarizer."),
                        HumanMessage(content=summary_input),
                    ]),
                    timeout=LLM_CALL_TIMEOUT,
                )
                summary_text = summary_result.content or ""
                break
            except asyncio.TimeoutError:
                if attempt <= max_retries:
                    logger.warning(f"[INPUT_LAYER] Summarization LLM timed out (attempt {attempt}/{max_retries + 1}), retrying...")
                    stream_writer({"step": "context", "status": "retrying", "message": f"Summarization timed out, retry {attempt}/{max_retries}..."})
                    continue
                logger.error(f"[INPUT_LAYER] Summarization LLM TIMED OUT after {max_retries + 1} attempts")
                summary_text = "[Previous conversation context could not be summarized — model timed out]"
            except Exception as e:
                if attempt <= max_retries:
                    logger.warning(f"[INPUT_LAYER] Summarization failed (attempt {attempt}/{max_retries + 1}): {e}, retrying...")
                    stream_writer({"step": "context", "status": "retrying", "message": f"Summarization error, retry {attempt}/{max_retries}..."})
                    continue
                logger.warning(f"[INPUT_LAYER] Summarization failed after {max_retries + 1} attempts: {e}")
                summary_text = "[Previous conversation context could not be summarized]"

        summary_msg = SystemMessage(content=f"[Conversation Summary]\n{summary_text}")
        compacted = [summary_msg] + compacted

        stream_writer({
            "step": "context",
            "status": "completed",
            "message": "Conversation history summarized.",
        })
        logger.info(
            f"[INPUT_LAYER] Summarized older turns into {len(summary_text)} chars"
        )
    if compacted != state.internal_messages:
        old_count = len(state.internal_messages)
        new_count = len(compacted) + 1
        if old_count > new_count:
            logger.info(f"[INPUT_LAYER] Compacted internal_messages: {old_count} -> {new_count}")

    # Encrypt user message before it reaches the LLM
    enc_manager = EncryptionManager.instance()
    user_msg_for_ui = state.input_message  # plaintext for UI
    user_msg_for_llm = HumanMessage(content=state.input_message.content)
    new_entries = []

    if enc_manager.enabled and project_name:
        try:
            user_msg_for_llm, new_entries = await enc_manager.encrypt_message(
                user_msg_for_llm, project_name
            )
            if new_entries:
                logger.info(f"[INPUT_LAYER] Encrypted {len(new_entries)} entities in user message")
        except Exception as e:
            logger.warning(f"[INPUT_LAYER] Encryption failed, using plaintext: {e}")
            user_msg_for_llm = HumanMessage(content=state.input_message.content)
            new_entries = []

    compacted.append(user_msg_for_llm)

    return {
        "internal_messages": compacted,
        "ui_messages": state.ui_messages + [user_msg_for_ui],
        "project_name": project_name,
        "user_email": user_email,
        "thread_id": thread_id,
        "last_rag_filter": None,
        "encryption_entries": state.encryption_entries + new_entries,
    }
