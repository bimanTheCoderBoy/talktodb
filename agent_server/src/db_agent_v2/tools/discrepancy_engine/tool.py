import json
import logging
from typing import Literal, Optional, List, Set, Dict, Any, Annotated
from datetime import datetime
from langchain_core.tools import tool, InjectedToolArg
from langgraph.prebuilt import InjectedState
from db_agent_v2.config.tool_config import DiscrepancyColumnAliases
from db_agent_v2.db.DatabaseManager import DynamicAsyncDatabaseManager, global_db_manager
from db_agent_v2.tools.base import ToolOutput
from security.encryption.iid_hash_utils import (
    HASHING_ENABLED as IID_HASHING_ENABLED,
    hash_iid,
    is_hashed_value,
    normalize_to_db_value,
    reverse_map_hashes,
)
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DiscrepancyEngine:
    """Discrepancy Engine is a Tool that is used to compare the OSS and Asset DB data.
       NOTE : it finds discrepancies only for cell parameter.
    """

    def __init__(self, db_manager: Optional[DynamicAsyncDatabaseManager] = None):
        """Initialize Discrepancy Engine with database manager."""
        self.db_manager = db_manager or global_db_manager
        self.column_aliases = DiscrepancyColumnAliases()
        if self.db_manager is None:
            raise ValueError("Database manager is not initialized")

    async def _get_cells_by_region(self, project_name: str, region: str, user_email: str) -> Set[str]:
        """Get cell names for a specific region."""
        # Use wildcard matching for region fields
        region_pattern = f"%{region.strip()}%"
        query = """
        SELECT DISTINCT d.cell_name 
        FROM discrepancies d
        JOIN location l ON d.location_eid = l.eid
        WHERE (
            LOWER(l.address1) LIKE LOWER($1) OR
            LOWER(l.town) LIKE LOWER($2) OR
            LOWER(l.state) LIKE LOWER($3) OR
            LOWER(l.postcode) LIKE LOWER($4)
        )
        """
        result = await self.db_manager.execute_query(
            project_name,
            query,
            user_email,
            (region_pattern, region_pattern, region_pattern, region_pattern),
        )
        if not result['status']:
            return set()
        return {row['cell_name'] for row in result['data']}

    async def _get_cells_by_technology(self, project_name: str, technology: str, user_email: str) -> Set[str]:
        """Get cell names for a specific technology.

        Maps technology to the appropriate cell table:
        - "LTE" or "4G" -> cell_lte
        - "NR" or "5G" -> cell_nr
        - "ALL" -> queries both tables without technology filter

        If technology doesn't match known values, queries both tables.
        """
        tech_upper = technology.strip().upper()
        tech_normalized = technology.strip()

        # Map technology to table name(s)
        if tech_upper in ("LTE", "4G", "4G LTE", "4g", "lte"):
            table_names = ["cell_lte"]
            use_tech_filter = True
        elif tech_upper in ("NR", "5G", "5G NR", "nr", "5g"):
            table_names = ["cell_nr"]
            use_tech_filter = True
        elif tech_upper == "ALL":
            # "ALL" means query both tables without technology filter
            table_names = ["cell_lte", "cell_nr"]
            use_tech_filter = False
        else:
            # Unknown technology: query both tables with technology filter
            table_names = ["cell_lte", "cell_nr"]
            use_tech_filter = True

        all_cells = set()
        for table_name in table_names:
            if use_tech_filter:
                query = f"""
                SELECT DISTINCT d.cell_name
                FROM discrepancies d
                WHERE d.cell_name IN (
                    SELECT iid FROM {table_name} WHERE LOWER(technology_active) = LOWER($1)
                )
                """
                result = await self.db_manager.execute_query(project_name, query, user_email, (tech_normalized,))
            else:
                # No technology filter - get all cells from this table
                query = f"""
                SELECT DISTINCT d.cell_name
                FROM discrepancies d
                WHERE d.cell_name IN (
                    SELECT iid FROM {table_name}
                )
                """
                result = await self.db_manager.execute_query(project_name, query, user_email, ())

            if result['status'] and result['data']:
                all_cells.update({row['cell_name'] for row in result['data']})

        return all_cells

    def _generate_column_pie_chart(self, column_summary: Dict[str, Dict]) -> str:
        """Generate parameter summary using a markdown table with visual bars.
        Replaces fragile Mermaid pie chart that breaks on special characters."""
        sorted_columns = sorted(column_summary.items(),
                               key=lambda x: x[1]['total_discrepancies'],
                               reverse=True)

        if not sorted_columns:
            return ""

        max_count = sorted_columns[0][1]['total_discrepancies'] if sorted_columns else 1
        total = sum(s['total_discrepancies'] for _, s in sorted_columns)

        chart = "**Discrepancies by Network Parameter**\n\n"
        chart += "| Parameter | Count | % | Distribution |\n"
        chart += "|-----------|------:|--:|-------------|\n"

        for col_name, summary in sorted_columns:
            count = summary['total_discrepancies']
            pct = (count / total * 100) if total > 0 else 0
            bar_len = int((count / max_count) * 20) if max_count > 0 else 0
            bar = "█" * bar_len + "░" * (20 - bar_len)
            chart += f"| {col_name} | {count:,} | {pct:.1f}% | {bar} |\n"

        chart += "\n"
        return chart

    def _generate_column_bar_chart(self, column_summary: Dict[str, Dict]) -> str:
        """Generate visual bar chart using a markdown table with inline bars.
        Replaces the fragile Mermaid Gantt hack which breaks on special characters."""
        sorted_columns = sorted(column_summary.items(),
                               key=lambda x: x[1]['total_discrepancies'],
                               reverse=True)

        if not sorted_columns:
            return ""

        max_count = sorted_columns[0][1]['total_discrepancies'] if sorted_columns else 1
        total = sum(s['total_discrepancies'] for _, s in sorted_columns)

        chart = "**Discrepancies by Network Parameter**\n\n"
        chart += "| Parameter | Count | % | Distribution |\n"
        chart += "|-----------|------:|--:|-------------|\n"

        for col_name, summary in sorted_columns:
            count = summary['total_discrepancies']
            pct = (count / total * 100) if total > 0 else 0
            # Visual bar using unicode block chars (scales to max)
            bar_len = int((count / max_count) * 20) if max_count > 0 else 0
            bar = "█" * bar_len + "░" * (20 - bar_len)
            chart += f"| {col_name} | {count:,} | {pct:.1f}% | {bar} |\n"

        chart += "\n"
        return chart

    def _generate_column_table(self, column_summary: Dict[str, Dict], total_discrepancies: int) -> str:
        """Generate table for column discrepancies (>30 columns or fallback)"""
        table = "| Network Parameter Name | Total Discrepancies | Contribution (%) |\n"
        table += "|------------------------|--------------------|-----------------|\n"

        # Sort by total discrepancies descending
        sorted_columns = sorted(column_summary.items(),
                                key=lambda x: x[1]['total_discrepancies'],
                                reverse=True)

        for col_name, summary in sorted_columns:
            count = summary['total_discrepancies']
            contribution = (count / total_discrepancies * 100) if total_discrepancies > 0 else 0
            table += f"| {col_name} | {count} | {contribution:.2f}% |\n"

        return table

    async def _format_discrepancies_results(self, result: Dict[str, Any], project_name: str = "") -> ToolOutput:
        """Format discrepancies results:
           result must have the following keys: status, data, columns, count, error
        """
        if not result['status'] or result['error'] is not None:
            return ToolOutput(status=False, errors=result['error'])

        data = result['data']
        columns_list = result['columns'] or []
        count = result['count']

        if data is None or len(data) == 0 or count == 0:
            return ToolOutput(status=True, data="No discrepancies found matching criteria.", md_data="No discrepancies found matching criteria.")

        # Check if all required columns are present
        required_columns = vars(self.column_aliases).values()
        if not all(column in columns_list for column in required_columns):
            return ToolOutput(status=False, errors="Columns are not found")

        # Reverse-map hashed cell_name and enodeb_name for display
        if IID_HASHING_ENABLED and data:
            hash_fields = [self.column_aliases.CELL_NAME, self.column_aliases.ENODEB_NAME]
            hashes = set()
            for row in data:
                for f in hash_fields:
                    val = row.get(f)
                    if val and isinstance(val, str) and is_hashed_value(val):
                        hashes.add(val)
            if hashes and self.db_manager and project_name:
                async with self.db_manager.connection(project_name) as conn:
                    rmap = await reverse_map_hashes(conn, hashes)
                if rmap:
                    for row in data:
                        for f in hash_fields:
                            val = row.get(f)
                            if val and val in rmap:
                                row[f] = rmap[val]

        # getting markdown data from the result
        _, _, markdown_data = await DynamicAsyncDatabaseManager.get_formatted_result(result)

        # --- Aggregate summaries (shared by LLM JSON + UI markdown) ---
        cell_name_wise_summary = {}
        for row in data:
            cell_name = row[self.column_aliases.CELL_NAME]
            status = row[self.column_aliases.STATUS]
            if cell_name not in cell_name_wise_summary:
                cell_name_wise_summary[cell_name] = {
                    "total_discrepancies": 0,
                    "status": set(),
                    "affected_columns": set()
                }
            cell_name_wise_summary[cell_name]['total_discrepancies'] += 1
            cell_name_wise_summary[cell_name]['status'].add(status)
            cell_name_wise_summary[cell_name]['affected_columns'].add(row[self.column_aliases.COLUMN_NAME])

        enodeb_name_wise_summary = {}
        for row in data:
            enodeb_name = row[self.column_aliases.ENODEB_NAME]
            status = row[self.column_aliases.STATUS]
            if enodeb_name not in enodeb_name_wise_summary:
                enodeb_name_wise_summary[enodeb_name] = {
                    "total_discrepancies": 0,
                    "status": set(),
                    "affected_columns": set()
                }
            enodeb_name_wise_summary[enodeb_name]['total_discrepancies'] += 1
            enodeb_name_wise_summary[enodeb_name]['status'].add(status)
            enodeb_name_wise_summary[enodeb_name]['affected_columns'].add(row[self.column_aliases.COLUMN_NAME])

        column_name_wise_summary = {}
        total_discrepancies_count = 0
        for row in data:
            column_name = row[self.column_aliases.COLUMN_NAME]
            if column_name not in column_name_wise_summary:
                column_name_wise_summary[column_name] = {
                    "total_discrepancies": 0,
                    "affected_cells": set(),
                    "affected_sites": set()
                }
            column_name_wise_summary[column_name]['total_discrepancies'] += 1
            total_discrepancies_count += 1

        # --- LLM-facing data: structured JSON for reliable tagging ---
        llm_json = {
            "total_discrepancies": count,
            "cell_summary": [
                {
                    "cell_name": cell_name,
                    "total": summary["total_discrepancies"],
                    "status": list(summary["status"]),
                    "affected_columns": list(summary["affected_columns"])
                }
                for cell_name, summary in cell_name_wise_summary.items()
            ],
            "site_summary": [
                {
                    "site_name": site_name,
                    "total": summary["total_discrepancies"],
                    "status": list(summary["status"]),
                    "affected_columns": list(summary["affected_columns"])
                }
                for site_name, summary in enodeb_name_wise_summary.items()
            ],
            "parameter_summary": [
                {
                    "parameter_name": col_name,
                    "total": summary["total_discrepancies"]
                }
                for col_name, summary in column_name_wise_summary.items()
            ]
        }
        llm_md = f"**Discrepancy Summary:**\n{json.dumps(llm_json)}"

        # --- UI-facing markdown: rich tables + charts (unchanged) ---
        ui_summary_md = f"\n## Total Discrepancies: {count}\n"
        ui_summary_md += "### Cell Name Wise Summary\n"
        ui_summary_md += "| Cell Name | Total Discrepancies | Status | Affected Columns |\n"
        ui_summary_md += "|-----------|--------------------|--------|------------------|\n"
        for cell_name, summary in cell_name_wise_summary.items():
            ui_summary_md += f"| {cell_name} | {summary['total_discrepancies']} | {', '.join(summary['status'])} | {', '.join(summary['affected_columns'])} |\n"
        ui_summary_md += "\n"

        ui_summary_md += "### Site Name Wise Summary\n"
        ui_summary_md += "| Site Name | Total Discrepancies | Status | Affected Columns |\n"
        ui_summary_md += "|-----------|--------------------|--------|------------------|\n"
        for enodeb_name, summary in enodeb_name_wise_summary.items():
            ui_summary_md += f"| {enodeb_name} | {summary['total_discrepancies']} | {', '.join(summary['status'])} | {', '.join(summary['affected_columns'])} |\n"
        ui_summary_md += "\n"

        column_name_wise_summary_md = "### Network Parameter Wise Summary\n\n"
        num_columns = len(column_name_wise_summary)
        if num_columns < 10:
            column_name_wise_summary_md += self._generate_column_pie_chart(column_name_wise_summary)
        elif 10 <= num_columns <= 30:
            column_name_wise_summary_md += self._generate_column_bar_chart(column_name_wise_summary)
        else:
            column_name_wise_summary_md += self._generate_column_table(column_name_wise_summary, total_discrepancies_count)

        markdown_data = f"""## Discrepancy Report\n{markdown_data}\n\n## Summary\n{ui_summary_md}\n{column_name_wise_summary_md.strip()}"""
        return ToolOutput(status=True, data=llm_md, is_summary_available=True, md_data=markdown_data)

    async def run(
        self,
        project_name: str,
        user_email: str,
        network_parameters: Optional[List[str]] = None,
        cell_names: Optional[List[str]] = None,
        site_names: Optional[List[str]] = None,
        all: Optional[bool] = None,
        region: Optional[str] = None,
        technology: Optional[str] = None,
        status: str = "mismatch",
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Main run method for discrepancy engine."""

        # Smart fallback: if technology is specified but no other filters provided,
        # assume the user wants ALL discrepancies for that technology.
        if not all and not cell_names and not site_names and not region and not network_parameters:
            if technology and technology.upper() != "ALL":
                all = True
                logger.info(f"[DISCREPANCY_ENGINE] No entities specified — auto-setting all=True (technology={technology})")

        common_conditions = []
        common_params = []

        if status and status.lower() != 'all':
            common_conditions.append(f"LOWER(status) = LOWER(${len(common_params) + 1})")
            common_params.append(status)

        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                common_conditions.append(f"DATE(imported_at) = ${len(common_params) + 1}")
                common_params.append(date_obj)
            except ValueError:
                raise ValueError(f"Invalid date format: {date}. Expected YYYY-MM-DD.")
        else:
            common_conditions.append("imported_at = (SELECT MAX(imported_at) FROM discrepancies)")

        if all:
            if technology and technology.strip().upper() != "ALL":
                tech_upper = technology.strip().upper()
                if tech_upper in ("LTE", "4G", "4G LTE"):
                    tech_filter = "LTE"
                elif tech_upper in ("NR", "5G", "5G NR"):
                    tech_filter = "NR"
                else:
                    tech_filter = technology.strip()

                common_conditions.append(f"LOWER(technology) = LOWER(${len(common_params) + 1})")
                common_params.append(tech_filter)

            where_clause = " AND ".join(common_conditions) if common_conditions else "1=1"
            query = f"""
            SELECT 
                cell_name AS "{self.column_aliases.CELL_NAME}", 
                enodeb_name AS "{self.column_aliases.ENODEB_NAME}", 
                column_name AS "{self.column_aliases.COLUMN_NAME}", 
                oss_value AS "{self.column_aliases.OSS_VALUE}", 
                db_value AS "{self.column_aliases.DB_VALUE}", 
                checked_at AS "{self.column_aliases.CHECKED_AT}",
                status AS "{self.column_aliases.STATUS}"
            FROM discrepancies
            WHERE {where_clause}
            ORDER BY imported_at DESC
            """
            print(query)
            return await self.db_manager.execute_query(project_name, query, user_email, tuple(common_params))

        cell_sets: List[Set[str]] = []
        final_cells: List[str] = []
        final_sites: List[str] = []

        if cell_names:
            # Normalize: <HASH:xxx> → xxx, original → hash, already-hashed → as-is
            cell_sets.append(set(normalize_to_db_value(c) for c in cell_names))
        if site_names:
            final_sites = [normalize_to_db_value(s) for s in site_names]

        if cell_names is None and site_names is None and region:
            region_cells = await self._get_cells_by_region(project_name, region, user_email)
            cell_sets.append(region_cells)

        # Technology filter always applies when provided (not "ALL")
        if technology and technology.strip().upper() != "ALL":
            tech_cells = await self._get_cells_by_technology(project_name, technology, user_email)
            cell_sets.append(tech_cells)

        if cell_sets:
            final_cells = list(set.intersection(*cell_sets))

        if not cell_sets and not final_sites and not network_parameters and status.lower() == 'all' and not date:
            raise ValueError("No filters provided. Please specify cells, sites, region, technology, network_parameters, status, date, or all=True.")

        where_clauses = list(common_conditions)
        params = list(common_params)
        param_idx = len(params) + 1

        # Entity filter (Cells OR Sites)
        entity_conditions = []

        # Cells — use ANY($N::text[]) for large lists to avoid PostgreSQL's 32767 param limit
        if final_cells:
            entity_conditions.append(f"cell_name = ANY(${param_idx}::text[])")
            params.append(list(final_cells))
            param_idx += 1

        if final_sites:
            entity_conditions.append(f"enodeb_name = ANY(${param_idx}::text[])")
            params.append(list(final_sites))
            param_idx += 1

        if entity_conditions:
            where_clauses.append(f"({' OR '.join(entity_conditions)})")

        if network_parameters:
            where_clauses.append(f"column_name = ANY(${param_idx}::text[])")
            params.append(list(network_parameters))
            param_idx += 1

        where_str = " AND ".join(where_clauses) if where_clauses else "1=1"

        query = f"""
            SELECT 
                cell_name AS "{self.column_aliases.CELL_NAME}",
                enodeb_name AS "{self.column_aliases.ENODEB_NAME}",
                column_name AS "{self.column_aliases.COLUMN_NAME}",
                oss_value AS "{self.column_aliases.OSS_VALUE}",
                db_value AS "{self.column_aliases.DB_VALUE}",
                checked_at AS "{self.column_aliases.CHECKED_AT}",
                status AS "{self.column_aliases.STATUS}"
            FROM discrepancies
            WHERE {where_str}
            ORDER BY imported_at DESC
            """
        print(query)
        return await self.db_manager.execute_query(project_name, query, user_email, tuple(params))

    async def execute(
        self,
        project_name: str,
        user_email: str,
        network_parameters: Optional[List[str]] = None,
        cell_names: Optional[List[str]] = None,
        site_names: Optional[List[str]] = None,
        all: Optional[bool] = None,
        region: Optional[str] = None,
        technology: Optional[str] = None,
        status: str = "mismatch",
        date: Optional[str] = None
    ) -> ToolOutput:
        """Execute discrepancy engine with specified parameters."""
        try:
            result = await self.run(
                project_name, user_email, network_parameters, cell_names, site_names,
                all, region, technology, status, date,
            )
            return await self._format_discrepancies_results(result, project_name=project_name)

        except Exception as e:
            return ToolOutput(
                status=False,
                errors=str(e),
                md_data=f"Error executing discrepancy engine: {str(e)}"
            )


# Factory function for tool creation
def create_discrepancy_engine_tool(db_manager: Optional[DynamicAsyncDatabaseManager] = None):
    """Create discrepancy engine tool with dependencies."""
    engine = DiscrepancyEngine(db_manager)

    from db_agent_v2.tools.base import DataRef

    class DiscrepancyEngineArgs(BaseModel):
        network_parameters: List[str] = Field(default_factory=list, description="Filter by specific parameter names, e.g. ['azimuth', 'mechanical_tilt', 'electrical_tilt']. Empty list means all parameters.")
        cell_names: List[str] = Field(default_factory=list, description="Specific Cell IIDs/names to check. Do NOT use when using data_refs.")
        site_names: List[str] = Field(default_factory=list, description="Specific Site IIDs/names to check. Do NOT use when using data_refs.")
        all: bool = Field(default=False, description="If true, return ALL discrepancies in the entire project. MUTUALLY EXCLUSIVE with data_refs, cell_names, site_names — do NOT set all=True when using data_refs or providing specific cells/sites.")
        region: str = Field(default="", description="Region name filters (matches address, town, state, postcode fields). E.g. ['London', 'Region_North'].")
        technology: str = Field(default="", description='Technology filter: "LTE" (4G only), "NR" (5G only), or "ALL" (both). Empty string means no technology filter.')
        status: Literal["mismatch", "fixed", "all"] = Field(default="mismatch", description='"mismatch" (default): unresolved discrepancies only. "fixed": resolved only. "all": both mismatch and fixed.')
        date: str = Field(default="", description="Filter by import date in YYYY-MM-DD format. Empty string means latest available date.")
        data_refs: Optional[List[DataRef]] = Field(default=None, description="References to pass cell/site identifiers from the most recent asset_db_rag_tool result. When data_refs is provided, do NOT set all=True and do NOT manually fill cell_names/site_names — the system resolves values automatically.")

    @tool("discrepancy_engine_tool", args_schema=DiscrepancyEngineArgs, parse_docstring=False)
    async def discrepancy_engine_tool(
        project_name: Annotated[str, InjectedState("project_name")],
        user_email: Annotated[str, InjectedToolArg],
        network_parameters: Optional[List[str]] = None,
        cell_names: Optional[List[str]] = None,
        site_names: Optional[List[str]] = None,
        all: bool = False,
        region: Optional[str] = None,
        technology: Optional[str] = None,
        status: Literal["mismatch", "fixed", "all"] = "mismatch",
        date: Optional[str] = None,
        data_refs: Optional[List] = None,
    ) -> ToolOutput:
        """
        Fetch discrepancy reports comparing OSS (Live Network) vs. Asset DB (Planned) based on the Args provided.
        any one or multiple of the Args must be provided to run the discrepancy engine.

        ## How the tool works [Summary]
        This tool queries a specialized `discrepancies` table where differences between the operational network (OSS) and the planning database (Asset DB) are recorded.
        1) Queries a discrepancies table where OSS vs DB differences are pre-recorded
        2) Filters by multiple criteria: cell_names, site_names, region, technology, network_parameters, status, date
        3) Builds cell-wise, site-wise, and parameter-wise summaries
        4) Generates visualizations (Pie/Bar charts or tables) based on the number of affected parameters
        5) Returns formatted markdown with statistics and detailed discrepancy list
        -  detailed information about the tool and how it works is available at [Discrepancy Engine Documentation](https://www.notion.so/bimandas/What-Next-AANA-2c3bb91a7a9780bd837fe70264ebf791)

        ## Capabilities
        -   **Comparison**: Identify where `oss_value` != `db_value`.
        -   **Filtering**: Drill down by specific parameters (e.g., "Check only 'azimuth' discrepancies").
        -   **Scope**: Analyze specific cells, sites, or entire regions/technologies.

        ## When to use
        -   When the user asks about "discrepancies", "mismatches", "differences", or "sync issues".
        -   **Before fixing**: Use this tool to identify *what* needs fixing.
        -   **Read-Only**: This tool DOES NOT fix data. It only reports differences.

        ## IMPORTANT — Choosing the right arguments:
        - `all` and `data_refs` are MUTUALLY EXCLUSIVE. Never use both together.
        - **To check discrepancies for cells from the most recent RAG query** (e.g., "check discrepancies for those cells", "find mismatches for cells with azimuth=0"): use `data_refs` to reference the most recent asset_db_rag_tool result. Do NOT set `all=True`. Do NOT manually copy cell names.
        - **To check ALL discrepancies in the project**: use `all=True`. Do NOT provide `data_refs`, `cell_names`, or `site_names`.
        - Even if there is only one entity, pass it as a list.
        """
        return await engine.execute(
            project_name,
            user_email,
            network_parameters or [],
            cell_names or [],
            site_names or [],
            all,
            region or None,
            technology or None,
            status,
            date or None,
        )

    return discrepancy_engine_tool
