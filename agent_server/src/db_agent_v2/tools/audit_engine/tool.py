from typing import Annotated, Optional, List, Dict, Any, Literal
from datetime import datetime
import asyncio
import logging
from enum import Enum
from langchain_core.tools import tool, InjectedToolArg
from langgraph.types import StreamWriter
from db_agent_v2.config.tool_config import AuditEngineToolConfig, AuditCategory
from db_agent_v2.db.DatabaseManager import DynamicAsyncDatabaseManager, global_db_manager
from .base import EntityType
from .registry import audit_function_registry
from .rule_preferences import load_rule_preferences, is_rule_enabled, load_enabled_custom_rules, load_builtin_rule_configs
from .custom_rules import CustomAuditRuleExecutor
from langgraph.prebuilt import InjectedState
from db_agent_v2.tools.base import ToolOutput
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field
from security.encryption.iid_hash_utils import (
    HASHING_ENABLED as IID_HASHING_ENABLED,
    collect_hashes_from_rows,
    apply_reverse_map,
    reverse_map_hashes,
)
# Import functions to ensure they are registered very important for the audit engine to work
from .functions import cell_functions, cell_nr_functions, site_functions
from .functions.helpers import format_audit_label



# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Technology(str, Enum):
    """Technology filter for cell audits"""
    LTE = "LTE"
    NR = "NR"
    ALL = "ALL"


class AuditEngine:
    """Audit Engine with injected dependencies."""
    
    def __init__(self, config=None, db_manager: Optional[DynamicAsyncDatabaseManager] = None):
        """Initialize Audit Engine with configuration and database manager."""
        self.config = config or AuditEngineToolConfig()
        self.db_manager = db_manager or global_db_manager
        
        if self.db_manager is None:
            raise ValueError("Database manager is not initialized")
    
    async def _fetch_query(self, project_name: str, query: str, user_email: str, params=None):
        """Helper function to execute SQL and return results as list of dicts."""
        result = await self.db_manager.execute_query(project_name, query, user_email, params)
        if not result['status']:
            logger.error(f"Error executing query: {result['error']}")
            raise Exception(f"Error executing query: {result['error']}")
        return result['data']

    async def _reverse_map_markdown(self, markdown: str, project_name: str) -> str:
        """Replace hashed IID values in markdown text with originals from iid_mapping."""
        if not IID_HASHING_ENABLED or not markdown:
            return markdown
        import re
        hash_pattern = re.compile(r'\b[0-9a-f]{32}\b')
        hashes = set(hash_pattern.findall(markdown))
        if not hashes:
            return markdown
        async with self.db_manager.connection(project_name) as conn:
            rmap = await reverse_map_hashes(conn, hashes)
        if rmap:
            for h, orig in rmap.items():
                markdown = markdown.replace(h, orig)
        return markdown

    # Helper Functions for ID Resolution
    
    async def get_latest_cell_names(self, project_name: str, user_email: str, technology: Technology = Technology.ALL):
        """Get only cell IIDs from the most recent import batch (based on technology filter)."""
        if technology == Technology.LTE:
            query = """
                SELECT DISTINCT c1.iid 
                FROM cell_lte c1
                WHERE c1.imported_at = (
                    SELECT MAX(imported_at) 
                    FROM cell_lte
                ) 
                ORDER BY c1.iid;
            """
        elif technology == Technology.NR:
            query = """
                SELECT DISTINCT c1.iid 
                FROM cell_nr c1
                WHERE c1.imported_at = (
                    SELECT MAX(imported_at) 
                    FROM cell_nr
                ) 
                ORDER BY c1.iid;
            """
        else:  # ALL
            query = """
                SELECT DISTINCT c1.iid 
                FROM cell_lte c1
                WHERE c1.imported_at = (
                    SELECT MAX(imported_at) 
                    FROM cell_lte
                ) 
                UNION
                SELECT DISTINCT c2.iid 
                FROM cell_nr c2
                WHERE c2.imported_at = (
                    SELECT MAX(imported_at) 
                    FROM cell_nr
                )
                ORDER BY iid;
            """
        try:
            rows = await self._fetch_query(project_name, query, user_email)
            return [row['iid'] for row in rows]
        except Exception as e:
            logger.warning(f"Warning: Could not fetch latest cell IIDs: {e}")
            return []
    
    async def get_latest_location_names(self, project_name: str, user_email: str):
        """Get only location IIDs from the most recent import batch."""
        query = """
            SELECT DISTINCT l1.iid 
            FROM location l1
            WHERE l1.imported_at = (
                SELECT MAX(imported_at) 
                FROM location
            ) 
            ORDER BY l1.iid;
        """
        try:
            rows = await self._fetch_query(project_name, query, user_email)
            return [row['iid'] for row in rows]
        except Exception as e:
            logger.warning(f"Warning: Could not fetch latest location IIDs: {e}")
            return []

    async def get_cell_names_by_names(self, project_name: str, cell_names, user_email: str, technology: Technology = Technology.ALL):
        """Get valid cell IIDs from provided names (based on technology filter)."""
        if not cell_names: return []
        from security.encryption.iid_hash_utils import normalize_to_db_value
        string_names = [normalize_to_db_value(str(name)) for name in cell_names]
        
        if technology == Technology.LTE:
            query_iid = """
                SELECT DISTINCT c1.iid 
                FROM cell_lte c1
                WHERE (
                    c1.iid = ANY($1::text[])
                    OR c1.eid::text = ANY($1::text[])
                ) 
                AND c1.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                ORDER BY c1.iid;
            """
        elif technology == Technology.NR:
            query_iid = """
                SELECT DISTINCT c1.iid 
                FROM cell_nr c1
                WHERE (
                    c1.iid = ANY($1::text[])
                    OR c1.eid::text = ANY($1::text[])
                ) 
                AND c1.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                ORDER BY c1.iid;
            """
        else:  # ALL
            query_iid = """
                SELECT DISTINCT c1.iid 
                FROM cell_lte c1
                WHERE (
                    c1.iid = ANY($1::text[])
                    OR c1.eid::text = ANY($1::text[])
                ) 
                AND c1.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                UNION
                SELECT DISTINCT c2.iid 
                FROM cell_nr c2
                WHERE c2.iid = ANY($1::text[]) 
                AND c2.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                ORDER BY iid;
            """
        try:
            rows = await self._fetch_query(project_name, query_iid, user_email, (string_names,))
            names = [row['iid'] for row in rows]
            return names
        except Exception:
            return []
    
    async def get_location_names_by_names(self, project_name: str, location_names, user_email: str):
        """Get valid location IIDs from provided names (matches iid OR address1)"""
        if not location_names: return []
        from security.encryption.iid_hash_utils import normalize_to_db_value
        original_names = [str(name) for name in location_names]
        hashed_names = [normalize_to_db_value(name) for name in original_names]
        # Match hashed iid OR original address1 (address1 is not hashed)
        query = """
            SELECT DISTINCT l1.iid
            FROM location l1
            WHERE (l1.iid = ANY($1::text[]) OR l1.address1 = ANY($2::text[]))
            AND l1.imported_at = (SELECT MAX(imported_at) FROM location)
            ORDER BY l1.iid;
        """
        try:
            rows = await self._fetch_query(project_name, query, user_email, (hashed_names, original_names))
            return [row['iid'] for row in rows]
        except Exception:
            return []
    
    async def get_location_names_by_region(self, project_name: str, region_values, user_email: str):
        """Get location IIDs by searching across address fields"""
        if not region_values: return []
        query = """
            SELECT DISTINCT l1.iid 
            FROM location l1
            WHERE (l1.address1 ILIKE ANY($1::text[]) OR l1.town ILIKE ANY($2::text[])
               OR l1.postcode ILIKE ANY($3::text[]) OR l1.state ILIKE ANY($4::text[]))
            AND l1.imported_at = (SELECT MAX(imported_at) FROM location);
        """
        like_patterns = [f"%{value}%" for value in region_values]
        try:
            rows = await self._fetch_query(project_name, query, user_email, (like_patterns, like_patterns, like_patterns, like_patterns))
            return [row['iid'] for row in rows]
        except Exception:
            return []
    
    async def get_cell_names_by_region(self, project_name: str, region_values, user_email: str, technology: Technology = Technology.ALL):
        """Get cell IIDs by searching across location fields (based on technology filter)"""
        if not region_values: return []
        like_patterns = [f"%{value}%" for value in region_values]
        
        if technology == Technology.LTE:
            query = """
                SELECT DISTINCT c1.iid 
                FROM cell_lte c1 JOIN location l1 ON c1.location_eid = l1.eid
                WHERE (l1.address1 ILIKE ANY($1::text[]) OR l1.town ILIKE ANY($2::text[])
                   OR l1.postcode ILIKE ANY($3::text[]) OR l1.state ILIKE ANY($4::text[]))
                AND c1.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                AND l1.imported_at = (SELECT MAX(l2.imported_at) FROM location l2 WHERE l2.eid = l1.eid);
            """
        elif technology == Technology.NR:
            query = """
                SELECT DISTINCT c1.iid 
                FROM cell_nr c1 JOIN location l1 ON c1.location_eid = l1.eid
                WHERE (l1.address1 ILIKE ANY($1::text[]) OR l1.town ILIKE ANY($2::text[])
                   OR l1.postcode ILIKE ANY($3::text[]) OR l1.state ILIKE ANY($4::text[]))
                AND c1.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                AND l1.imported_at = (SELECT MAX(l2.imported_at) FROM location l2 WHERE l2.eid = l1.eid);
            """
        else:  # ALL
            query = """
                SELECT DISTINCT c1.iid 
                FROM cell_lte c1 JOIN location l1 ON c1.location_eid = l1.eid
                WHERE (l1.address1 ILIKE ANY($1::text[]) OR l1.town ILIKE ANY($2::text[])
                   OR l1.postcode ILIKE ANY($3::text[]) OR l1.state ILIKE ANY($4::text[]))
                AND c1.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                AND l1.imported_at = (SELECT MAX(l2.imported_at) FROM location l2 WHERE l2.eid = l1.eid)
                UNION
                SELECT DISTINCT c2.iid 
                FROM cell_nr c2 JOIN location l2 ON c2.location_eid = l2.eid
                WHERE (l2.address1 ILIKE ANY($1::text[]) OR l2.town ILIKE ANY($2::text[])
                   OR l2.postcode ILIKE ANY($3::text[]) OR l2.state ILIKE ANY($4::text[]))
                AND c2.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                AND l2.imported_at = (SELECT MAX(l3.imported_at) FROM location l3 WHERE l3.eid = l2.eid);
            """
        try:
            rows = await self._fetch_query(project_name, query, user_email, (like_patterns, like_patterns, like_patterns, like_patterns))
            return [row['iid'] for row in rows]
        except Exception:
            return []

    async def get_cell_names_by_location_iids(self, project_name: str, location_iids: List[str], user_email: str, technology: Technology = Technology.ALL):
        """Get cell IIDs from provided location IIDs (based on technology filter)"""
        if not location_iids: return []
        string_iids = [str(iid) for iid in location_iids]
        
        if technology == Technology.LTE:
            query = """
                SELECT DISTINCT c1.iid 
                FROM cell_lte c1 JOIN location l1 ON c1.location_eid = l1.eid
                WHERE l1.iid = ANY($1::text[])
                AND c1.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                AND l1.imported_at = (SELECT MAX(l2.imported_at) FROM location l2 WHERE l2.eid = l1.eid)
                ORDER BY c1.iid;
            """
        elif technology == Technology.NR:
            query = """
                SELECT DISTINCT c1.iid 
                FROM cell_nr c1 JOIN location l1 ON c1.location_eid = l1.eid
                WHERE l1.iid = ANY($1::text[])
                AND c1.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                AND l1.imported_at = (SELECT MAX(l2.imported_at) FROM location l2 WHERE l2.eid = l1.eid)
                ORDER BY c1.iid;
            """
        else:  # ALL
            query = """
                SELECT DISTINCT c1.iid 
                FROM cell_lte c1 JOIN location l1 ON c1.location_eid = l1.eid
                WHERE l1.iid = ANY($1::text[])
                AND c1.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                AND l1.imported_at = (SELECT MAX(l2.imported_at) FROM location l2 WHERE l2.eid = l1.eid)
                UNION
                SELECT DISTINCT c2.iid 
                FROM cell_nr c2 JOIN location l2 ON c2.location_eid = l2.eid
                WHERE l2.iid = ANY($1::text[])
                AND c2.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                AND l2.imported_at = (SELECT MAX(l3.imported_at) FROM location l3 WHERE l3.eid = l2.eid)
                ORDER BY iid;
            """
        try:
            rows = await self._fetch_query(project_name, query, user_email, (string_iids,))
            return [row['iid'] for row in rows]
        except Exception as e:
            logger.warning(f"Warning: Could not fetch cell IIDs by location IIDs: {e}")
            return []
            
    async def _resolve_entity_names(self, entity_type_str: str, project_name: str, names: list, region: list, all_flag: bool, user_email: str, technology: Technology = Technology.ALL) -> tuple[List[str], Technology]:
        """Unified method to resolve entity names (IIDs) based on provided filters.
        Returns tuple of (entity_names, detected_technology) where detected_technology is the actual technology
        of the cells found (LTE, NR, or ALL if mixed or technology was explicitly set to ALL)."""
        entity_names = []
        detected_tech = technology  # Default to provided technology
        
        if entity_type_str == EntityType.CELL:
            if all_flag:
                found_names = await self.get_latest_cell_names(project_name, user_email, technology)
                entity_names.extend(found_names)
            if names:
                found_names = await self.get_cell_names_by_names(project_name, names, user_email, technology)
                entity_names.extend(found_names)
            if region:
                found_names = await self.get_cell_names_by_region(project_name, region, user_email, technology)
                entity_names.extend(found_names)
            
            # Auto-detect technology if ALL was specified and we have specific cells
            if technology == Technology.ALL and entity_names:
                # Check which table(s) the cells are actually in
                lte_cells = await self.get_cell_names_by_names(project_name, entity_names, user_email, Technology.LTE)
                nr_cells = await self.get_cell_names_by_names(project_name, entity_names, user_email, Technology.NR)
                
                if lte_cells and not nr_cells:
                    detected_tech = Technology.LTE
                    logger.info(f"Auto-detected technology: LTE (found {len(lte_cells)} LTE cells)")
                elif nr_cells and not lte_cells:
                    detected_tech = Technology.NR
                    logger.info(f"Auto-detected technology: NR (found {len(nr_cells)} NR cells)")
                elif lte_cells and nr_cells:
                    # Mixed - keep as ALL
                    logger.info(f"Mixed technology: found {len(lte_cells)} LTE and {len(nr_cells)} NR cells")
                # If neither found, keep as ALL (might be empty result)
        
        elif entity_type_str == EntityType.SITE:
            if all_flag:
                entity_names.extend(await self.get_latest_location_names(project_name, user_email))
            if names:
                entity_names.extend(await self.get_location_names_by_names(project_name, names, user_email))
            if region:
                entity_names.extend(await self.get_location_names_by_region(project_name, region, user_email))
        
        return (list(set(entity_names)), detected_tech)  # deduplicate

    def _filter_functions_by_technology(self, functions: List, technology: Technology) -> List:
        """Filter audit functions based on technology (LTE, NR, or ALL)"""
        if technology == Technology.ALL:
            return functions
        
        filtered = []
        for func_class in functions:
            func_name = func_class.name.lower()
            if technology == Technology.LTE:
                # Include LTE functions (name ends with _lte) 
                # Exclude NR functions (name ends with _nr)
                if func_name.endswith('_lte') and not func_name.endswith('_nr'):
                    filtered.append(func_class)
            elif technology == Technology.NR:
                # Include NR functions (name ends with _nr)
                # Exclude LTE functions (name ends with _lte)
                if func_name.endswith('_nr') and not func_name.endswith('_lte'):
                    filtered.append(func_class)
        
        logger.info(f"Technology filter '{technology.value}': {len(functions)} functions -> {len(filtered)} filtered functions")
        return filtered

    @staticmethod
    def _should_include_cell_audit_in_report(name: str, data: dict, technology: Technology) -> bool:
        """Built-in cell rules are filtered by LTE/NR suffix; custom rules always show."""
        if technology == Technology.ALL:
            return True
        if data.get("is_custom"):
            return True
        func_name_lower = name.lower()
        if technology == Technology.LTE:
            return func_name_lower.endswith("_lte")
        if technology == Technology.NR:
            return func_name_lower.endswith("_nr")
        return True

    def _generate_summary_markdown(self, results: dict, technology: Technology) -> str:
        """Generate concise summary for LLM"""
        timestamp = results["audit_summary"].get("execution_timestamp", str(datetime.now()))
        total_rules = results["audit_summary"].get("total_rules_executed", 0)
        
        summary_markdown = f"# Audit Summary\n\n"
        summary_markdown += f"**Timestamp**: {timestamp}\n"
        summary_markdown += f"**Technology Filter**: {technology.value}\n"
        summary_markdown += f"**Total Rules**: {total_rules}\n\n"
        
        # Entities
        entities = results['audit_summary']['entities_audited']
        summary_markdown += "## Entities Audited\n"
        summary_markdown += f"- Cells: {entities.get('cells', 0)}\n"
        summary_markdown += f"- Sites: {entities.get('sites', 0)}\n\n"
        
        summary_markdown += "## Results\n"
        
        # Collect all summaries - Only show rules that were actually executed
        for key in ['cell_audits', 'site_audits']:
            if results.get(key):
                for name, data in results[key].items():
                    if key == "cell_audits" and not self._should_include_cell_audit_in_report(name, data, technology):
                        continue
                    
                    # All results come from AuditFunctionResult.to_dict()
                    # success=False means error occurred, summary/error always present
                    if data.get('success') is False:
                        summary_markdown += f"- ⚠️ {format_audit_label(name)}: Failed - {data['error']}\n"
                    else:
                        summary_markdown += f"- {data['summary']}\n"
        
        return summary_markdown

    def _generate_detailed_markdown(self, results: dict, technology: Technology) -> str:
        """Combine markdown from all executed functions"""
        timestamp = results["audit_summary"].get("execution_timestamp", str(datetime.now()))
        total_rules = results["audit_summary"].get("total_rules_executed", 0)
        
        combined_markdown = f"# Network Infrastructure Audit Report\n\n"
        combined_markdown += f"**Generated at**: {timestamp}\n\n"
        combined_markdown += f"**Technology Filter**: {technology.value}\n\n"
        combined_markdown += f"**Total audit rules executed**: {total_rules}\n\n"
        
        # Table of Contents
        combined_markdown += "## Table of Contents\n\n"
        # combined_markdown += "1. [Executive Summary](#executive-summary)\n"
        # combined_markdown += "2. [Entities Audited](#entities-audited)\n"
        combined_markdown += "1. Executive Summary\n"
        combined_markdown += "2. Entities Audited\n"
        
        section_num = 3
        if results.get('cell_audits'):
            # combined_markdown += f"{section_num}. [Cell Infrastructure Analysis](#cell-infrastructure-analysis)\n"
            combined_markdown += f"{section_num}. Cell Infrastructure Analysis\n"
            section_num += 1
        if results.get('site_audits'):
            # combined_markdown += f"{section_num}. [Site Infrastructure Analysis](#site-infrastructure-analysis)\n"
            combined_markdown += f"{section_num}. Site Infrastructure Analysis\n"
        
        combined_markdown += "\n"
        
        # Executive Summary
        combined_markdown += "## Executive Summary\n\n"
        combined_markdown += "This comprehensive audit report provides a detailed analysis of your network infrastructure. "
        combined_markdown += "The audit examines compliance with established standards and identifies potential issues.\n\n"
        
        # Entities Audited
        entities = results['audit_summary']['entities_audited']
        if any(entities.values()):
            combined_markdown += "## Entities Audited\n\n"
            combined_markdown += "| Entity Type | Count | Description |\n"
            combined_markdown += "|-------------|-------|-------------|\n"
            for entity_type, count in entities.items():
                if count > 0:
                    combined_markdown += f"| **{entity_type.title()}** | {count} | {entity_type.title()} entities analyzed |\n"
            combined_markdown += "\n"
        
        # Cell Audits - Only show rules that were actually executed
        if results.get('cell_audits'):
            combined_markdown += "## Cell Infrastructure Analysis\n\n"
            # Filter by technology to ensure only relevant rules are shown
            for name, data in results['cell_audits'].items():
                if not self._should_include_cell_audit_in_report(name, data, technology):
                    continue
                
                # All results come from AuditFunctionResult.to_dict()
                # success=False means error occurred, md_data is just "Error: {msg}"
                if data.get('success') is False:
                    combined_markdown += f"### {format_audit_label(name)} (Failed)\n\n"
                    combined_markdown += f"❌ **Error executing audit**: {data['error']}\n\n---\n"
                else:
                    combined_markdown += data['md_data'] + "\n---\n"
        
        # Site Audits - Only show rules that were actually executed
        if results.get('site_audits'):
            combined_markdown += "## Site Infrastructure Analysis\n\n"
            for name, data in results['site_audits'].items():
                # All results come from AuditFunctionResult.to_dict()
                if data.get('success') is False:
                    combined_markdown += f"### {format_audit_label(name)} (Failed)\n\n"
                    combined_markdown += f"❌ **Error executing audit**: {data['error']}\n\n---\n"
                else:
                    combined_markdown += data['md_data'] + "\n---\n"
        
        return combined_markdown

    async def execute(self, project_name: str, audit_execute_for: List[str], user_email: str, all: bool = False, cells: List[str] = [], sites: List[str] = [], region: List[str] = [], technology: str = "ALL") -> ToolOutput:
        """
        Execute audit engine with specified parameters.
        """
        logger.info("[AUDIT_ENGINE] Starting audit engine execution")

        # Parse technology filter
        try:
            tech_filter = Technology(technology.upper())
        except ValueError:
            tech_filter = Technology.ALL
            logger.warning(f"Invalid technology '{technology}', defaulting to ALL")

        # Fallback: if no entities provided, audit ALL of the specified technology.
        if not all and not cells and not sites and not region:
            all = True
            logger.info(f"[AUDIT_ENGINE] No entities and no shared filter — auto-setting all=True (technology={tech_filter.value})")

        stream_writer: StreamWriter = get_stream_writer()
        stream_writer({"step": "1/9", "status": "started", "message": f"Initializing audit results (Technology: {tech_filter.value})"})
        # Initialize results
        # Track effective technology used (may be auto-detected for cells)
        effective_technology_for_cells = tech_filter
        audit_results = {
            "audit_summary": {
                "total_rules_executed": 0,
                "entities_audited": {"cells": 0, "sites": 0},
                "execution_timestamp": str(datetime.now()),
                "technology_filter": tech_filter.value,
                "effective_technology": tech_filter.value  # Will be updated if auto-detected
            },
            "cell_audits": {},
            "site_audits": {},
            "markdown": ""
        }
        stream_writer({"step": "2/9", "status": "started", "message": "Audit results initialized"})
        # Validate audit_execute_for
        valid_types = [EntityType.CELL, EntityType.SITE]
        target_types = []
        for t in audit_execute_for:
            if t in valid_types:
                target_types.append(t)
            else:
                logger.warning(f"Invalid entity type requested: {t}")
        
        # Auto-find cells within sites if cell audits are requested and sites are provided
        if EntityType.CELL in target_types and sites:
            stream_writer({"step": "2.5/9", "status": "started", "message": "Finding cells within provided sites"})
            # Resolve site IIDs first
            site_iids, _ = await self._resolve_entity_names(
                EntityType.SITE, project_name, sites, region, all, user_email, tech_filter
            )
            if site_iids:
                # Find cells within those sites
                cells_from_sites = await self.get_cell_names_by_location_iids(
                    project_name, site_iids, user_email, tech_filter
                )
                if cells_from_sites:
                    # Merge with explicitly provided cells (deduplicate)
                    cells = list(set(cells + cells_from_sites))
                    logger.info(f"Found {len(cells_from_sites)} cells within {len(site_iids)} sites, total cells to audit: {len(cells)}")
                    stream_writer({"step": "2.5/9", "status": "completed", "message": f"Found {len(cells_from_sites)} cells within {len(site_iids)} sites"})
                else:
                    logger.info(f"No cells found within {len(site_iids)} sites")
                    stream_writer({"step": "2.5/9", "status": "completed", "message": f"No cells found within {len(site_iids)} sites"})
        
        stream_writer({"step": "3/9", "status": "started", "message": "Resolving entity names"})
        rule_preferences = await load_rule_preferences(user_email, project_name)
        builtin_rule_configs = await load_builtin_rule_configs(user_email, project_name)
        for entity_type_str in target_types:
            entity_type = EntityType(entity_type_str)
            
            # Step 1: Resolve entity Names (IIDs) and auto-detect technology if needed
            names = cells if entity_type == EntityType.CELL else sites
            entity_names, detected_tech = await self._resolve_entity_names(
                entity_type_str, project_name, names, region, all, user_email, tech_filter
            )
            
            # Use detected technology for cell audits (auto-detected from actual cell data)
            effective_tech_filter = detected_tech if entity_type == EntityType.CELL else tech_filter
            # Update effective technology in results for cell audits
            if entity_type == EntityType.CELL:
                effective_technology_for_cells = effective_tech_filter
                audit_results["audit_summary"]["effective_technology"] = effective_tech_filter.value
            
            # Record count
            key_map = {EntityType.CELL: "cells", EntityType.SITE: "sites"}
            audit_results["audit_summary"]["entities_audited"][key_map[entity_type]] = len(entity_names)
            stream_writer({"step": "4/9", "status": "started", "message": f"Found {len(entity_names)} {entity_type_str}s to audit"})
            logger.info(f"Found {len(entity_names)} {entity_type_str}s to audit (Technology: {effective_tech_filter.value})")
            
            # Step 2: Determine category
            count = len(entity_names)
            category = self.config.category_config.get_category(count)
            logger.info(f"Audit Category for {entity_type_str}: {category}")
            
            if category == AuditCategory.NONE:
                continue
            
            # Step 3: Get functions
            functions = audit_function_registry.get_functions(entity_type, category)

            # Step 3.25: Filter by user enable/disable preferences
            functions = [
                fc for fc in functions
                if is_rule_enabled(fc.name, rule_preferences)
            ]
            
            # Step 3.5: Filter functions by technology (only for CELL audits)
            if entity_type == EntityType.CELL:
                functions = self._filter_functions_by_technology(functions, effective_tech_filter)
            
            stream_writer({"step": "5/9", "status": "started", "message": f"Getting {len(functions)} functions for {entity_type_str} (Tech: {effective_tech_filter.value})"})
            logger.info(f"Getting {len(functions)} functions for {entity_type_str} (Technology: {effective_tech_filter.value})")
            
            # Step 4: Execute functions concurrently for speed (with streaming progress)
            audit_key = f"{entity_type_str}_audits"

            async def _run_audit_func(index: int, func_class):
                """Run a single audit function with error handling."""
                try:
                    stream_writer({"step": f"5.{index + 1}/9", "status": "running", "message": f"Executing {func_class.name} for {entity_type_str}"})
                    user_config = builtin_rule_configs.get(func_class.name)
                    func_instance = func_class(self.db_manager, rule_config=user_config)
                    result = await func_instance.execute(project_name, entity_names, user_email)
                    return func_instance.name, result.to_dict(), result.success
                except Exception as e:
                    logger.error(f"Error executing {func_class.name}: {e}")
                    return func_class.name, {
                        "summary": f"Error in {func_class.name}",
                        "md_data": f"Error: {str(e)}",
                        "error": str(e),
                        "success": False,
                        "raw_data": None,
                        "stats": None
                    }, False

            results = await asyncio.gather(*[_run_audit_func(i + 1, fc) for i, fc in enumerate(functions)])
            executed_count = 0
            for func_name, result_dict, success in results:
                audit_results[audit_key][func_name] = result_dict
                executed_count += 1
                if success:
                    audit_results["audit_summary"]["total_rules_executed"] += 1

            # Step 4.5: Execute enabled custom rules (DETAILED/MODERATE only)
            custom_rules = await load_enabled_custom_rules(
                user_email, project_name, entity_type.value, category, rule_preferences
            )
            logger.info(
                f"Loaded {len(custom_rules)} enabled custom rules for {entity_type_str} "
                f"(category={category.value}, user={user_email})"
            )
            if custom_rules:
                stream_writer({
                    "step": "6/9",
                    "status": "running",
                    "message": f"Executing {len(custom_rules)} custom rules for {entity_type_str}",
                })

                async def _run_custom_rule(index: int, rule):
                    try:
                        executor = CustomAuditRuleExecutor(self.db_manager, rule)
                        stream_writer({
                            "step": f"6.{index + 1}/9",
                            "status": "running",
                            "message": f"Executing custom rule {rule.name} for {entity_type_str}",
                        })
                        result = await executor.execute(project_name, entity_names, user_email)
                        return executor.name, result.to_dict(), result.success, rule.name
                    except Exception as e:
                        logger.error(f"Error executing custom rule {rule.id}: {e}")
                        key = f"custom:{rule.id}"
                        return key, {
                            "summary": f"Error in {rule.name}",
                            "md_data": f"Error: {str(e)}",
                            "error": str(e),
                            "success": False,
                            "raw_data": None,
                            "stats": None,
                        }, False, rule.name

                custom_results = await asyncio.gather(
                    *[_run_custom_rule(i + 1, rule) for i, rule in enumerate(custom_rules)]
                )
                for func_name, result_dict, success, display_name in custom_results:
                    result_dict["is_custom"] = True
                    audit_results[audit_key][display_name] = result_dict
                    executed_count += 1
                    if success:
                        audit_results["audit_summary"]["total_rules_executed"] += 1

            logger.info(f"Executed {executed_count} functions for {entity_type_str} (Technology: {effective_tech_filter.value})")
            stream_writer({"step": "6/9", "status": "running", "message": f"Executing {len(functions)} functions for {entity_type_str}"})
        stream_writer({"step": "7/9", "status": "running", "message": "Generating detailed markdown"})
        # Step 5: Generate Report
        # Use effective technology (auto-detected) for report generation
        effective_tech_for_report = Technology(audit_results["audit_summary"].get("effective_technology", tech_filter.value))
        detailed_md = self._generate_detailed_markdown(audit_results, effective_tech_for_report)
        summary_md = self._generate_summary_markdown(audit_results, effective_tech_for_report)

        # Reverse-map hashed IIDs in final markdown output
        detailed_md = await self._reverse_map_markdown(detailed_md, project_name)
        summary_md = await self._reverse_map_markdown(summary_md, project_name)

        stream_writer({"step": "8/9", "status": "running", "message": "Generating summary markdown"})
        stream_writer({"step": "9/9", "status": "completed", "message": "Audit engine execution completed successfully"})
        logger.info("✅ Audit Engine execution completed successfully")

        return ToolOutput(
            status=True,
            data=summary_md,
            md_data=detailed_md,
            is_summary_available=True
        )


# Factory function for tool creation
def create_audit_engine_tool(config=None, db_manager: Optional[DynamicAsyncDatabaseManager] = None):
    """Create audit engine tool with dependencies."""
    engine = AuditEngine(config, db_manager)

    from db_agent_v2.tools.base import DataRef

    class AuditEngineArgs(BaseModel):
        audit_execute_for: List[str] = Field(description='Entity types to audit. Accepted values: ["cell"], ["site"], or ["cell", "site"] for both.')
        all: bool = Field(default=False, description="If true, audit ALL entities in the entire project. MUTUALLY EXCLUSIVE with data_refs, cells, sites — do NOT set all=True when using data_refs or providing specific cells/sites.")
        cells: List[str] = Field(default_factory=list, description="Specific Cell IIDs/names to audit. Only use when the user provides cell names directly. Do NOT use when using data_refs.")
        sites: List[str] = Field(default_factory=list, description="Site IIDs/names. For cell audits: the engine auto-finds all cells on these sites. For site audits: audits the sites directly.")
        regions: List[str] = Field(default_factory=list, description="Region name filters (matches address, town, state, postcode fields). E.g. ['London', 'Region_North'].")
        technology: str = Field(default="ALL", description='Technology filter: "LTE" (4G only), "NR" (5G only), or "ALL" (both). Default is "ALL".')
        data_refs: Optional[List[DataRef]] = Field(default=None, description="References to columns from the most recent asset_db_rag_tool output. Use this to pass cell/site identifiers from the last RAG query result. When data_refs is provided, do NOT set all=True and do NOT manually fill cells/sites — the system resolves values automatically.")

    @tool("audit_engine_tool", args_schema=AuditEngineArgs, parse_docstring=False)
    async def audit_engine_tool(
        project_name: Annotated[str, InjectedState("project_name")],
        user_email: Annotated[str, InjectedToolArg],
        audit_execute_for: List[str] = [],
        all: bool = False,
        cells: Optional[List[str]] = None,
        sites: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
        technology: str = "ALL",
        data_refs: Optional[List] = None,
    ) -> ToolOutput:
        """
        Run a comprehensive audit on network infrastructure entities (Cells/Sites).
        any one or multiple of the Args must be provided to filter the entities and then an audit is performed.

        ## How the tool works [Summary]
        This tool executes a suite of pre-defined validation rules against the selected network entities.
        1) Resolves target entities (cells/sites) based on filters (all, cells, sites, region)
        2) Determines audit category based on entity count (to select appropriate audit functions)
        3) Filters audit functions by technology (LTE/NR/ALL) for cell audits
        4) Executes registered audit functions (e.g., antenna tilt checks, PCI conflicts) from a function registry
        5) Aggregates results into a detailed Markdown report with statistics and compliance summaries
        -  detailed information about the tool and how it works is available at [Audit Engine Documentation](https://www.notion.so/bimandas/What-Next-AANA-2c3bb91a7a9780bd837fe70264ebf791)

        ## Capabilities
        -   **Health Checks**: Validate data integrity and compliance with network design rules.
        -   **Scope Flexibility**: Audit a single cell, a specific region, or the entire network.
        -   **Multi-Entity**: Supports both 'cell' and 'site' level audits.
        -   **Technology Filtering**: Filter cell audits by LTE (4G), NR (5G), or ALL technologies.

        ## When to use
        -   When the user asks to "check", "audit", or "validate" the network.
        -   When investigating reported issues in a specific area.
        -   When user wants to audit only LTE (4G) or NR (5G) cells specifically.
        -   **NOT** for simple data retrieval (use `asset_db_rag_tool`).
        -   **NOT** for checking OSS vs DB differences (use `discrepancy_engine_tool`)

        ## IMPORTANT — Choosing the right arguments:
        - `all` and `data_refs` are MUTUALLY EXCLUSIVE. Never use both together.
        - **To audit cells from the most recent RAG query** (e.g., "audit those cells", "audit the cells with azimuth=0"): use `data_refs` to reference the most recent asset_db_rag_tool result. Do NOT set `all=True`. Do NOT manually copy cell names.
        - **To audit ALL cells in the project**: use `all=True`. Do NOT provide `data_refs`, `cells`, or `sites`.
        - **To audit all cells on a specific site** (e.g., "audit cells of site X"): use `audit_execute_for=["cell"], sites=["site_name"]`. The engine auto-finds all cells on that site.
        - To audit specific cells by name: use `cells=["cell_name_1", "cell_name_2"]` — only when the user provides specific cell names directly.
        - **To audit a site itself** (site-level checks): use `audit_execute_for=["site"], sites=["site_name"]`.
        - **To audit both site AND its cells**: use `audit_execute_for=["cell", "site"], sites=["site_name"]`.
        - Even if there is only one entity, pass it as a list.
        """
        return await engine.execute(project_name, audit_execute_for, user_email, all, cells or [], sites or [], regions or [], technology)
    return audit_engine_tool
