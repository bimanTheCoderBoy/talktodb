import logging
import os
import json
from typing import List, Tuple

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, AnyMessage

logger = logging.getLogger(__name__)
from dotenv import load_dotenv
load_dotenv()
MAX_CONTEXT_CHARS = int(os.getenv("DB_AGENT_MAX_CONTEXT_CHARS", "200000"))
from db_agent_v2.config.agent_config import MAXIMUM_TOOL_RESULT_SIZE
SUMMARIZATION_PROMPT = (
    "Summarize the actions taken so far in this conversation. Focus on:\n"
    "1. What the user originally asked.\n"
    "2. Which tools were successfully run.\n"
    "3. What data was found.\n"
    "make it like event summary like : `user asked for the cell details, tool was run to get the cell details, the cell details were found and returned to the user.`"
    "DO NOT summarize specific Network Parameters values, only the status of the investigation."
    "The Maximum length of the summary should not exceed 2000 characters."
)


def split_into_turns(messages: List[AnyMessage]) -> List[List[AnyMessage]]:
    """Split a flat message list into turns delimited by HumanMessage."""
    turns: List[List[AnyMessage]] = []
    current: List[AnyMessage] = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            if current:
                turns.append(current)
            current = [msg]
        else:
            current.append(msg)
    if current:
        turns.append(current)
    return turns


def strip_tool_messages(turn: List[AnyMessage]) -> List[AnyMessage]:
    """Remove ToolMessages from a turn, keeping Human and AI messages only."""
    kept = []
    for msg in turn:
        if isinstance(msg, ToolMessage):
            continue
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            continue
        kept.append(msg)
    return kept


def _safe_serialize(value) -> str:
    """Serialize arbitrary values to text without raising."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        try:
            return str(value)
        except Exception:
            return ""


def estimate_chars(messages: List[AnyMessage]) -> int:
    """
    Approximate context size for mixed message payloads.

    Includes message identity + content fields so estimates remain stable even when
    message.content is a non-string structure (list/dict/blocks).
    """
    total = 0
    for msg in messages:
        payload = {
            "type": getattr(msg, "type", type(msg).__name__),
            "name": getattr(msg, "name", None),
            "content": getattr(msg, "content", None),
            "tool_calls": getattr(msg, "tool_calls", None),
            "additional_kwargs": getattr(msg, "additional_kwargs", None),
            "response_metadata": getattr(msg, "response_metadata", None),
        }
        logger.info(f"[CONTEXT] Payload {payload}\n\n")
        total += len(_safe_serialize(payload))
    return total
def doc_retrieval_tool_result_trim(messages: List[AnyMessage], trim_length: int = MAXIMUM_TOOL_RESULT_SIZE//2, keep_recent_turns: int = 3) -> List[AnyMessage]:
    """
    Trim the doc_retrieval_tool result from the messages.
    Keep the recent turns and trim the older turns.
    """
    turns = split_into_turns(messages)
    if not turns:
        return messages
    recent_count = min(keep_recent_turns, len(turns))
    older_turns = turns[:-recent_count]
    recent_turns = turns[-recent_count:]
    recent_flat = [m for t in recent_turns for m in t]
    if not older_turns:
        return recent_flat
    for turn in older_turns:
        for msg in turn:
            if isinstance(msg, ToolMessage) and msg.name == "doc_retrieval_tool":
                content = msg.content
                if len(content) > trim_length:
                    content = content[:trim_length]+"... (truncated)"
                    msg.content = content

    
    #make the messages flat old and recent turns
    older_flat = [m for t in older_turns for m in t]
    return older_flat + recent_flat


def compact_history(
    messages: List[AnyMessage],
    keep_recent_turns: int = 3,
    max_chars: int = MAX_CONTEXT_CHARS,
) -> Tuple[List[AnyMessage], List[List[AnyMessage]] | None]:
    """
    Two-phase compaction:
    1. Keep last `keep_recent_turns` turns in full. For older turns, drop ToolMessages
       and AI-with-tool-calls, keeping only Human + plain-AI messages.
    2. If the result still exceeds `max_chars`, return the older turns (unfiltered)
       separately so the caller can summarize them with an LLM.

    Returns (compacted_messages, older_turns_needing_summary_or_None).
    """
    if not messages:
        return messages, None

    turns = split_into_turns(messages)
    if not turns:
        return messages, None

    recent_count = min(keep_recent_turns, len(turns))
    older_turns = turns[:-recent_count] if recent_count < len(turns) else []
    recent_turns = turns[-recent_count:]

    recent_flat = [m for t in recent_turns for m in t]

    if not older_turns:
        return recent_flat, None

    # Phase 1: strip tool messages from older turns
    older_stripped = []
    for turn in older_turns:
        older_stripped.extend(strip_tool_messages(turn))

    combined = older_stripped + recent_flat
    total = estimate_chars(combined)
    logger.info(
        f"[CONTEXT] Phase-1 compaction: {len(older_turns)} older turns stripped, "
        f"{recent_count} recent kept, {total} chars"
    )

    if total <= max_chars:
        return combined, None

    # Phase 2: older turns need LLM summarization
    logger.info(
        f"[CONTEXT] Phase-2: still {total} chars (limit {max_chars}), "
        f"older turns will be summarized"
    )
    return recent_flat, older_turns


def build_summarization_input(older_turns: List[List[AnyMessage]]) -> str:
    """Flatten older turns into a text block suitable for LLM summarization."""
    lines = []
    for turn in older_turns:
        for msg in turn:
            role = type(msg).__name__.replace("Message", "")
            content = (getattr(msg, "content", "") or "")
            if isinstance(msg, ToolMessage):
                lines.append(f"[{msg.name} result]: {content}")
            elif isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                tool_names = ", ".join(tc.get("name", "?") for tc in msg.tool_calls)
                args = ", ".join(_safe_serialize(tc.get("args", {})) for tc in msg.tool_calls)
                lines.append(f"[AI tool request: {tool_names} with arguments: {args}]")
            else:
                lines.append(f"[{role}]: {content}")
    return "\n".join(lines)
