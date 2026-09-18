import inspect
import json
import re
import traceback
import logging
import time
from langchain_core.messages import ToolMessage, AIMessage, SystemMessage
from db_agent_v2.state import AgentState, ctx_schema_State
from db_agent_v2.tool_registry.registry import tool_registry
from db_agent_v2.tools.base import ToolOutput
from db_agent_v2.config.agent_config import MAXIMUM_TOOL_RESULT_SIZE
from db_agent_v2.utils.error_ui import format_tool_error_ui
from langgraph.types import Command
from langgraph.errors import GraphInterrupt
from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _emit_tool_runner_event(stream_writer, event: str, **payload):
    """
    Emit custom LangGraph stream events for tool-runner observability.
    Includes step/status/message fields to match frontend onCustomEvent parsing.
    """
    status_map = {
        "tool_execution_started": "running",
        "tool_execution_succeeded": "completed",
        "tool_execution_failed": "failed",
        "tool_execution_exception": "failed",
        "tool_execution_interrupted": "failed",
        "tool_execution_command_returned": "completed",
    }
    status = payload.pop("status", status_map.get(event, "running"))
    tool_name = payload.get("tool_name", "tool")
    tool_id = payload.get("tool_id")
    elapsed_ms = payload.get("elapsed_ms")
    error_text = payload.get("error")
    if error_text:
        message = f"{tool_name} failed: {error_text}"
    elif status == "running":
        message = f"Executing {tool_name}..."
    elif elapsed_ms is not None:
        message = f"{tool_name} completed in {elapsed_ms} ms"
    else:
        message = f"{tool_name} {status}"

    try:
        if stream_writer:
            stream_writer({
                # Frontend-supported shape
                "step": "tool",
                "status": status,
                "message": message,
                # Extended debug context
                "source": "db_agent.tool_runner",
                "event": event,
                "tool_id": tool_id,
                **payload,
            })
    except Exception:
       
        pass

def _normalize_col_key(name: str) -> str:
    """Collapse a column name to a canonical form for fuzzy matching.

    ``"Site IID"`` / ``"SITE_IID"`` / ``"site_iid"`` / ``"site iid"``
    all become ``"siteiid"``.
    """
    return name.strip().lower().replace("_", "").replace(" ", "")


def _find_column(columns: list[str], source_column: str) -> str | None:
    """Match *source_column* against stored column names.

    Tries exact case-insensitive match first, then falls back to a
    normalized match that ignores spaces vs underscores.
    Returns the actual column name as stored (preserving case), or None.
    """
    sc_lower = source_column.strip().lower()
    for col in columns:
        if col.lower() == sc_lower:
            return col

    sc_key = _normalize_col_key(source_column)
    for col in columns:
        if _normalize_col_key(col) == sc_key:
            return col

    return None


async def _resolve_data_refs(data_refs, tool_args, last_rag_result: dict | None):
    """Resolve data_refs by reading column values from the stored RAG result.

    ``last_rag_result`` has the shape ``{"columns": [...], "rows": [(...), ...]}``.
    Each ref maps a ``source_column`` (the column name or alias the LLM reads
    from the SQL / output) to a ``target_arg`` in the downstream tool.
    """
    if not last_rag_result:
        raise ValueError(
            "Cannot resolve data_refs: no stored RAG result. "
            "You must call asset_db_rag_tool first and it must succeed before "
            "calling a dependent tool with data_refs. Please retry the asset_db_rag_tool call."
        )

    columns: list[str] = last_rag_result.get("columns", [])
    rows: list = last_rag_result.get("rows", [])

    for ref in data_refs:
        if isinstance(ref, str):
            ref = json.loads(ref)

        source_column = ref.get("source_column")
        target_arg = ref.get("target_arg")

        if not source_column or not target_arg:
            raise ValueError(
                f"Malformed data_ref — both 'source_column' and 'target_arg' are required. Got: {ref}"
            )

        actual_col = _find_column(columns, source_column)
        if actual_col is None:
            raise ValueError(
                f"Cannot resolve data_ref: column '{source_column}' not found in "
                f"the stored RAG result. Available columns: {columns}. "
                f"Please retry asset_db_rag_tool and make sure its SQL query "
                f"includes the identifier column you need (e.g. iid)."
            )

        col_idx = columns.index(actual_col)
        values = list({row[col_idx] for row in rows if row[col_idx] is not None})
        logger.info(f"[DATA_REF] Resolved {len(values)} values for '{target_arg}' from column '{actual_col}'")
        tool_args[target_arg] = values


async def tool_runner(state: AgentState, runtime: Runtime[ctx_schema_State]):
    """
    Executes tools requested by the agent and handles output formatting for separate channels.
    """
    last_message = state.internal_messages[-1]
    
    # Ensure there are tool calls
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return Command(goto="loop_detector")
    
    # Check if there are multiple tool calls (only one is allowed)
    if len(last_message.tool_calls) > 1:
        dummy_tool_messages=[ToolMessage(content="Multiple tool calls are not allowed.", tool_call_id=tool_call["id"], name=tool_call["name"]) for tool_call in last_message.tool_calls]
        error_msg = f"Multiple tool calls detected ({len(last_message.tool_calls)}). Only one tool call is allowed at a time. Please call one tool at a time."
        return Command(goto="loop_detector", update={
            "internal_messages": state.internal_messages + dummy_tool_messages + [SystemMessage(content=error_msg)],
        })
    
    # Process only the first (0th) tool call
    tool_call = last_message.tool_calls[0]
    tool_name = tool_call["name"]
    tool_args = tool_call["args"].copy()
    tool_id = tool_call["id"]
    stream_writer = get_stream_writer()
    start_time = time.perf_counter()

    # Get user_email from runtime context
    user_email = getattr(runtime.context, "user_email", None)
    logger.info(f"[TOOL RUNNER] User email: {user_email or 'Not found'}")
    
    try:
        # Get the tool
        tool = tool_registry.get_tool(tool_name)
        
        # Inject state-backed context fields for tools that need them.
        if hasattr(tool, 'coroutine') and tool.coroutine:
            tool_func = tool.coroutine
        elif hasattr(tool, 'func') and tool.func:
            tool_func = tool.func
        else:
            tool_func = tool
        sig = inspect.signature(tool_func)
        if 'project_name' in sig.parameters and 'project_name' not in tool_args:
            if state.project_name:
                tool_args['project_name'] = state.project_name.strip()
        if 'thread_id' in sig.parameters and 'thread_id' not in tool_args:
            if state.thread_id:
                tool_args['thread_id'] = state.thread_id
        if 'user_email' in sig.parameters and 'user_email' not in tool_args:
            if user_email:
                tool_args['user_email'] = user_email

        # Resolve data_refs before tool execution — pops from args so the tool
        # never sees the field, only the resolved values in the target args.
        data_refs_raw = tool_args.pop("data_refs", None)
        if data_refs_raw:
            # LLMs sometimes emit data_refs as a JSON string instead of a list.
            if isinstance(data_refs_raw, str):
                try:
                    data_refs_raw = json.loads(data_refs_raw)
                except (json.JSONDecodeError, TypeError):
                    raise ValueError(f"data_refs is not valid JSON: {data_refs_raw!r}")
            if isinstance(data_refs_raw, list) and data_refs_raw:
                await _resolve_data_refs(data_refs_raw, tool_args, state.last_rag_result)

        # Execute the tool
        logger.info(f"[TOOL RUNNER] Executing tool: {tool_name}")
        logger.info(f"[TOOL RUNNER] Tool args: {tool_args}")
        logger.info(f"[TOOL RUNNER] Tool ID: {tool_id}")
        _emit_tool_runner_event(
            stream_writer,
            "tool_execution_started",
            tool_name=tool_name,
            tool_id=tool_id,
            tool_args=tool_args,
        )
        result = await tool.ainvoke(tool_args)
        
        # logger.info(f"[TOOL RUNNER] Result: {result.model_dump()}")
        
        # First check: if result is Command, return it directly
        if isinstance(result, Command):
            _emit_tool_runner_event(
                stream_writer,
                "tool_execution_command_returned",
                tool_name=tool_name,
                tool_id=tool_id,
                elapsed_ms=int((time.perf_counter() - start_time) * 1000),
            )
            return result
        
        # Second check: result must be ToolOutput type
        if not isinstance(result, ToolOutput):
            raise TypeError(f"Tool '{tool_name}' must return ToolOutput type, got {type(result)}")
        
        # Handle ToolOutput based on status
        if not result.status or result.errors is not None:
            # Status is false: return AIMessage with errors
            error_content = result.errors or "Tool execution failed"
            error_msg =  f"Tool '{tool_name}' failed: {error_content}"
            error_msg_ui = format_tool_error_ui(tool_name, str(error_content), maximum_size=MAXIMUM_TOOL_RESULT_SIZE)
            _emit_tool_runner_event(
                stream_writer,
                "tool_execution_failed",
                tool_name=tool_name,
                tool_id=tool_id,
                error=str(error_content),
                elapsed_ms=int((time.perf_counter() - start_time) * 1000),
            )

            
            error_tool_msg_internal = ToolMessage(content=error_msg, tool_call_id=tool_id, name=tool_name)
            error_tool_msg_ui = ToolMessage(content=error_msg_ui, tool_call_id=tool_id, name=tool_name)

            ai_tool_call_ui = AIMessage(content="", tool_calls=last_message.tool_calls)
            ai_tool_call_ui.name = "db_agent"

            return Command(goto="loop_detector", update={
                "internal_messages": state.internal_messages + [error_tool_msg_internal],
                "ui_messages": state.ui_messages + [ai_tool_call_ui, error_tool_msg_ui]
            })
        
        # Status is true: push data to internal message and md_data to ui message
        internal_content = result.data or ""

        # Create messages
        ui_content = result.md_data or ""
        ui_artifact = json.dumps(result.extra) if result.extra else None
        ui_msg = ToolMessage(content=ui_content, tool_call_id=tool_id, name=tool_name, artifact=ui_artifact)

        
        effective_max = MAXIMUM_TOOL_RESULT_SIZE * 3 if tool_name == "doc_retrieval_tool" else MAXIMUM_TOOL_RESULT_SIZE
        if len(internal_content) > effective_max:
            internal_content = internal_content[:effective_max] + "\nTRUNCATED DUE TO HUGE TOOL OUTPUT SIZE"

        internal_msg = ToolMessage(content=internal_content, tool_call_id=tool_id, name=tool_name)

        # Build the AI tool-call message for UI (executor no longer adds it,
        # so we add it here only when the tool actually executes).
        ai_tool_call_ui = AIMessage(content="", tool_calls=last_message.tool_calls)
        ai_tool_call_ui.name = "db_agent"

        state_update = {
            "internal_messages": state.internal_messages + [internal_msg],
            "ui_messages": state.ui_messages + [ai_tool_call_ui, ui_msg],
        }

        # When asset_db_rag_tool succeeds, persist the full result so
        # dependent tools can resolve data_refs from it without re-executing SQL.
        if tool_name == "asset_db_rag_tool" and result.data:
            rag_stored = False
            try:
                json_match = re.search(r'\*\*Data returned:\*\*\n(.+)', result.data, re.DOTALL)
                if json_match:
                    rag_data = json.loads(json_match.group(1))
                    state_update["last_rag_result"] = {
                        "columns": rag_data.get("columns", []),
                        "rows": rag_data.get("rows", []),
                    }
                    rag_stored = True
                    logger.info(
                        f"[TOOL RUNNER] Stored last_rag_result: "
                        f"{len(rag_data.get('columns', []))} columns, "
                        f"{len(rag_data.get('rows', []))} rows"
                    )
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning(f"[TOOL RUNNER] Failed to parse RAG data for state storage: {e}")

            if not rag_stored:
                parse_hint = (
                    "\n\n[SYSTEM WARNING] Failed to store query result for dependent tool chaining. "
                    "If you need to chain a dependent tool next, please retry this asset_db_rag_tool call."
                )
                internal_msg = ToolMessage(
                    content=internal_content + parse_hint,
                    tool_call_id=tool_id,
                    name=tool_name,
                )
                state_update["internal_messages"] = state.internal_messages + [internal_msg]

            # --- Guard: prevent executor from re-calling RAG after success ---
            # Qwen/Gemini models often treat 0-row results as failure and retry.
            # Inject a system instruction so the executor knows RAG is done.
            # rag_guard_msg = SystemMessage(
            #     content=(
            #         "[SYSTEM] asset_db_rag_tool has completed successfully. "
            #         "Present the result to the user as your Final Answer now. "
            #         "If the result has 0 rows, that IS the answer — the data does not exist in the database. "
            #         "Do NOT call asset_db_rag_tool again. "
            #         "You MAY proceed to audit_engine_tool or discrepancy_engine_tool ONLY if the user's original request requires it."
            #     )
            # )
            # state_update["internal_messages"] = state_update["internal_messages"] + [rag_guard_msg]

        _emit_tool_runner_event(
            stream_writer,
            "tool_execution_succeeded",
            tool_name=tool_name,
            tool_id=tool_id,
            elapsed_ms=int((time.perf_counter() - start_time) * 1000),
        )
        return Command(goto="loop_detector", update=state_update)
            
    except GraphInterrupt:
        #Let LangGraph interrupt propagate — do NOT swallow it.
        #This is raised by interrupt() inside tools (e.g. human-in-the-loop approval).
        logger.error(f"[TOOL RUNNER] GraphInterrupt Occured")
        _emit_tool_runner_event(
            stream_writer,
            "tool_execution_interrupted",
            tool_name=tool_name,
            tool_id=tool_id,
            elapsed_ms=int((time.perf_counter() - start_time) * 1000),
        )
        raise

    except Exception as e:
        
        error_msg = f"Error executing tool '{tool_name}': {str(e)}"

        # Prefer a readable, concrete error (and include exception type).
        # We avoid sending full tracebacks to the UI, but we do want the real message.
        exc_only = "".join(traceback.format_exception_only(type(e), e)).strip()
        if not exc_only:
            exc_only = str(e) or "Tool execution failed"
        error_msg_ui = format_tool_error_ui(tool_name, exc_only, maximum_size=MAXIMUM_TOOL_RESULT_SIZE)
        _emit_tool_runner_event(
            stream_writer,
            "tool_execution_exception",
            tool_name=tool_name,
            tool_id=tool_id,
            error=exc_only,
            elapsed_ms=int((time.perf_counter() - start_time) * 1000),
        )

      
        # Create error messages
        error_tool_msg_internal = ToolMessage(content=error_msg, tool_call_id=tool_id, name=tool_name)
        error_tool_msg_ui = ToolMessage(content=error_msg_ui, tool_call_id=tool_id, name=tool_name)

        ai_tool_call_ui = AIMessage(content="", tool_calls=last_message.tool_calls)
        ai_tool_call_ui.name = "db_agent"

        return Command(goto="loop_detector", update={
            "internal_messages": state.internal_messages + [error_tool_msg_internal],
            "ui_messages": state.ui_messages + [ai_tool_call_ui, error_tool_msg_ui]
        })
