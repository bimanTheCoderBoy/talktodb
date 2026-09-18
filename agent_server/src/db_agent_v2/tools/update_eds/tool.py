import asyncio
import logging
import datetime
import json
import uuid
from pathlib import Path
from typing import Any, Annotated, Dict, List, Optional, Tuple
from collections import defaultdict
import aiofiles
import aiofiles.os
import httpx


from db_agent_v2.state import AgentState, ctx_schema_State
from langgraph.runtime import Runtime
from langchain_core.messages import AIMessage, ToolMessage
from db_agent_v2.tools.asset_db_rag.DBRagPromptTemplate import FUZZY_IDENTIFIER
from db_agent_v2.tools.asset_db_rag.tool import AssetDBRAGTool, _convert_datetime_to_str
from db_agent_v2.tools.update_eds.EDSPromptTemplate import SYSTEM_PROMPT
from db_agent_v2.tools.update_eds.config.eds_config import get_eds_api_config, get_eds_tool_config, get_eds_mapping_config, DB_TO_OSS_COLUMN_MAP
from db_agent_v2.db.DatabaseManager import DynamicAsyncDatabaseManager, global_db_manager
from db_agent_v2.tools.base import ToolOutput
from security.encryption.iid_hash_utils import (
    HASHING_ENABLED as IID_HASHING_ENABLED,
    collect_hashes_from_rows,
    apply_reverse_map,
    reverse_map_hashes,
)
from db_agent_v2.config.agent_config import MAXIMUM_TOOL_RESULT_SIZE
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool, InjectedToolArg
from langgraph.config import get_stream_writer
from langgraph.types import Command, interrupt, StreamWriter
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class UpdateEDSTool:
    """
    Encapsulates all logic for building EDS payloads, sending them to the
    EDS API, and updating Asset Database after a successful EDS update.
    """

    TABLE_BY_TECH = {
        "LTE": "cell_lte",
        "NR": "cell_nr",
    }

    def __init__(
        self,
        db_manager: Optional[DynamicAsyncDatabaseManager] = None,
    ):
        self.db_manager = db_manager or global_db_manager
        self.asset_db_rag_tool = AssetDBRAGTool(
            db_manager=self.db_manager, system_prompt=SYSTEM_PROMPT
        )
        self._mapping_path = get_eds_mapping_config().mapping_db_eds_path
        self._data_payload_dir = Path(get_eds_mapping_config().saved_data_payload_dir)
        self._mapping_cache: Optional[Dict[str, Any]] = None


    def build_approval_message(self, data:str) -> str:
        """
        Build a human-readable approval message summarising the pending changes.
        """
        
        message = (

            "This operation will make **PERMANENT CHANGES** in:\n"
            "- **EDS** (Network configuration)\n"
            "- **ASSET DB** (Database)\n\n"
            f"**Affected Items** \n{data}\n\n"
            "Do you **approve** this change? (yes / no)"
        )
        return message

  

    async def _load_mapping(self) -> Dict[str, Any]:
        """Load and cache mapping_db_eds.json (async, non-blocking)."""
        if self._mapping_cache is None:
            async with aiofiles.open(self._mapping_path, "r") as f:
                content = await f.read()
            self._mapping_cache = json.loads(content)
        return self._mapping_cache

    @staticmethod
    def _apply_transform(value: Any, transform: str) -> Any:
        """Cast *value* according to the mapping's transform type."""
        if transform == "int":
            return int(value)
        if transform == "float":
            return float(value)
        if transform == "bool":
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        return str(value)

    @staticmethod
    def _set_nested(d: dict, dotted_path: str, value: Any) -> None:
        """
        Set a value in a nested dict using a dotted path.
        e.g. _set_nested(d, "lte.carrierParameters.maxTxPower", 43.0)
        results in d["lte"]["carrierParameters"]["maxTxPower"] = 43.0
        """
        keys = dotted_path.split(".")
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value

    @staticmethod
    def _deep_merge(base: dict, update: dict) -> dict:
        """Recursively merge *update* into *base* (returns new dict)."""
        result = base.copy()
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = UpdateEDSTool._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def _resolve_parameter(param_name: str, tech_section: dict) -> dict | None:
        """
        Look up *param_name* in the technology's updatable_columns.
        Returns the mapping rule dict (eds_path, transform, aliases) or None.
        Tries exact key match first, then checks aliases.
        """
        updatable = tech_section.get("updatable_columns", {})
        param_lower = param_name.lower()

        # Exact match on column key
        if param_lower in updatable:
            return updatable[param_lower]

        # Search by alias
        for _col_key, rule in updatable.items():
            if param_lower in [a.lower() for a in rule.get("aliases", [])]:
                return rule

        return None

    # ------------------------------------------------------------------
    # Payload builder  (long format only)
    # ------------------------------------------------------------------

    async def build_eds_payload(self, data: dict, project_name: str) -> dict:

        logger.info(f"Building EDS payload for project: {project_name}")
       
        mapping = await self._load_mapping()
        columns = data.get("columns", [])
        rows = data.get("rows", [])

        if not columns or not rows:
            logger.warning("No columns or rows in tool output — returning empty payload")
            return {"appData": []}

        # Resolve column indices from the long-format columns
        col_norm = [c.lower().replace(" ", "_") for c in columns]

        def _find_col(candidates: list[str]) -> int:
            """Return index of the first matching column name."""
            for name in candidates:
                if name in col_norm:
                    return col_norm.index(name)
            raise ValueError(
                f"Required column not found. Expected one of {candidates}, "
                f"got columns: {columns}"
            )

        idx_tech = _find_col(["technology", "technology_active"])
        idx_tech_fixed = _find_col(["technology_fixed"])
        idx_cell = _find_col(["cell_iid", "iid"])
        idx_param = _find_col(["parameter"])
        idx_new = _find_col(["new_value"])

        # Accumulate update fields per cell_iid
        cell_updates: Dict[str, dict] = {}

        for row in rows:
            technology_active = row[idx_tech]
            technology_fixed = row[idx_tech_fixed]
            cell_iid = row[idx_cell]
            param_name = row[idx_param]
            new_value = row[idx_new]

            # Pick the right tech section from the mapping
            tech_key = technology_active.lower()
            tech_section = mapping.get(tech_key)
            if tech_section is None:
                raise ValueError(f"Unsupported technology '{technology_active}' in mapping")

            # Resolve parameter to its mapping rule
            rule = self._resolve_parameter(param_name, tech_section)
            if rule is None:
                raise ValueError(
                    f"Parameter '{param_name}' not found in mapping for technology '{technology_active}'"
                )

            # Cast the value and build the nested structure
            casted_value = self._apply_transform(new_value, rule["transform"])
            update_fragment: dict = {}
            self._set_nested(update_fragment, rule["eds_path"], casted_value)

            # Merge into this cell's accumulated updates
            if cell_iid in cell_updates:
                cell_updates[cell_iid] = self._deep_merge(cell_updates[cell_iid], update_fragment)
            else:
                 cell_updates[cell_iid] = {
                                "technology": {
                                    "fixed": technology_fixed,
                                    "active": technology_active
                                },
                                **update_fragment
                            }

        # Build the appData list
        app_data = []
        for cell_iid, fields in cell_updates.items():
            # This we have to improve to make it more dynamic to all the Asset Object Types like Cellv214Type, Sitev214Type, etc.
            cell_obj = {
                "$type": "Cellv214Type",
                "allowedOperations": "ReadWrite",
                "iid": cell_iid,
                "bvid": project_name,
            }
            cell_obj = self._deep_merge(cell_obj, fields)
            app_data.append(cell_obj)

        payload = {"appData": app_data}
        logger.info("Built EDS payload with %d cell(s)", len(app_data))
        return payload


    async def _save_payload(
        self,
        payload: Dict[str, Any],
        save_dir: Path | str | None = None,
    ) -> str:
        """Save EDS payload to a JSON file for audit."""
        save_dir = Path(save_dir) if save_dir else self._data_payload_dir
        save_dir = Path(save_dir)  # ensure Path even if _data_payload_dir is str
        await aiofiles.os.makedirs(save_dir, exist_ok=True)

        cell_iids: List[str] = [
            item.get("iid", "unknown") for item in payload.get("appData", [])
        ]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if len(cell_iids) <= 3:
            cells_str = "_".join(cell_iids)
            filename = f"update_{cells_str}_{timestamp}.json"
        else:
            filename = f"update_{len(cell_iids)}_cells_{timestamp}.json"

        filepath = save_dir / filename

        try:
            async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
                await f.write(json.dumps(payload, indent=2, ensure_ascii=False))
            logger.info("⚡Saved payload to %s", filepath)
            return str(filepath)
        except Exception as e:
            logger.error("Failed to save payload: %s", e)
            return ""

    async def _send_eds_update(
        self,
        payload: Dict[str, Any],
        object_type: str = "Cellv214Type",
        stream_writer=None,
    ) -> Dict[str, Any]:
        """Send a single EDS update via HTTP PUT with retry on transient failures."""
        api_config = get_eds_api_config()
        url = f"{api_config.eds_update_url}/{object_type}"
        headers = {
            "Content-Type": "application/json",
            "api-key": api_config.api_key,
        }
        max_retries = api_config.max_retries
        last_exception: Optional[Exception] = None

        for attempt in range(1, max_retries + 2):
            try:
                async with httpx.AsyncClient(timeout=api_config.timeout) as client:
                    response = await client.put(url, json=payload, headers=headers)

                if response.status_code >= 500 and attempt <= max_retries:
                    logger.warning(
                        "EDS API 5xx (attempt %d/%d), status=%s, retrying...",
                        attempt, max_retries + 1, response.status_code,
                    )
                    if stream_writer:
                        stream_writer({"status": "retrying", "message": f"EDS API returned {response.status_code}, retry {attempt}/{max_retries}..."})
                    await asyncio.sleep(2 * attempt)
                    continue

                if response.status_code >= 400:
                    logger.error(
                        "EDS API error: status=%s, body=%s",
                        response.status_code,
                        response.text,
                    )
                    raise httpx.HTTPStatusError(
                        f"EDS API Error: Status {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                result = response.json()
                logger.info("EDS API response: %s", result)
                return result

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exception = e
                if attempt <= max_retries:
                    logger.warning(
                        "EDS API timeout/connect error (attempt %d/%d): %s, retrying...",
                        attempt, max_retries + 1, e,
                    )
                    if stream_writer:
                        stream_writer({"status": "retrying", "message": f"EDS API timed out, retry {attempt}/{max_retries}..."})
                    await asyncio.sleep(2 * attempt)
                    continue
                raise

        raise last_exception

    async def send_eds_update_batched(
        self,
        payload: Dict[str, Any],
        object_type: str = "Cellv214Type",
        save_dir: Path | str | None = None,
        stream_writer=None,
    ) -> Dict[str, Any]:
        """Send EDS update in batches of max_batch_size (default 100)."""
        tool_config = get_eds_tool_config()
        max_batch_size = tool_config.max_batch_size

        app_data = payload.get("appData", [])
        total_cells = len(app_data)
        total_batches = (total_cells + max_batch_size - 1) // max_batch_size

        logger.info(
            "Processing %d cell(s) in %d batch(es) of max %d",
            total_cells, total_batches, max_batch_size,
        )

        num_updated = 0
        saved_files: List[str] = []
        last_response: Dict[str, Any] = {"code": "OK", "message": "Batch processing completed"}
        error: str | None = None

        for i in range(0, total_cells, max_batch_size):
            batch_num = i // max_batch_size + 1
            batch_app_data = app_data[i : i + max_batch_size]
            batch_payload = {"appData": batch_app_data}

            logger.info(
                "Batch %d/%d: cells %d to %d (%d cells)",
                batch_num, total_batches,
                i + 1, min(i + max_batch_size, total_cells),
                len(batch_app_data),
            )

            # Save batch payload for audit
            saved = await self._save_payload(batch_payload, save_dir)
            if saved:
                saved_files.append(saved)

            # Send batch to EDS API
            try:
                response = await self._send_eds_update(batch_payload, object_type, stream_writer)

                if response.get("code") != "OK":
                    error = (
                        f"Batch {batch_num}/{total_batches} failed: "
                        f"code={response.get('code')}, status={response.get('status', 'Unknown')}"
                    )
                    logger.error(error)
                    last_response = response
                    break
                

                num_updated += len(batch_app_data)
                last_response = response
                logger.info(
                    "Batch %d/%d succeeded: %d cells updated",
                    batch_num, total_batches, len(batch_app_data),
                )

            except Exception as e:
                error = f"Batch {batch_num}/{total_batches} exception: {e}"
                logger.error(error)
                break

        logger.info(
            "Update workflow completed: %d/%d cell(s) updated across %d batch(es)",
            num_updated, total_cells, total_batches,
        )

        return {
            "total_cells": total_cells,
            "cells_updated": num_updated,
            "total_batches": total_batches,
            "batches_succeeded": (
                num_updated // max_batch_size + (1 if num_updated % max_batch_size else 0)
                if num_updated else 0
            ),
            "saved_files": saved_files,
            "last_response": last_response,
            "error": error,
        }


    async def update_postgres_table(
        self,
        project_name: str,
        data: Dict[str, Any],
        user_email: str,
    ) -> Tuple[str, bool]:
        """
        Post-EDS-success hook: update Postgres tables with the new values.
        Groups rows by (table, column) and issues batch UPDATE statements.
        """
        logger.info("Postgres update hook called for project=%s", project_name)

        col_index = {name: idx for idx, name in enumerate(data["columns"])}

        required_cols = {"technology_active", "CELL_IID", "Parameter", "New Value"}
        missing = required_cols - col_index.keys()
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        grouped = defaultdict(list)

        for row in data["rows"]:
            technology = row[col_index["technology_active"]].upper()
            cell_iid = row[col_index["CELL_IID"]]
            column = row[col_index["Parameter"]]
            new_value = row[col_index["New Value"]]

            if technology not in self.TABLE_BY_TECH:
                raise ValueError(f"Unsupported technology: {technology}")

            table = self.TABLE_BY_TECH[technology]
            grouped[(table, column)].append((cell_iid, new_value))

        sql_statements = []

        for (table, column), updates in grouped.items():
            values_sql = ",\n        ".join(
                f"('{cell_iid}', {repr(new_value)})"
                for cell_iid, new_value in updates
            )

            sql = f"""
                UPDATE {table} AS t
                SET {column} = v.new_value
                FROM (
                    VALUES
                        {values_sql}
                ) AS v(cell_iid, new_value)
                WHERE t.cell_iid = v.cell_iid;
                """.strip()

            sql_statements.append(sql)

        query = "\n\n".join(sql_statements)
        logger.info("Postgres update hook query: %s", query)

        result = await self.db_manager.execute_query(project_name, query, user_email)
        status = bool(result.get("status"))
    
        if status:
            logger.info(
                "📊Postgres update hook successful (EDS succeeded)."
            )
            return query, True

        logger.error(
            "Postgres update hook failed (EDS succeeded): %s",
            result.get("error") or "Unknown database error",
        )
        return query, False   

    async def update_discrepancy_table(
        self,
        project_name: str,
        data: Dict[str, Any],
        user_email: str,
    ) -> Tuple[int, int, int]:
        """
        Post-EDS-success hook: reconcile the discrepancies table.

        For each updated (cell_name, parameter, new_value):
          1. Remap DB column name → OSS column name (what discrepancies.column_name stores).
          2. Find the discrepancy record with matching cell_name, column_name,
             technology, and status='MISMATCH'.
          3. If oss_value == new_value  → mark status = 'fixed'.
             If oss_value != new_value  → update db_value = new_value.

        Returns:
            (fixed_count, updated_count, skipped_count)
        """
        logger.info("Discrepancy reconciliation called for project=%s", project_name)

        db_to_oss = DB_TO_OSS_COLUMN_MAP
        col_index = {name: idx for idx, name in enumerate(data["columns"])}

        required = {"technology_active", "CELL_IID", "Parameter", "New Value"}
        missing = required - col_index.keys()
        if missing:
            raise ValueError(f"Missing required columns for discrepancy update: {missing}")

        fix_queries: List[Tuple[str, Tuple[Any, ...]]] = []
        update_queries: List[Tuple[str, Tuple[Any, ...]]] = []
        skipped = 0

        for row in data["rows"]:
            technology = row[col_index["technology_active"]].upper()
            cell_name = row[col_index["CELL_IID"]]
            db_column = row[col_index["Parameter"]].lower()
            new_value = str(row[col_index["New Value"]])

            tech_map = db_to_oss.get(technology, {})
            oss_column_name = tech_map.get(db_column)

            if not oss_column_name:
                logger.warning(
                    "No DB→OSS column mapping for %s (tech=%s), skipping discrepancy reconciliation",
                    db_column, technology,
                )
                skipped += 1
                continue

            select_query = (
                "SELECT id, oss_value FROM discrepancies "
                "WHERE cell_name = $1 AND column_name = $2 "
                "AND LOWER(status) = 'mismatch' AND LOWER(technology) = LOWER($3) "
                "ORDER BY imported_at DESC LIMIT 1"
            )
            result = await self.db_manager.execute_query(
                project_name, select_query, user_email,
                params=(cell_name, oss_column_name, technology),
            )

            rows_found = result.get("data", [])
            if not rows_found:
                skipped += 1
                continue

            disc_row = rows_found[0]
            disc_id = disc_row["id"]
            oss_value = str(disc_row["oss_value"]) if disc_row["oss_value"] is not None else None

            if oss_value == new_value:
                fix_queries.append((
                    "UPDATE discrepancies SET status = 'FIXED' WHERE id = $1",
                    (disc_id,),
                ))
            else:
                update_queries.append((
                    "UPDATE discrepancies SET db_value = $1 WHERE id = $2",
                    (new_value, disc_id),
                ))

        all_queries = fix_queries + update_queries
        fixed_count = len(fix_queries)
        updated_count = len(update_queries)

        if all_queries:
            bulk_result = await self.db_manager.execute_bulk_queries(
                project_name=project_name,
                queries=all_queries,
                user_email=user_email,
                use_transaction=True,
            )
            logger.info(
                "Discrepancy reconciliation done: %d fixed, %d db_value updated, %d skipped, bulk_status=%s",
                fixed_count, updated_count, skipped, bulk_result.get("status"),
            )
        else:
            logger.info(
                "Discrepancy reconciliation: no matching mismatch records found (%d skipped)", skipped
            )

        return fixed_count, updated_count, skipped


# ═══════════════════════════════════════════════════════════════════════════
# Helper Node (phase machine)
# ═══════════════════════════════════════════════════════════════════════════

async def update_eds_tool_helper(state: AgentState, runtime: Runtime[ctx_schema_State]):
    """Phase-machine helper node for Update EDS with replay-safe interrupt."""
    logger.info("[UPDATE EDS TOOL HELPER] Entered")

    # Recover tool_call_id and tool_name from last message
    last_msg = state.internal_messages[-1] if state.internal_messages else None
    tool_call: Dict[str, Any] = {}
    if last_msg and hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        tool_call = last_msg.tool_calls[0]
    tool_id = tool_call.get("id", str(uuid.uuid4()))
    tool_name = tool_call.get("name", "update_eds_tool")

    # Helper to build final Command with ToolMessage and clear interrupt_data
    def _finish(output: ToolOutput) -> Command:
        if (not output.status) or output.errors:
            err = output.errors or "Tool execution failed"
            internal_msg = ToolMessage(content=f"Tool '{tool_name}' failed: {err}", tool_call_id=tool_id, name=tool_name)
            ui_msg = ToolMessage(content=f"**Calling `{tool_name}` failed**\n{err}\n\n", tool_call_id=tool_id, name=tool_name)
        else:
            content = output.data or ""
            if len(content) > MAXIMUM_TOOL_RESULT_SIZE:
                content = content[:MAXIMUM_TOOL_RESULT_SIZE] + "\n(truncated)"
            internal_msg = ToolMessage(content=content, tool_call_id=tool_id, name=tool_name)
            ui_msg = ToolMessage(content=output.md_data or "", tool_call_id=tool_id, name=tool_name)
        return Command(
            goto="loop_detector",
            update={
                "internal_messages": state.internal_messages + [internal_msg],
                "ui_messages": state.ui_messages + [ui_msg],
                "interrupt_data": None,
            },
        )

    # Read interrupt_data
    update_data = (state.interrupt_data or {}).get("update_eds", {})
    phase = update_data.get("phase", "init")
    args = update_data.get("args", {})
    stored_thread_id = update_data.get("thread_id")

    # Guard: if thread_id mismatch, reset to init
    if phase != "init":
        if stored_thread_id != state.thread_id:
            logger.warning("[UPDATE EDS TOOL HELPER] thread_id mismatch — resetting to init")
            phase = "init"

    update_eds = UpdateEDSTool(db_manager=global_db_manager)
    stream_writer: StreamWriter = get_stream_writer()

    # Extract args
    task = args.get("task", "")
    project_name = args.get("project_name") or state.project_name
    user_email = getattr(runtime.context, "user_email", None) or args.get("user_email")

    # ─── Phase: done / cancelled ───
    if phase in ("done", "cancelled"):
        logger.info(f"[UPDATE EDS TOOL HELPER] Already {phase}, returning cached result")
        cached = update_data.get("result", {})
        
        return _finish(ToolOutput(**cached) if cached else ToolOutput(status=True, data="(no cached result)"))

    # ─── Phase: init ───
    if phase == "init":
        logger.info("🚀Starting Update EDS tool (init phase)...")

        query_executed = None
        try:
            wrapped_task = f"Make a update preview for the following network configuration change intention: '{task}'"
            logger.info(f"[UPDATE EDS TOOL] Task: {task}")
            result, query_executed = await update_eds.asset_db_rag_tool.generate_and_execute_sql_query(
                wrapped_task, True, project_name, user_email, stream_writer=stream_writer
            )
        except Exception as e:
            query_md = (
                "**Query executed:**\n\n```sql\n"
                + (query_executed or "N/A")
                + "\n```\n\n"
            )
            return _finish(ToolOutput(
                status=False,
                data=json.dumps({"error": str(e)}),
                md_data=query_md + f"**Error Executing Query**\n\n{e}",
                errors=str(e),
            ))

        logger.info(f"[UPDATE EDS TOOL] DB RAG Tool Result: {result.model_dump()}")
        logger.info(f"[UPDATE EDS TOOL] Query Executed: {query_executed}")

        result_dict = result.model_dump()
        logger.info(f"[EDS-DEBUG] result_dict keys: {list(result_dict.keys())}, count={result_dict.get('count')}, status={result_dict.get('status')}, fuzzy_flag={result_dict.get('fuzzy_flag')}, error={result_dict.get('error')}")
        logger.info(f"[EDS-DEBUG] result_dict data count: {len(result_dict.get('data') or [])}, columns: {result_dict.get('columns')}")

        # Reverse-map hashed IIDs — needed for both display AND EDS API payload
        if IID_HASHING_ENABLED and result_dict.get("data"):
            hashes = collect_hashes_from_rows(result_dict["data"])
            if hashes:
                async with global_db_manager.connection(project_name) as conn:
                    rmap = await reverse_map_hashes(conn, hashes)
                if rmap:
                    apply_reverse_map(result_dict["data"], rmap)

        columns, rows, markdown_data = await DynamicAsyncDatabaseManager.get_formatted_result(result_dict)
        markdown_data = markdown_data or ""
        data = {"columns": columns, "rows": rows}
        data = _convert_datetime_to_str(data)

        logger.info(f"[EDS-DEBUG] After formatting: columns={columns}, rows_count={len(rows)}, first_row={rows[0] if rows else 'EMPTY'}")

        if not result.status:
            logger.info(f"[EDS-DEBUG] NO SUCCESS -> returning error. fuzzy_flag was {result.fuzzy_flag}")
            error_msg = (
                f"SQL query generation failed for the update request. "
                f"Error: {result.error}. "
            )
            return _finish(ToolOutput(
                status=False,
                data=json.dumps(data),
                md_data=markdown_data,
                errors=error_msg,
            ))

        # Handle fuzzy results — retbburn suggestions, don't proceed with update
        if result.fuzzy_flag:
            data["fuzzy_notice"] = FUZZY_IDENTIFIER
            logger.info("[EDS-DEBUG] FUZZY FLAG IS TRUE -> returning suggestions, NOT proceeding with update")
            return _finish(ToolOutput(
                status=True,
                data=json.dumps(data),
                is_summary_available=False,
                md_data=markdown_data,
                errors=None,
            ))

        if not data or not data.get("rows"):
            logger.info(f"[EDS-DEBUG] NO ROWS -> returning error. fuzzy_flag was {result.fuzzy_flag}")
            error_msg = (
                f"No matching cells found for the update request. "
                f"The SQL query returned 0 rows. "
                f"Query: {query_executed}. "
                f"Please verify the site/cell name, technology, and parameter are correct."
            )
            return _finish(ToolOutput(
                status=False,
                data=json.dumps(data),
                md_data=markdown_data,
                errors=error_msg,
            ))

        try:
            eds_payload = await update_eds.build_eds_payload(data, project_name)
        except ValueError as e:
            logger.error("Payload build failed: %s", e)
            return _finish(ToolOutput(
                status=False,
                data=json.dumps(data),
                md_data=markdown_data,
                errors=str(e),
            ))

        if not eds_payload.get("appData"):
            logger.warning("Update EDS Tool: payload appData is empty after build")
            return _finish(ToolOutput(
                status=False,
                data=json.dumps(data),
                md_data=markdown_data,
                errors="Payload construction resulted in 0 cells.",
            ))

        logger.info("EDS payload: %d cell(s)", len(eds_payload.get("appData", [])))

        # Persist plan and transition to ready_for_approval
        new_data = {
            "update_eds": {
                "thread_id": state.thread_id,
                "phase": "ready_for_approval",
                "args": args,
                "plan": {
                    "query_executed": query_executed,
                    "markdown_data": markdown_data,
                    "data": data,
                    "eds_payload": eds_payload,
                },
            }
        }
        return Command(goto="update_eds_tool_helper", update={"interrupt_data": new_data})

    # ─── Phase: ready_for_approval ───
    if phase == "ready_for_approval":
        plan = update_data.get("plan", {})
        markdown_data = plan.get("markdown_data", "")

        approval_message = update_eds.build_approval_message(markdown_data)
        user_response = interrupt({"type": "ASK_HUMAN_BINARY", "content": approval_message})

        if not user_response:
            out = ToolOutput(
                status=False,
                data=json.dumps({"cancelled": True, "cancelled_reason": "User denied the change. No update executed"}),
                md_data="\n\n**User denied the change. No update executed.**",
                errors="**User Have Denied the Change. No update executed.**",
            )
            new_data = {
                "update_eds": {
                    **update_data,
                    "phase": "cancelled",
                    "result": out.model_dump(),
                }
            }
            return Command(goto="update_eds_tool_helper", update={"interrupt_data": new_data})

        # Approved — transition to approved phase
        new_data = {
            "update_eds": {
                **update_data,
                "phase": "approved",
            }
        }
        return Command(goto="update_eds_tool_helper", update={"interrupt_data": new_data})

    # ─── Phase: approved ───
    if phase == "approved":
        logger.info("User approved the EDS and Asset DB update — proceeding")
        plan = update_data.get("plan", {})
        query_executed = plan.get("query_executed")
        markdown_data = plan.get("markdown_data", "")
        data = plan.get("data", {})
        eds_payload = plan.get("eds_payload", {})

        # Step 3: Save each batch & send to EDS API
        try:
            batch_result = await update_eds.send_eds_update_batched(eds_payload, stream_writer=stream_writer)
        except Exception as e:
            logger.error("EDS batch update failed: %s", e)
            out = ToolOutput(
                status=False,
                data=json.dumps({"payload": eds_payload}),
                md_data=markdown_data,
                errors=f"EDS API call failed: {e}",
            )
            new_data = {"update_eds": {**update_data, "phase": "done", "result": out.model_dump()}}
            return Command(goto="update_eds_tool_helper", update={"interrupt_data": new_data})

        # Check if all batches succeeded
        if batch_result.get("error"):
            out = ToolOutput(
                status=False,
                data=json.dumps({"payload": eds_payload, "batch_result": batch_result}),
                md_data=markdown_data,
                errors=batch_result["error"],
            )
            new_data = {"update_eds": {**update_data, "phase": "done", "result": out.model_dump()}}
            return Command(goto="update_eds_tool_helper", update={"interrupt_data": new_data})

        # Step 4: Only after EDS upload succeeds, update Postgres tables
        update_query = query_executed or ""
        if update_eds.db_manager is not None:
            try:
                update_query, update_status = await update_eds.update_postgres_table(
                    project_name=project_name,
                    data=data,
                    user_email=user_email,
                )
            except Exception as e:
                logger.error("Postgres update hook failed (EDS succeeded): %s", e)

            # Step 5: Reconcile discrepancy table
            try:
                fixed, updated, skipped = await update_eds.update_discrepancy_table(
                    project_name=project_name,
                    data=data,
                    user_email=user_email,
                )
                logger.info(
                    "Discrepancy reconciliation: %d fixed, %d updated, %d skipped",
                    fixed, updated, skipped,
                )
            except Exception as e:
                logger.error("Discrepancy reconciliation failed (EDS+Postgres succeeded): %s", e)

        final_markdown = f"**Query executed:**\n\n```sql\n{update_query}\n```\n\n{markdown_data}"

        out = ToolOutput(
            status=True,
            data=json.dumps({"payload": eds_payload, "batch_result": batch_result}),
            md_data=final_markdown,
            errors=None,
        )
        new_data = {"update_eds": {**update_data, "phase": "done", "result": out.model_dump()}}
        return Command(goto="update_eds_tool_helper", update={"interrupt_data": new_data})

    # Fallback — unknown phase
    logger.warning(f"[UPDATE EDS TOOL HELPER] Unknown phase '{phase}', resetting")
    return _finish(ToolOutput(status=False, errors=f"Unknown phase '{phase}'"))


# ═══════════════════════════════════════════════════════════════════════════
# Tool Factory (router)
# ═══════════════════════════════════════════════════════════════════════════

def create_update_eds_tool(
    db_manager: Optional[DynamicAsyncDatabaseManager] = global_db_manager,
):
    
    class UpdateEdsArgs(BaseModel):
        task: str = Field(...,description="Natural-language description of the update to perform. Include target cells/sites, parameter name, and new value, or any conditions to fetch the target cells/sites. E.g. 'Set TAC to 44 for all LTE cells in Jesery_Site_1', 'update tac to 50 NR for all cells in London', 'Update TAC to 50 for all cells whose azimuth is 0', etc.")

    @tool("update_eds_tool", args_schema=UpdateEdsArgs, parse_docstring=False)
    async def update_eds_tool(
        task: str,  
        project_name: Annotated[str, InjectedState("project_name")],
        user_email: Annotated[str, InjectedToolArg],
        thread_id: Annotated[Optional[str], InjectedState("thread_id")] = None,
    ) -> Command:
        """
        Update cell configuration parameters in the EDS system by constructing and submitting
        validated update payloads and finally update the ASSET DB by executing an UPDATE query.

        This tool is responsible for applying configuration changes to network Parameters(cells)
        via the EDS API and updating the same in the Asset Database.

        The tool performs the following high-level steps:
        1. Fetches current cell identifiers and parameter values based on the task conditions and intent using the Asset DB (read-only).
        2. Constructs a deterministic EDS-compatible payload based on user intent and mappings.
        3. Submits the payload to the EDS API to apply the requested updates.
        4. Update the Asset Database with the new data that user provided.

        ### *IMPORTANT* How to build <task> arg for it:
        - When giving a <task> arg, Must give the whole context clearly, It does not have access to previous context so it should be a complete task description about the update to be performed.
          - Example: 
                User: "tell me cells with tac 50"
                ...|other tool call|
                User: "update above cells with tac 5"
                Here, the <task> arg should be "update cells with tac 50 to 5" not "update above cells with tac 5".

        - The Tool accepts specific cell/site or any other conditions to fetch the target cells/sites as elements of the task.
          - so for user queries like 'update tac to 50 NR for all cells in London', don't need to call asset_db_rag_tool first to fetch the cells in London, just give the task as it is.
        
        When to use:
            - When the user explicitly asks to update, modify, set, enable, or disable
            one or more network parameters(cells).
            - When the user specifies target cells using cell name (iid), site name,
            region, or any supported parameters.
            - When changes must be applied to the EDS system and the asset DB.
            - Multi-cell updates derived from site, region, or pattern-based selection.
            - Batch updates where the same parameter/value applies to multiple cells.
        """
        args = {
            "task": task,
            "project_name": project_name,
            "user_email": user_email,
        }

        return Command(
            goto="update_eds_tool_helper",
            update={
                "interrupt_data": {
                    "update_eds": {
                        "thread_id": thread_id,
                        "phase": "init",
                        "args": args,
                    }
                }
            },
        )

    return update_eds_tool
