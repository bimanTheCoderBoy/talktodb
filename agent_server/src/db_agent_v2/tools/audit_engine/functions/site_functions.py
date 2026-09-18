from typing import List, Dict, Any, Optional
from ..base import BaseAuditFunction, AuditFunctionResult, EntityType, AuditCategory
from ..registry import audit_function_registry
from ..configurable_apply import (
    build_site_high_level_markdown,
    evaluate_configurable_rule,
    filter_high_level_stats_dict,
)
from .helpers import (
    generate_generic_markdown,
    calculate_pass_fail_stats,
    calculate_configured_stats,
)


@audit_function_registry.register
class BeamformingSupportByLocation(BaseAuditFunction):
    name = "beamforming_support" 
    description = "Beamforming Support by Location"
    entity_types = [EntityType.SITE]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE, AuditCategory.SUMMARY]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT 
                       loc.iid AS "Site Name",
                       COUNT(DISTINCT COALESCE(c_lte.iid, c_nr.iid)) AS num_cells,
                       CASE 
                           WHEN SUM(CASE WHEN l.singlebeamenabled = TRUE THEN 1 ELSE 0 END) > 0
                           THEN 'Yes' 
                           ELSE 'No' 
                       END AS beamforming_support
                FROM location loc
                LEFT JOIN cell_lte c_lte 
                    ON loc.iid = c_lte.location_iid
                    AND c_lte.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                LEFT JOIN cell_nr c_nr 
                    ON loc.iid = c_nr.location_iid
                    AND c_nr.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                LEFT JOIN cell_logical_antenna l 
                    ON (l.cell_iid = c_lte.iid OR l.cell_iid = c_nr.iid)
                WHERE loc.iid = ANY($1::text[])
                AND loc.imported_at = (SELECT MAX(imported_at) FROM location)
                GROUP BY loc.iid
                HAVING COUNT(DISTINCT COALESCE(c_lte.iid, c_nr.iid)) > 0;
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            
            config = self.get_config()
            rows, stats = evaluate_configurable_rule(self.name, config, rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Beamforming (Sites): {stats['yes']}/{stats['total']} sites beamforming compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class AntennasOnLocation(BaseAuditFunction):
    name = "antennas_on_location"
    description = "Antennas per Location"
    entity_types = [EntityType.SITE]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT
                       loc.iid AS "Site Name",
                       l.logical_eid AS logical_antenna_id,
                       p.antennadevice_eid AS physical_antenna_id
                FROM location loc
                LEFT JOIN cell_logical_antenna l ON loc.eid = l.location_eid
                LEFT JOIN cell_physical_antenna p ON loc.eid = p.location_eid
                WHERE loc.iid = ANY($1::text[])
                AND loc.imported_at = (SELECT MAX(imported_at) FROM location)
                ORDER BY loc.iid;
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            stats = {"total": len(rows)}
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Antennas on Location: Analyzed {len(rows)} records",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class LteTacAudit(BaseAuditFunction):
    name = "lte_tac"
    description = "LTE TAC per Location"
    entity_types = [EntityType.SITE]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE, AuditCategory.SUMMARY]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT
                       loc.iid AS "Site Name",
                       c.iid AS "Cell Name",
                       c.lte_tac
                FROM location loc
                LEFT JOIN cell_lte c ON loc.eid = c.location_eid
                WHERE loc.iid = ANY($1::text[])
                AND loc.imported_at = (SELECT MAX(imported_at) FROM location)
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                ORDER BY loc.iid, c.iid;
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            stats = calculate_configured_stats(rows, ["lte_tac"])
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"LTE TAC: {stats['yes']}/{stats['total']} records have TAC configured",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class NrTacAudit(BaseAuditFunction):
    name = "nr_tac"
    description = "5G NR TAC per Location"
    entity_types = [EntityType.SITE]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE, AuditCategory.SUMMARY]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT
                       loc.iid AS "Site Name",
                       c.iid AS "Cell Name",
                       c.nrt_tac
                FROM location loc
                LEFT JOIN cell_nr c ON loc.eid = c.location_eid
                WHERE loc.iid = ANY($1::text[])
                AND loc.imported_at = (SELECT MAX(imported_at) FROM location)
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                ORDER BY loc.iid, c.iid;
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            stats = calculate_configured_stats(rows, ["nrt_tac"])
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"NR TAC: {stats['yes']}/{stats['total']} records have TAC configured",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class SiteHighLevelStats(BaseAuditFunction):
    name = "site_high_level_stats"
    description = "High level statistics for large site populations"
    entity_types = [EntityType.SITE]
    categories = [AuditCategory.AGGREGATED, AuditCategory.STATISTICS]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            # Optimized: Use separate simpler queries instead of complex JOINs
            # This is much faster for large datasets
            
            # Base count query
            base_query = """
                SELECT COUNT(DISTINCT loc.eid) AS total_sites
                FROM location loc
                WHERE loc.iid = ANY($1::text[])
                AND loc.imported_at = (SELECT MAX(imported_at) FROM location);
            """
            base_rows = await self._fetch_query(project_name, base_query, user_email, (entity_names,))
            total = base_rows[0].get('total_sites', 0) if base_rows else 0
            
            # Cell counts (simpler aggregation)
            cell_query = """
                SELECT 
                    COUNT(DISTINCT c_lte.iid) AS lte_cells,
                    COUNT(DISTINCT c_nr.iid) AS nr_cells
                FROM location loc
                LEFT JOIN cell_lte c_lte 
                    ON loc.iid = c_lte.location_iid
                    AND c_lte.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                LEFT JOIN cell_nr c_nr 
                    ON loc.iid = c_nr.location_iid
                    AND c_nr.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                WHERE loc.iid = ANY($1::text[])
                AND loc.imported_at = (SELECT MAX(imported_at) FROM location);
            """
            cell_rows = await self._fetch_query(project_name, cell_query, user_email, (entity_names,))
            lte_cells = cell_rows[0].get('lte_cells', 0) if cell_rows else 0
            nr_cells = cell_rows[0].get('nr_cells', 0) if cell_rows else 0
            total_cells = lte_cells + nr_cells
            
            # Beamforming support (using EXISTS for better performance)
            beamforming_query = """
                SELECT COUNT(DISTINCT loc.eid) AS beamforming_supported
                FROM location loc
                WHERE loc.iid = ANY($1::text[])
                AND loc.imported_at = (SELECT MAX(imported_at) FROM location)
                AND (
                    EXISTS (
                        SELECT 1 FROM cell_lte c
                        WHERE c.location_iid = loc.iid
                        AND c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                        AND EXISTS (
                            SELECT 1 FROM cell_logical_antenna l 
                            WHERE l.cell_iid = c.iid 
                            AND l.singlebeamenabled = TRUE
                        )
                    )
                    OR EXISTS (
                        SELECT 1 FROM cell_nr c
                        WHERE c.location_iid = loc.iid
                        AND c.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                        AND EXISTS (
                            SELECT 1 FROM cell_logical_antenna l 
                            WHERE l.cell_iid = c.iid 
                            AND l.singlebeamenabled = TRUE
                        )
                    )
                );
            """
            beamforming_rows = await self._fetch_query(project_name, beamforming_query, user_email, (entity_names,))
            beamforming = beamforming_rows[0].get('beamforming_supported', 0) if beamforming_rows else 0
            
            # Sites with antennas (using EXISTS)
            antennas_query = """
                SELECT COUNT(DISTINCT loc.eid) AS sites_with_antennas
                FROM location loc
                WHERE loc.iid = ANY($1::text[])
                AND loc.imported_at = (SELECT MAX(imported_at) FROM location)
                AND (
                    EXISTS (SELECT 1 FROM cell_logical_antenna l WHERE l.location_eid = loc.eid)
                    OR EXISTS (SELECT 1 FROM cell_physical_antenna p WHERE p.location_eid = loc.eid)
                );
            """
            antennas_rows = await self._fetch_query(project_name, antennas_query, user_email, (entity_names,))
            with_antennas = antennas_rows[0].get('sites_with_antennas', 0) if antennas_rows else 0
            
            # Sites with LTE TAC
            lte_tac_query = """
                SELECT COUNT(DISTINCT loc.eid) AS sites_with_lte_tac
                FROM location loc
                WHERE loc.iid = ANY($1::text[])
                AND loc.imported_at = (SELECT MAX(imported_at) FROM location)
                AND EXISTS (
                    SELECT 1 FROM cell_lte c
                    WHERE c.location_eid = loc.eid
                    AND c.lte_tac IS NOT NULL
                    AND c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                );
            """
            lte_tac_rows = await self._fetch_query(project_name, lte_tac_query, user_email, (entity_names,))
            with_lte_tac = lte_tac_rows[0].get('sites_with_lte_tac', 0) if lte_tac_rows else 0
            
            # Sites with NR TAC
            nr_tac_query = """
                SELECT COUNT(DISTINCT loc.eid) AS sites_with_nr_tac
                FROM location loc
                WHERE loc.iid = ANY($1::text[])
                AND loc.imported_at = (SELECT MAX(imported_at) FROM location)
                AND EXISTS (
                    SELECT 1 FROM cell_nr c
                    WHERE c.location_eid = loc.eid
                    AND c.nrt_tac IS NOT NULL
                    AND c.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                );
            """
            nr_tac_rows = await self._fetch_query(project_name, nr_tac_query, user_email, (entity_names,))
            with_nr_tac = nr_tac_rows[0].get('sites_with_nr_tac', 0) if nr_tac_rows else 0
            
            # Combine results
            rows = [{
                'total_sites': total,
                'beamforming_supported': beamforming,
                'sites_with_antennas': with_antennas,
                'sites_with_lte_tac': with_lte_tac,
                'sites_with_nr_tac': with_nr_tac,
                'total_cells': total_cells,
                'lte_cells': lte_cells,
                'nr_cells': nr_cells
            }]
            
            if total > 0:
                avg_cells_per_site = total_cells / total if total > 0 else 0
                
                stats = {
                    "total": total,
                    "beamforming_supported": beamforming,
                    "sites_with_antennas": with_antennas,
                    "sites_with_lte_tac": with_lte_tac,
                    "sites_with_nr_tac": with_nr_tac,
                    "total_cells": total_cells,
                    "lte_cells": lte_cells,
                    "nr_cells": nr_cells,
                    "avg_cells_per_site": avg_cells_per_site,
                }

                md_data = build_site_high_level_markdown(stats, self.get_config())
                stats = filter_high_level_stats_dict(stats, self.get_config())
                
                summary = f"High Level Stats: {total} sites - Beamforming: {beamforming}, Antennas: {with_antennas}, LTE TAC: {with_lte_tac}, NR TAC: {with_nr_tac}"
                
                return AuditFunctionResult(
                    summary=summary,
                    md_data=md_data,
                    raw_data=rows,
                    stats=stats
                )
            else:
                return AuditFunctionResult(
                    summary=f"High Level Stats: {len(entity_names)} sites analyzed",
                    md_data=f"### Site High Level Statistics\n\nNo data found for {len(entity_names)} sites.",
                    stats={"total": len(entity_names)}
                )
        except Exception as e:
            return AuditFunctionResult(
                summary=f"Error in {self.name}", 
                md_data=f"Error: {str(e)}", 
                error=str(e), 
                success=False
            )
