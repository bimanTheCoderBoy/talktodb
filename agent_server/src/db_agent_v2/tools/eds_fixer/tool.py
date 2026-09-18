import asyncio
import os
import json
import logging
import re
import hashlib
import uuid
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import httpx
import aiofiles
import aiofiles.os
from langchain_core.tools import tool, InjectedToolArg
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from typing import Annotated
from langgraph.config import get_stream_writer
from langgraph.types import StreamWriter, interrupt, Command
from db_agent_v2.config.tool_config import EDSFixerToolConfig, DiscrepancyColumnAliases
from db_agent_v2.config.agent_config import MAXIMUM_TOOL_RESULT_SIZE
from db_agent_v2.db.DatabaseManager import DynamicAsyncDatabaseManager, global_db_manager
from db_agent_v2.state import AgentState, ctx_schema_State
from langgraph.runtime import Runtime
from db_agent_v2.tools.base import ToolOutput
from db_agent_v2.tools.discrepancy_engine.tool import DiscrepancyEngine
from security.encryption.iid_hash_utils import (
    HASHING_ENABLED as IID_HASHING_ENABLED,
    collect_hashes_from_rows,
    apply_reverse_map,
    reverse_map_hashes,
)
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EDSFixer:
    """EDS Fixer with injected dependencies."""

    def __init__(
        self,
        config: Optional[EDSFixerToolConfig] = None,
        db_manager: Optional[DynamicAsyncDatabaseManager] = None,
        discrepancy_engine: Optional[DiscrepancyEngine] = None,
    ):
        self.config = config or EDSFixerToolConfig()
        self.db_manager = db_manager or global_db_manager
        self.discrepancy_engine = discrepancy_engine or DiscrepancyEngine(self.db_manager)
        self.aliases = self.config.discrepancy_aliases

        if self.db_manager is None:
            raise ValueError("Database manager is not initialized")

        self.json_export_folder = str(self.config.file_paths.get_json_export_path())

    # ── Approval helpers ───────────────────────────────────────────────

    def _build_approval_summary(
        self,
        discrepancy_count: int,
        json_payload: Dict[str, Any],
        sql_actions: List[Dict[str, Any]],
    ) -> str:
        """Human-readable approval message for the ASK_HUMAN_BINARY interrupt."""
        cell_count = len(json_payload.get("appData", []))
        max_batch = self.config.max_batch_size
        total_batches = (cell_count + max_batch - 1) // max_batch if cell_count else 0
        param_set: set = set()
        cell_sample: list = []
        for action in sql_actions:
            param_set.add(action.get("column_name", "unknown"))
            if action.get("cell_name") and action["cell_name"] not in cell_sample:
                cell_sample.append(action["cell_name"])

        params_str = ", ".join(sorted(param_set)) or "N/A"
        cells_preview = ", ".join(cell_sample[:5])
        if len(cell_sample) > 5:
            cells_preview += f" … and {len(cell_sample) - 5} more"

        return (
            f"**EDS Fixer — Approval Required**\n\n"
            f"The following changes are ready to be applied:\n\n"
            f"| Detail | Value |\n"
            f"|---|---|\n"
            f"| Discrepancies | {discrepancy_count} |\n"
            f"| Cells affected | {cell_count} |\n"
            f"| Batches | {total_batches} (max {max_batch} cells each) |\n"
            f"| Parameters | {params_str} |\n"
            f"| Cells | {cells_preview} |\n\n"
            f"**Actions:** Update EDS API + local PostgreSQL tables\n\n"
            f"Do you **approve** this fix?"
        )

    # ── Batch helpers ──────────────────────────────────────────────────

    @staticmethod
    def _make_batches(
        json_payload: Dict[str, Any],
        sql_actions: List[Dict[str, Any]],
        max_batch_size: int,
    ) -> List[Dict[str, Any]]:
        """Split payload and aligned SQL actions into deterministic batches."""
        app_data = json_payload.get("appData", [])
        if not app_data:
            return []

        actions_by_cell: Dict[str, List[Dict[str, Any]]] = {}
        for action in sql_actions:
            cn = action.get("cell_name", "")
            actions_by_cell.setdefault(cn, []).append(action)

        batches: List[Dict[str, Any]] = []
        for i in range(0, len(app_data), max_batch_size):
            chunk = app_data[i : i + max_batch_size]
            cell_names_in_chunk = {cell.get("iid", "") for cell in chunk}
            batch_sql = []
            for cn in cell_names_in_chunk:
                batch_sql.extend(actions_by_cell.get(cn, []))
            batches.append({
                "payload": {"appData": chunk},
                "sql_actions": batch_sql,
                "cell_names": cell_names_in_chunk,
            })
        return batches

    @staticmethod
    def _parse_binary_approval(user_response: Any) -> bool:
        """Deny-safe normalisation of the interrupt response to a strict boolean."""
        if isinstance(user_response, bool):
            return user_response
        if isinstance(user_response, str):
            return user_response.strip().lower() in (
                "true", "yes", "approve", "approved", "1", "y",
            )
        if isinstance(user_response, dict):
            v = user_response.get("approved")
            if isinstance(v, bool):
                return v
            content = str(user_response.get("content", "")).strip().lower()
            return content in ("true", "yes", "approve", "approved", "1", "y")
        return False

    # ── Value conversion helpers ───────────────────────────────────────

    @staticmethod
    def convert_to_int(value):
        """Safely convert a string or float to an integer."""
        if value is None or (isinstance(value, str) and value.lower() == 'nan'):
            return None
        try:
            if isinstance(value, str):
                match = re.search(r'(\d+)', str(value))
                if match:
                    return int(match.group(1))
            return int(float(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def convert_to_float(value):
        """Safely convert a string or float to a float."""
        if value is None or (isinstance(value, str) and value.lower() == 'nan'):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def convert_to_bool(value):
        """Safely convert a string to a boolean."""
        if isinstance(value, str):
            return value.lower() in ['true', '1', 'yes', 'on']
        return bool(value)

    @staticmethod
    def convert_value_by_type(value, value_type):
        """Convert value based on the specified type."""
        if value is None or (isinstance(value, str) and value.lower() == 'nan'):
            return None
        try:
            if value_type == "int":
                return EDSFixer.convert_to_int(value)
            elif value_type == "float":
                return EDSFixer.convert_to_float(value)
            elif value_type == "bool":
                return EDSFixer.convert_to_bool(value)
            elif value_type == "str":
                return str(value)
            else:
                return value
        except Exception:
            return None

    @staticmethod
    def set_nested_value(obj, path, value):
        """Set a nested value in an object using dot notation path."""
        keys = path.split('.')
        current = obj
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    # ── Technology helpers ─────────────────────────────────────────────

    def _get_technology_from_row(self, row: Dict[str, Any]) -> Optional[str]:
        """Extract technology from discrepancy row."""
        technology = row.get("technology") or row.get("Technology") or row.get("TECHNOLOGY")
        if technology:
            tech_upper = str(technology).upper().strip()
            if tech_upper in ("LTE", "4G", "4G LTE"):
                return "LTE"
            elif tech_upper in ("NR", "5G", "5G NR"):
                return "NR"
            return tech_upper
        return None

    def _get_table_name_for_technology(self, technology: Optional[str]) -> str:
        """Get the correct table name based on technology."""
        if not technology:
            return "cell_lte"
        tech_upper = technology.upper().strip()
        if tech_upper in ("NR", "5G", "5G NR"):
            return "cell_nr"
        return "cell_lte"

    # ── Column mapping helpers ─────────────────────────────────────────

    def _map_column_to_json(self, column_name, value, technology: Optional[str] = None) -> Tuple[Optional[str], Any]:
        """Map a column name to its JSON path and convert the value for EDS API."""
        eds_mappings = self.config.eds_column_mappings
        value_conversions = eds_mappings.value_conversions

        json_path = eds_mappings.get_eds_column_mapping(column_name, technology)
        if not json_path:
            logger.warning(f"No EDS mapping found for column: '{column_name}' (technology: {technology}).")
            return None, None

        value_type = value_conversions.get(column_name, "str")
        converted_value = self.convert_value_by_type(value, value_type)

        if converted_value is None:
            logger.warning(f"Failed to convert value '{value}' to type '{value_type}' for column '{column_name}'")
            return None, None

        return json_path, converted_value

    def _map_column_to_db(self, column_name, value, technology: Optional[str] = None) -> Tuple[Optional[str], Any]:
        """Map a column name to its DB column and convert the value for PostgreSQL."""
        db_mappings = self.config.column_mappings
        value_conversions = self.config.eds_column_mappings.value_conversions

        db_column = db_mappings.get_column_mapping(column_name, technology)
        if not db_column:
            logger.warning(f"No DB mapping found for column: {column_name} (technology: {technology})")
            return None, None

        value_type = value_conversions.get(column_name, "str")
        converted_value = self.convert_value_by_type(value, value_type)
        return db_column, converted_value

    # ── Heavy-build ────────────────────────────────────────────────────

    async def _build_payloads_and_queries(self, discrepancies: List[Dict[str, Any]], project_name: str, user_email: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Build JSON payload for API and SQL queries for DB update."""
        latest_discrepancies_json = {}
        sql_actions = []
        bvid = project_name

        # Fetch per-cell technology_fixed from DB so payload reflects actual cell state
        technology_fixed_map = await self._get_cell_technology_fixed_map(project_name, discrepancies, user_email)

        for row in discrepancies:
            cell_name = row.get(self.aliases.CELL_NAME)
            column_name = row.get(self.aliases.COLUMN_NAME)
            oss_value = row.get(self.aliases.OSS_VALUE)

            if not cell_name or not column_name:
                logger.warning(f"Skipping row with missing cell_name or column_name: {row}")
                continue

            technology = self._get_technology_from_row(row)
            table_name = self._get_table_name_for_technology(technology)

            if cell_name not in latest_discrepancies_json:
                latest_discrepancies_json[cell_name] = self.config.minimal_payload.get_minimal_cell_structure(
                    cell_name=cell_name, bvid=bvid, technology=technology or "LTE",
                )
                # Override technology.fixed with DB value when available
                if cell_name in technology_fixed_map:
                    if "technology" not in latest_discrepancies_json[cell_name]:
                        latest_discrepancies_json[cell_name]["technology"] = {}
                    latest_discrepancies_json[cell_name]["technology"]["fixed"] = technology_fixed_map[cell_name]
                    logger.debug(f"Set technology.fixed={technology_fixed_map[cell_name]} for cell {cell_name} from DB")

            json_path, json_value = self._map_column_to_json(column_name, oss_value, technology)
            if json_path and json_value is not None:
                try:
                    self.set_nested_value(latest_discrepancies_json[cell_name], json_path, json_value)
                    logger.debug(f"Successfully set {json_path} = {json_value} for cell {cell_name}")
                except Exception as e:
                    logger.error(f"Failed to set nested value {json_path} = {json_value} for cell {cell_name}: {e}")

            db_column, db_value = self._map_column_to_db(column_name, oss_value, technology)
            if db_column and db_value is not None:
                query = f"UPDATE {table_name} SET {db_column} = $1 WHERE iid = $2"
                sql_actions.append({
                    "query": query,
                    "params": (db_value, cell_name),
                    "cell_name": cell_name,
                    "column_name": column_name,
                    "technology": technology,
                    "table_name": table_name,
                    "original_row": row,
                })

        json_payload = {"appData": list(latest_discrepancies_json.values())} if latest_discrepancies_json else {}

        # Reverse-map hashed iid values in EDS API payload — API needs original IIDs
        if IID_HASHING_ENABLED and json_payload.get("appData"):
            iid_hashes = set()
            for cell_obj in json_payload["appData"]:
                if cell_obj.get("iid"):
                    iid_hashes.add(cell_obj["iid"])
            if iid_hashes:
                try:
                    async with self.db_manager.connection(project_name) as conn:
                        rmap = await reverse_map_hashes(conn, iid_hashes)
                    if rmap:
                        for cell_obj in json_payload["appData"]:
                            if cell_obj.get("iid") in rmap:
                                cell_obj["iid"] = rmap[cell_obj["iid"]]
                except Exception as e:
                    logger.warning(f"Failed to reverse-map EDS payload iids: {e}")

        return json_payload, sql_actions

    # ── EDS API / DB write helpers ─────────────────────────────────────

    async def _send_eds_batch(self, batch_payload: Dict[str, Any], batch_num: int, total_batches: int, stream_writer=None) -> Tuple[bool, str]:
        """Send a single batch payload to EDS API with retry on transient failures."""
        if not batch_payload or not batch_payload.get("appData"):
            return False, "Empty batch payload"

        url = f"{self.config.eds_api.api_base_url}{self.config.eds_api.get_update_types()[0]['api_endpoint']}"
        headers = self.config.eds_api.get_headers()
        max_retries = self.config.eds_api.max_retries

        try:
            await aiofiles.os.makedirs(self.json_export_folder, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to create export folder: {e}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"discrepancies_batch{batch_num}of{total_batches}_{timestamp}.json"
        json_path = os.path.join(self.json_export_folder, json_filename)

        try:
            async with aiofiles.open(json_path, 'w') as f:
                await f.write(json.dumps(batch_payload, indent=4))
            logger.info(f"Saved batch {batch_num}/{total_batches} payload to {json_path}")
        except Exception as e:
            logger.error(f"Failed to save batch JSON file: {e}")

        logger.info(f"Sending PUT batch {batch_num}/{total_batches} ({len(batch_payload['appData'])} cells) to: {url}")

        for attempt in range(1, max_retries + 2):
            try:
                timeout = httpx.Timeout(self.config.eds_api.timeout)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.put(url, headers=headers, json=batch_payload)

                if response.status_code >= 500 and attempt <= max_retries:
                    logger.warning(
                        f"Batch {batch_num}/{total_batches} got {response.status_code} (attempt {attempt}/{max_retries + 1}), retrying..."
                    )
                    if stream_writer:
                        stream_writer({"step": "4/5", "status": "retrying", "message": f"Batch {batch_num}/{total_batches} got {response.status_code}, retry {attempt}/{max_retries}..."})
                    await asyncio.sleep(2 * attempt)
                    continue

                response.raise_for_status()
                logger.info(f"Batch {batch_num}/{total_batches} API Success")
                return True, f"Batch {batch_num}/{total_batches} API Success: {response.status_code}"

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt <= max_retries:
                    logger.warning(
                        f"Batch {batch_num}/{total_batches} timeout/connect error (attempt {attempt}/{max_retries + 1}): {e}, retrying..."
                    )
                    if stream_writer:
                        stream_writer({"step": "4/5", "status": "retrying", "message": f"Batch {batch_num}/{total_batches} timed out, retry {attempt}/{max_retries}..."})
                    await asyncio.sleep(2 * attempt)
                    continue
                logger.error(f"Batch {batch_num}/{total_batches} EDS API Failed after {max_retries + 1} attempts: {e}")
                return False, f"Batch {batch_num}/{total_batches} failed: {e}"

            except Exception as e:
                logger.error(f"Batch {batch_num}/{total_batches} EDS API Failed: {e}")
                return False, f"Batch {batch_num}/{total_batches} failed: {e}"

        return False, f"Batch {batch_num}/{total_batches} failed after {max_retries + 1} attempts"

    async def _update_postgres(self, project_name: str, sql_actions: List[Dict[str, Any]], user_email: str) -> Tuple[bool, str, List[str]]:
        """Update PostgreSQL table."""
        queries = []
        for action in sql_actions:
            queries.append((action["query"], action["params"]))

        logger.info(f"[EDS FIXER] Updating PostgreSQL with {len(queries)} queries")

        result = await self.db_manager.execute_bulk_queries(
            project_name=project_name,
            queries=queries,
            user_email=user_email,
            use_transaction=True,
        )

        logger.info(f"[EDS FIXER] Result: {result}")
        logger.info(f"[EDS FIXER] Status: {result['status']}")
        logger.info(f"[EDS FIXER] Success Count: {result['success_count']}")
        logger.info(f"[EDS FIXER] Total Count: {result['total_count']}")
        logger.info(f"[EDS FIXER] Failed Queries: {result['failed_queries']}")
        logger.info(f"[EDS FIXER] Error: {result['error']}")

        if result["status"]:
            return True, f"Successfully updated {result['success_count']} records in PostgreSQL.", []

        failed_msgs = []
        for fail in result.get("failed_queries", []):
            if 'params' in fail:
                param_info = f"Params: {fail.get('params')}"
            elif 'params_batch_size' in fail:
                param_info = f"Batch Size: {fail.get('params_batch_size')}"
            else:
                param_info = "Params: Unknown"
            failed_msgs.append(f"{fail.get('query')} -- {param_info} -- Error: {fail.get('error')}")

        if result.get("error") and not failed_msgs:
            failed_msgs.append(f"Transaction failed: {result.get('error')}")

        return False, f"Updated {result['success_count']}/{len(sql_actions)} records. Some updates failed.", failed_msgs

    async def _mark_discrepancies_as_fixed(self, project_name: str, sql_actions: List[Dict[str, Any]], user_email: str):
        """Mark fixed discrepancies as 'fixed' in the database."""
        queries = []
        for action in sql_actions:
            row = action.get("original_row")
            if not row:
                continue

            cell_name = row.get(self.aliases.CELL_NAME)
            column_name = row.get(self.aliases.COLUMN_NAME)
            technology = self._get_technology_from_row(row)

            if technology:
                query = "UPDATE discrepancies SET status = 'fixed' WHERE cell_name = $1 AND column_name = $2 AND LOWER(technology) = LOWER($3)"
                queries.append((query, (cell_name, column_name, technology)))
            else:
                query = "UPDATE discrepancies SET status = 'fixed' WHERE cell_name = $1 AND column_name = $2"
                queries.append((query, (cell_name, column_name)))

        result = await self.db_manager.execute_bulk_queries(
            project_name=project_name,
            queries=queries,
            user_email=user_email,
            use_transaction=True,
        )

        count = result["success_count"]
        logger.info(f"Marked {count} discrepancies as fixed.")
        return count

    async def _enrich_discrepancies_with_technology(self, project_name: str, discrepancies: List[Dict[str, Any]], user_email: str) -> List[Dict[str, Any]]:
        """Enrich discrepancies with technology information from the discrepancies table."""
        if not discrepancies:
            return discrepancies

        cell_names = list(set(row.get(self.aliases.CELL_NAME) for row in discrepancies if row.get(self.aliases.CELL_NAME)))
        if not cell_names:
            return discrepancies

        placeholders = ",".join([f"${i+1}" for i in range(len(cell_names))])
        query = f"""
            SELECT DISTINCT cell_name, technology
            FROM discrepancies
            WHERE cell_name IN ({placeholders})
            AND technology IS NOT NULL
        """

        try:
            result = await self.db_manager.execute_query(project_name, query, user_email, tuple(cell_names))
            if result['status'] and result['data']:
                tech_map = {row['cell_name']: row['technology'] for row in result['data']}

                for row in discrepancies:
                    cell_name = row.get(self.aliases.CELL_NAME)
                    if cell_name and cell_name in tech_map:
                        row['technology'] = tech_map[cell_name]
                        logger.debug(f"Set technology '{tech_map[cell_name]}' for cell '{cell_name}'")
                    elif cell_name and 'technology' not in row:
                        if cell_name.startswith("NR_") or "_NR_" in cell_name:
                            row['technology'] = "NR"
                            logger.debug(f"Inferred technology 'NR' for cell '{cell_name}' from cell name")
                        else:
                            row['technology'] = "LTE"
                            logger.debug(f"Defaulted technology 'LTE' for cell '{cell_name}'")
        except Exception as e:
            logger.warning(f"Failed to enrich discrepancies with technology: {e}")

        return discrepancies

    async def _get_cell_technology_fixed_map(
        self, project_name: str, discrepancies: List[Dict[str, Any]], user_email: str
    ) -> Dict[str, bool]:
        """
        Fetch technology_fixed from cell_lte/cell_nr for each cell in discrepancies.
        Returns a map cell_name -> technology_fixed (bool). Missing or NULL in DB
        are omitted so caller can fall back to config-derived value.
        """
        lte_cells = set()
        nr_cells = set()
        for row in discrepancies:
            cell_name = row.get(self.aliases.CELL_NAME)
            if not cell_name:
                continue
            technology = self._get_technology_from_row(row)
            tech_upper = (technology or "").upper().strip()
            if tech_upper in ("NR", "5G", "5G NR"):
                nr_cells.add(cell_name)
            else:
                lte_cells.add(cell_name)

        result_map: Dict[str, bool] = {}
        if lte_cells:
            placeholders = ",".join([f"${i+1}" for i in range(len(lte_cells))])
            query = f"SELECT iid, technology_fixed FROM cell_lte WHERE iid IN ({placeholders})"
            try:
                r = await self.db_manager.execute_query(
                    project_name, query, user_email, tuple(lte_cells)
                )
                if r.get("status") and r.get("data"):
                    for row in r["data"]:
                        if row.get("technology_fixed") is not None:
                            result_map[row["iid"]] = bool(row["technology_fixed"])
            except Exception as e:
                logger.warning("Failed to fetch technology_fixed from cell_lte: %s", e)
        if nr_cells:
            placeholders = ",".join([f"${i+1}" for i in range(len(nr_cells))])
            query = f"SELECT iid, technology_fixed FROM cell_nr WHERE iid IN ({placeholders})"
            try:
                r = await self.db_manager.execute_query(
                    project_name, query, user_email, tuple(nr_cells)
                )
                if r.get("status") and r.get("data"):
                    for row in r["data"]:
                        if row.get("technology_fixed") is not None:
                            result_map[row["iid"]] = bool(row["technology_fixed"])
            except Exception as e:
                logger.warning("Failed to fetch technology_fixed from cell_nr: %s", e)
        return result_map


# ═══════════════════════════════════════════════════════════════════════════
# Helper Node (phase machine)
# ═══════════════════════════════════════════════════════════════════════════

async def eds_fixer_tool_helper(state: AgentState, runtime: Runtime[ctx_schema_State]):
    """Phase-machine helper node for EDS Fixer with replay-safe interrupt."""
    logger.info("[EDS FIXER HELPER] Entered")

    # Recover tool_call_id and tool_name from last message
    last_msg = state.internal_messages[-1] if state.internal_messages else None
    tool_call: Dict[str, Any] = {}
    if last_msg and hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        tool_call = last_msg.tool_calls[0]
    tool_id = tool_call.get("id", str(uuid.uuid4()))
    tool_name = tool_call.get("name", "run_eds_fixer_tool")

    # Helper to build final Command with ToolMessage
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
    fixer_data = (state.interrupt_data or {}).get("eds_fixer", {})
    phase = fixer_data.get("phase", "init")
    args = fixer_data.get("args", {})
    stored_thread_id = fixer_data.get("thread_id")

    # Guard: if thread_id mismatch, reset to init
    if phase != "init":
        if stored_thread_id != state.thread_id:
            logger.warning("[EDS FIXER HELPER] thread_id mismatch — resetting to init")
            phase = "init"

    stream_writer: StreamWriter = get_stream_writer()
    engine = EDSFixer(db_manager=global_db_manager)

    # Extract args
    project_name = args.get("project_name") or state.project_name
    user_email = getattr(runtime.context, "user_email", None) or args.get("user_email")
    network_parameters = args.get("network_parameters")
    cell_names = args.get("cell_names")
    site_names = args.get("site_names")
    all_flag = args.get("all", False)
    region = args.get("region")
    technology = args.get("technology")
    date = args.get("date")

    # ─── Phase: done / cancelled ───
    if phase in ("done", "cancelled"):
        logger.info(f"[EDS FIXER HELPER] Already {phase}, returning cached result")
        cached = fixer_data.get("result", {})
        return _finish(ToolOutput(**cached) if cached else ToolOutput(status=True, data="(no cached result)"))

    # ─── Phase: init ───
    if phase == "init":
        stream_writer({"step": "1/5", "status": "started", "message": "Getting discrepancies..."})
        try:
            result = await engine.discrepancy_engine.run(
                project_name, user_email, network_parameters, cell_names, site_names,
                all_flag, region, technology, status="mismatch", date=date,
            )
            if not result["status"]:
                stream_writer({"step": "1/5", "status": "failed", "message": f"Failed: {result.get('error')}"})
                return _finish(ToolOutput(status=False, errors=f"Failed to fetch discrepancies: {result.get('error')}"))

            discrepancies = result.get("data", [])
            if not discrepancies:
                stream_writer({"step": "1/5", "status": "completed", "message": "No discrepancies found."})
                return _finish(ToolOutput(status=True, data="No discrepancies found matching criteria.", md_data="No discrepancies found matching criteria."))

            # NOTE: Do NOT reverse-map discrepancy data here — the hashed cell_name values
            # are needed for DB operations (_mark_discrepancies_as_fixed, _update_postgres).
            # The executor catch-all reverse-maps any hashes in the final user-facing response.

            discrepancies = await engine._enrich_discrepancies_with_technology(project_name, discrepancies, user_email)
        except Exception as e:
            stream_writer({"step": "1/5", "status": "failed", "message": str(e)})
            return _finish(ToolOutput(status=False, errors=f"Error in Step 1 (Fetch): {e}"))

        stream_writer({"step": "2/5", "status": "started", "message": "Building update plan..."})
        try:
            json_payload, sql_actions = await engine._build_payloads_and_queries(discrepancies, project_name, user_email)
            if not json_payload:
                stream_writer({"step": "2/5", "status": "failed", "message": "No valid payload."})
                return _finish(ToolOutput(status=False, errors="Failed to generate valid JSON payload from discrepancies."))
        except Exception as e:
            stream_writer({"step": "2/5", "status": "failed", "message": str(e)})
            return _finish(ToolOutput(status=False, errors=f"Error in Step 2 (Build): {e}"))

        cell_count = len(json_payload.get("appData", []))
        stream_writer({"step": "2/5", "status": "completed", "message": f"Plan ready: {len(discrepancies)} discrepancies, {cell_count} cells."})

        # Persist plan and transition to ready_for_approval
        new_data = {
            "eds_fixer": {
                "thread_id": state.thread_id,
                "phase": "ready_for_approval",
                "args": args,
                "plan": {
                    "discrepancy_count": len(discrepancies),
                    "json_payload": json_payload,
                    "sql_actions": sql_actions,
                },
            }
        }
        return Command(goto="eds_fixer_tool_helper", update={"interrupt_data": new_data})

    # ─── Phase: ready_for_approval ───
    if phase == "ready_for_approval":
        plan = fixer_data.get("plan", {})
        json_payload = plan.get("json_payload", {})
        sql_actions = plan.get("sql_actions", [])
        discrepancy_count = plan.get("discrepancy_count", 0)

        approval_message = engine._build_approval_summary(discrepancy_count, json_payload, sql_actions)
        stream_writer({"step": "3/5", "status": "awaiting_approval", "message": "Waiting for user approval..."})

        user_response = interrupt({"type": "ASK_HUMAN_BINARY", "content": approval_message})
        approved = engine._parse_binary_approval(user_response)

        if not approved:
            stream_writer({"step": "3/5", "status": "denied", "message": "User denied the fix."})
            out = ToolOutput(status=False, data=json.dumps({"cancelled": True}), md_data="**User denied the fix. No update executed.**", errors="User denied the EDS fix operation.")
            new_data = {
                "eds_fixer": {
                    **fixer_data,
                    "phase": "cancelled",
                    "result": out.model_dump(),
                }
            }
            return Command(goto="eds_fixer_tool_helper", update={"interrupt_data": new_data})

        # Approved — transition to approved phase
        new_data = {
            "eds_fixer": {
                **fixer_data,
                "phase": "approved",
            }
        }
        return Command(goto="eds_fixer_tool_helper", update={"interrupt_data": new_data})

    # ─── Phase: approved ───
    if phase == "approved":
        plan = fixer_data.get("plan", {})
        json_payload = plan.get("json_payload", {})
        sql_actions = plan.get("sql_actions", [])

        max_batch = engine.config.max_batch_size
        batches = engine._make_batches(json_payload, sql_actions, max_batch)
        total_batches = len(batches)

        total_cells_updated = 0
        total_db_updated = 0
        total_fixed = 0

        stream_writer({"step": "4/5", "status": "started", "message": f"Processing {total_batches} batch(es)..."})

        for batch_idx, batch in enumerate(batches):
            batch_num = batch_idx + 1
            batch_payload = batch["payload"]
            batch_sql_actions = batch["sql_actions"]
            batch_cell_count = len(batch_payload.get("appData", []))

            stream_writer({"step": "4/5", "status": "in_progress", "message": f"Batch {batch_num}/{total_batches}..."})

            try:
                api_ok, api_msg = await engine._send_eds_batch(batch_payload, batch_num, total_batches, stream_writer)
                if not api_ok:
                    stream_writer({"step": "4/5", "status": "failed", "message": api_msg})
                    out = ToolOutput(status=False, errors=f"{api_msg}. Completed {batch_idx}/{total_batches} batch(es) before failure.")
                    new_data = {"eds_fixer": {**fixer_data, "phase": "done", "result": out.model_dump()}}
                    return Command(goto="eds_fixer_tool_helper", update={"interrupt_data": new_data})
            except Exception as e:
                stream_writer({"step": "4/5", "status": "failed", "message": str(e)})
                out = ToolOutput(status=False, errors=f"Batch {batch_num} exception: {e}")
                new_data = {"eds_fixer": {**fixer_data, "phase": "done", "result": out.model_dump()}}
                return Command(goto="eds_fixer_tool_helper", update={"interrupt_data": new_data})

            total_cells_updated += batch_cell_count

            if batch_sql_actions:
                try:
                    db_ok, db_msg, failed_queries = await engine._update_postgres(project_name, batch_sql_actions, user_email)
                    if not db_ok:
                        sql_block = "\n".join(failed_queries)
                        stream_writer({"step": "5/5", "status": "partial_success", "message": f"DB failure on batch {batch_num}."})
                        out = ToolOutput(
                            status=True,
                            data=f"EDS API completed ({total_cells_updated} cells). DB partial failure on batch {batch_num}: {db_msg}",
                            md_data=f"### Partial Success\n- **EDS API**: {total_cells_updated} cells\n- **PostgreSQL**: Failures:\n```sql\n{sql_block}\n```",
                        )
                        new_data = {"eds_fixer": {**fixer_data, "phase": "done", "result": out.model_dump()}}
                        return Command(goto="eds_fixer_tool_helper", update={"interrupt_data": new_data})
                    total_db_updated += len(batch_sql_actions)
                except Exception as e:
                    queries_str = "\n".join([q["query"] + f" -- {q['params']}" for q in batch_sql_actions])
                    stream_writer({"step": "5/5", "status": "failed", "message": f"DB crashed: {e}"})
                    out = ToolOutput(
                        status=True,
                        data=f"EDS API completed ({total_cells_updated} cells). DB crashed on batch {batch_num}.",
                        md_data=f"### Warning\nEDS API OK, but PostgreSQL crashed:\n```sql\n{queries_str}\n```",
                    )
                    new_data = {"eds_fixer": {**fixer_data, "phase": "done", "result": out.model_dump()}}
                    return Command(goto="eds_fixer_tool_helper", update={"interrupt_data": new_data})

            logger.info(f"[EDS FIXER] Marking discrepancies as fixed with {len(batch_sql_actions)} queries")
            batch_fixed = await engine._mark_discrepancies_as_fixed(project_name, batch_sql_actions, user_email)
            total_fixed += batch_fixed

        stream_writer({"step": "5/5", "status": "completed", "message": f"Done! {total_cells_updated} cells, {total_db_updated} DB rows, {total_fixed} fixed."})

        out = ToolOutput(
            status=True,
            data=f"Success! {total_cells_updated} cells updated via EDS API in {total_batches} batch(es), {total_db_updated} DB records updated, {total_fixed} discrepancies marked as fixed.",
            md_data=(
                f"## EDS Fixer Success\n"
                f"- **EDS API**: {total_cells_updated} cells updated in {total_batches} batch(es)\n"
                f"- **PostgreSQL**: {total_db_updated} records updated\n"
                f"- **Discrepancies**: {total_fixed} marked as fixed"
            ),
        )
        new_data = {"eds_fixer": {**fixer_data, "phase": "done", "result": out.model_dump()}}
        return Command(goto="eds_fixer_tool_helper", update={"interrupt_data": new_data})

    # Fallback — unknown phase
    logger.warning(f"[EDS FIXER HELPER] Unknown phase '{phase}', resetting")
    return _finish(ToolOutput(status=False, errors=f"Unknown phase '{phase}'"))


# ═══════════════════════════════════════════════════════════════════════════
# Tool Factory (router)
# ═══════════════════════════════════════════════════════════════════════════

def create_eds_fixer_tool(db_manager: Optional[DynamicAsyncDatabaseManager] = None):
    """Create EDS fixer tool with dependencies."""

    from db_agent_v2.tools.base import DataRef

    class EDSFixerArgs(BaseModel):
        network_parameters: List[str] = Field(default_factory=list, description="Filter by specific parameter names to fix, e.g. ['azimuth', 'mechanical_tilt']. Empty list means fix all mismatched parameters.")
        cell_names: List[str] = Field(default_factory=list, description="Specific Cell IIDs/names to fix. Do NOT use when using data_refs.")
        site_names: List[str] = Field(default_factory=list, description="Specific Site IIDs/names to fix. Do NOT use when using data_refs.")
        all: bool = Field(default=False, description="If true, fix ALL discrepancies in the entire project. MUTUALLY EXCLUSIVE with data_refs, cell_names, site_names — do NOT set all=True when using data_refs or providing specific cells/sites.")
        region: str = Field(default="", description="Region name filters (matches address, town, state, postcode fields). E.g. ['London', 'Region_North'].")
        technology: str = Field(default="", description='Technology filter: "LTE" (4G only), "NR" (5G only), or "ALL" (both). Empty string means no technology filter.')
        date: str = Field(default="", description="Filter by import date in YYYY-MM-DD format. Empty string means latest available date.")
        data_refs: Optional[List[DataRef]] = Field(default=None, description="References to pass cell/site identifiers from the most recent asset_db_rag_tool result. When data_refs is provided, do NOT set all=True and do NOT manually fill cell_names/site_names — the system resolves values automatically.")

    @tool("run_eds_fixer_tool", args_schema=EDSFixerArgs, parse_docstring=False)
    async def run_eds_fixer_tool(
        project_name: Annotated[str, InjectedState("project_name")],
        user_email: Annotated[str, InjectedToolArg],
        network_parameters: Optional[List[str]] = None,
        cell_names: Optional[List[str]] = None,
        site_names: Optional[List[str]] = None,
        all: bool = False,
        region: Optional[str] = None,
        technology: Optional[str] = None,
        date: Optional[str] = None,
        thread_id: Annotated[Optional[str], InjectedState("thread_id")] = None,
        data_refs: Optional[List[DataRef]] = None,
    ) -> Command:
        """
        Apply fixes to synchronize Asset DB with OSS values via the EDS API.
        Filters the discrepancies with the Args provided and then fixes the discrepancies based on the provided filters.
        Any one or multiple of the Args must be provided to run the EDS Fixer tool.

        IMPORTANT — Built-in approval:
         - This tool has a **built-in human approval step**. After building the update plan it will
           automatically pause and ask the user to approve or deny. You do NOT need to call
           `ask_human_tool` separately before invoking this tool.

        ## How the tool works [Summary]
        This is a **WRITE** operation tool that fixes identified discrepancies between Asset and OSS data.
        1) Fetches current mismatched discrepancies using the same filters as discrepancy engine
        2) Enriches data with technology info (LTE/NR) for correct table mapping
        3) Builds JSON payload and SQL update plan
        4) **Pauses for user approval** (approve / deny)
        5) On approval — sends PUT request to EDS API in batches and updates local PostgreSQL tables
        6) Marks fixed records as status='fixed' in the discrepancies table

        ## Limitations
        -   **Scope Restriction**: This tool can ONLY fix discrepancies found between Asset and OSS data.

        ## Capabilities
        -   **Batch Processing**: Sends EDS updates in batches of 100 cells (configurable).
        -   **Synchronization**: Ensures consistency between planning (Asset) and operational (OSS) data.

        ## When to use
        -   **ONLY** after the user has explicitly requested to "fix", "update", or "sync" data.
        -   **ONLY** for fixing discrepancies between Asset and OSS data.

        ## IMPORTANT — Choosing the right arguments:
        - `all` and `data_refs` are MUTUALLY EXCLUSIVE. Never use both together.
        - **To fix discrepancies for cells from the most recent RAG query** (e.g., "fix those cells", "fix discrepancies for cells with azimuth issues"): use `data_refs` to reference the most recent asset_db_rag_tool result. Do NOT set `all=True`. Do NOT manually copy cell names.
        - **To fix ALL discrepancies in the project**: use `all=True`. Do NOT provide `data_refs`, `cell_names`, or `site_names`.
        - Even if there is only one entity, pass it as a list.
        """
        args = {
            "project_name": project_name,
            "user_email": user_email,
            "network_parameters": network_parameters or [],
            "cell_names": cell_names or [],
            "site_names": site_names or [],
            "all": all,
            "region": region or None,
            "technology": technology or None,
            "date": date or None,
        }

        return Command(
            goto="eds_fixer_tool_helper",
            update={
                "interrupt_data": {
                    "eds_fixer": {
                        "thread_id": thread_id,
                        "phase": "init",
                        "args": args,
                    }
                }
            },
        )

    return run_eds_fixer_tool
