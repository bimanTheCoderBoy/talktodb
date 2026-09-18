from typing import List, Dict, Any, Optional
from ..base import BaseAuditFunction, AuditFunctionResult, EntityType, AuditCategory
from ..registry import audit_function_registry
from ..configurable_apply import (
    apply_configurable_or_default,
    build_cell_high_level_markdown,
    evaluate_configurable_rule,
    filter_high_level_stats_dict,
)
from .helpers import (
    generate_generic_markdown,
    calculate_configured_stats,
    calculate_status_stats,
    calculate_pass_fail_stats,
)


@audit_function_registry.register
class CarrierAssignmentAudit(BaseAuditFunction):
    name = "carrier_assignment_lte"
    description = "Analyzes carrier assignment (PCI) for 4G LTE cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", lte_carrierparameters_physicalcellid AS pci
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows, lambda r: calculate_configured_stats(r, ["pci"])
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Carrier Assignment (LTE): {stats['yes']}/{stats['total']} cells PCI compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class CarrierAggregationAudit(BaseAuditFunction):
    name = "carrier_aggregation_lte"
    description = "Checks whether the carrier aggregation (CA) parameter is configured per cell (TRUE/FALSE). NULL means not configured."
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", lte_carrierparameters_caenabledatcell
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name,
                config,
                rows,
                lambda r: calculate_configured_stats(r, ["lte_carrierparameters_caenabledatcell"]),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Carrier Aggregation (LTE): {stats['yes']}/{stats['total']} cells CA compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class SuMimoAudit(BaseAuditFunction):
    name = "su_mimo_lte"
    description = "Check if SU-MIMO is configured for uplink/downlink in 4G LTE cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", lte_sumimosupportdl, lte_sumimosupportul
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name,
                config,
                rows,
                lambda r: calculate_configured_stats(r, ["lte_sumimosupportdl", "lte_sumimosupportul"]),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"SU-MIMO (LTE): {stats['yes']}/{stats['total']} cells SU-MIMO compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class MuMimoAudit(BaseAuditFunction):
    name = "mu_mimo_lte"
    description = "Retrieve MU-MIMO terms assigned to a 4G LTE cell"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", lte_mumimosupportdl, lte_mumimosupportul,
                       lte_mumimotermsdl, lte_mumimotermsul
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name,
                config,
                rows,
                lambda r: calculate_configured_stats(
                    r,
                    ["lte_mumimosupportdl", "lte_mumimosupportul", "lte_mumimotermsdl", "lte_mumimotermsul"],
                ),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"MU-MIMO (LTE): {stats['yes']}/{stats['total']} cells MU-MIMO compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class RxTxElementsAudit(BaseAuditFunction):
    name = "rx_tx_elements_lte"
    description = "Get number of TX and RX elements for 4G LTE cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", lte_sumimotxelems, lte_sumimorxelems
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows, lambda r: calculate_configured_stats(r, ["lte_sumimotxelems", "lte_sumimorxelems"])
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"RX/TX Elements (LTE): {stats['yes']}/{stats['total']} cells RX/TX compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class BeamformingSupportAudit(BaseAuditFunction):
    name = "beamforming_support_lte"
    description = "Checks whether DL/UL beamforming support parameters are configured per cell (TRUE/FALSE). NULL means not configured."
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE, AuditCategory.SUMMARY]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", lte_beamformingsupportdl, lte_beamformingsupportul
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name,
                config,
                rows,
                lambda r: calculate_configured_stats(r, ["lte_beamformingsupportdl", "lte_beamformingsupportul"]),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Beamforming (LTE): {stats['yes']}/{stats['total']} cells beamforming compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class SignalThresholdsAudit(BaseAuditFunction):
    name = "signal_thresholds_lte"
    description = "Retrieve RSRP and SINR thresholds per 4G LTE cell"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", lte_carrierparameters_rsrpthreshold, lte_carrierparameters_sinrthreshold
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name,
                config,
                rows,
                lambda r: calculate_configured_stats(
                    r, ["lte_carrierparameters_rsrpthreshold", "lte_carrierparameters_sinrthreshold"]
                ),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Signal Thresholds (LTE): {stats['yes']}/{stats['total']} cells thresholds compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class CoverageRangeAudit(BaseAuditFunction):
    name = "coverage_range_lte"
    description = "Get estimated 4G LTE cell coverage range"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE, AuditCategory.SUMMARY]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", lte_carrierparameters_maxrange, lte_preamblecellrange_ro
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name,
                config,
                rows,
                lambda r: calculate_configured_stats(
                    r, ["lte_carrierparameters_maxrange", "lte_preamblecellrange_ro"]
                ),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Coverage Range (LTE): {stats['yes']}/{stats['total']} cells coverage range compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class InterferenceAudit(BaseAuditFunction):
    name = "interference_lte"
    description = "Find 4G LTE cells with high inter-tech interference"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", lte_carrierparameters_intertechinterference_nrnoiserisecellterm
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name,
                config,
                rows,
                lambda r: calculate_configured_stats(
                    r, ["lte_carrierparameters_intertechinterference_nrnoiserisecellterm"]
                ),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Interference (LTE): {stats['yes']}/{stats['total']} cells interference compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class CellLoadAudit(BaseAuditFunction):
    name = "cell_load_lte"
    description = "Retrieve average connected users and load for 4G LTE cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE, AuditCategory.SUMMARY]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name",
                       lte_carrierparameters_cellload_avgnumofconnusers,
                       lte_carrierparameters_cellload_cellcentredl,
                       lte_carrierparameters_cellload_celledgedl
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name,
                config,
                rows,
                lambda r: calculate_configured_stats(
                    r,
                    [
                        "lte_carrierparameters_cellload_avgnumofconnusers",
                        "lte_carrierparameters_cellload_cellcentredl",
                        "lte_carrierparameters_cellload_celledgedl",
                    ],
                ),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Cell Load (LTE): {stats['yes']}/{stats['total']} cells cell load compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class SecurityAudit(BaseAuditFunction):
    name = "security_audit_lte"
    description = "Check who last modified a 4G LTE cell"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", security_modifyuser, security_modifydate
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            stats = {"total": len(rows)}
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Security (LTE): Analyzed {len(rows)} cells",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class CoverageAndHeightAudit(BaseAuditFunction):
    name = "coverage_and_height_lte"
    description = "4G LTE Cell Coverage and Antenna Height"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE, AuditCategory.SUMMARY]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT 
                    c.iid AS "Cell Name",
                    l.primarymodel_radiuskm AS coverage_km,
                    p.height AS antenna_height_m
                FROM cell_lte c
                JOIN cell_logical_antenna l 
                    ON c.eid = l.cell_eid
                JOIN cell_physical_antenna p 
                    ON c.eid = p.cell_eid
                WHERE c.iid = ANY($1::text[])
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows, lambda r: calculate_configured_stats(r, ["coverage_km", "antenna_height_m"])
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Coverage & Height (LTE): {stats['yes']}/{stats['total']} cells coverage/height compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class AntennaOrientationAudit(BaseAuditFunction):
    name = "antenna_orientation_lte"
    description = "Antenna Orientation (Azimuth/Tilt) for 4G LTE cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT 
                    c.iid AS "Cell Name",
                    p.azimuth, 
                    p.tilt
                FROM cell_lte c
                JOIN cell_physical_antenna p 
                    ON c.eid = p.cell_eid
                WHERE c.iid = ANY($1::text[])
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows, lambda r: calculate_configured_stats(r, ["azimuth", "tilt"])
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Orientation (LTE): {stats['yes']}/{stats['total']} cells orientation compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class DowntiltComplianceAudit(BaseAuditFunction):
    name = "downtilt_compliance_lte"
    description = "Antenna Downtilt Compliance Check for 4G LTE cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE, AuditCategory.SUMMARY]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT ON (c.eid)
                    c.iid AS "Cell Name",
                    l.town AS location_name,
                    p.tilt AS current_tilt,
                    p.constraints_minmechanicaltilt_value AS min_allowed_tilt,
                    p.constraints_maxmechanicaltilt_value AS max_allowed_tilt,
                    CASE 
                        WHEN p.tilt BETWEEN 
                             COALESCE(p.constraints_minmechanicaltilt_value, 0) 
                             AND COALESCE(p.constraints_maxmechanicaltilt_value, 90) 
                        THEN 'Yes'
                        ELSE 'No'
                    END AS within_compliance
                FROM cell_lte c
                JOIN location l 
                    ON c.location_eid = l.eid
                LEFT JOIN cell_physical_antenna p 
                    ON c.eid = p.cell_eid
                WHERE c.iid = ANY($1::text[])
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                ORDER BY c.eid, p.imported_at DESC NULLS LAST;
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = evaluate_configurable_rule(self.name, config, rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Downtilt Compliance (LTE): {stats['yes']}/{stats['total']} cells compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class CellHighLevelStats(BaseAuditFunction):
    name = "cell_high_level_stats_lte"
    description = "High level statistics for large 4G LTE cell populations"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.AGGREGATED, AuditCategory.STATISTICS]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            # Try full query with all columns; fallback if any column missing in DB
            try:
                query = """
                    SELECT
                        COUNT(*) AS total_cells,
                        COUNT(CASE WHEN lte_eci IS NOT NULL THEN 1 END) AS eci_assigned,
                        COUNT(CASE WHEN lte_ecgi IS NOT NULL THEN 1 END) AS ecgi_assigned,
                        COUNT(CASE WHEN lte_tac IS NOT NULL THEN 1 END) AS tac_assigned,
                        COUNT(CASE WHEN lte_carrierparameters_physicalcellid IS NOT NULL THEN 1 END) AS carrier_assigned,
                        COUNT(CASE WHEN lte_firstassignedrsi IS NOT NULL THEN 1 END) AS rsi_assigned,
                        COUNT(CASE WHEN lte_carrierparameters_maxtxpower IS NOT NULL THEN 1 END) AS tx_power_configured,
                        COUNT(CASE WHEN lte_carrierparameters_referencesignalppre IS NOT NULL THEN 1 END) AS rs_power_configured,
                        COUNT(CASE WHEN lte_carrierparameters_bandwidth IS NOT NULL THEN 1 END) AS bandwidth_configured,
                        COUNT(CASE WHEN lte_carrierparameters_iid IS NOT NULL THEN 1 END) AS carrier_earfcn_configured,
                        COUNT(CASE WHEN lte_carrierparameters_caenabledatcell = TRUE THEN 1 END) AS carrier_aggregation_enabled,
                        COUNT(CASE WHEN lte_sumimosupportdl = TRUE OR lte_sumimosupportul = TRUE THEN 1 END) AS su_mimo_enabled,
                        COUNT(CASE WHEN lte_mumimosupportdl = TRUE OR lte_mumimosupportul = TRUE THEN 1 END) AS mu_mimo_enabled,
                        COUNT(CASE WHEN lte_beamformingsupportdl = TRUE OR lte_beamformingsupportul = TRUE THEN 1 END) AS beamforming_enabled,
                        COUNT(CASE WHEN lte_carrierparameters_maxrange IS NOT NULL OR lte_preamblecellrange_ro IS NOT NULL THEN 1 END) AS coverage_range_configured,
                        COUNT(CASE WHEN lte_carrierparameters_cellload_avgnumofconnusers IS NOT NULL THEN 1 END) AS cell_load_configured
                    FROM cell_lte
                    WHERE iid = ANY($1::text[])
                    AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
                """
                rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            except Exception:
                # Fallback: omit columns that may not exist (bandwidth, referencesignalppre, eci, ecgi)
                query = """
                    SELECT
                        COUNT(*) AS total_cells,
                        0 AS eci_assigned, 0 AS ecgi_assigned,
                        COUNT(CASE WHEN lte_tac IS NOT NULL THEN 1 END) AS tac_assigned,
                        COUNT(CASE WHEN lte_carrierparameters_physicalcellid IS NOT NULL THEN 1 END) AS carrier_assigned,
                        COUNT(CASE WHEN lte_firstassignedrsi IS NOT NULL THEN 1 END) AS rsi_assigned,
                        COUNT(CASE WHEN lte_carrierparameters_maxtxpower IS NOT NULL THEN 1 END) AS tx_power_configured,
                        0 AS rs_power_configured, 0 AS bandwidth_configured,
                        COUNT(CASE WHEN lte_carrierparameters_iid IS NOT NULL THEN 1 END) AS carrier_earfcn_configured,
                        COUNT(CASE WHEN lte_carrierparameters_caenabledatcell = TRUE THEN 1 END) AS carrier_aggregation_enabled,
                        COUNT(CASE WHEN lte_sumimosupportdl = TRUE OR lte_sumimosupportul = TRUE THEN 1 END) AS su_mimo_enabled,
                        COUNT(CASE WHEN lte_mumimosupportdl = TRUE OR lte_mumimosupportul = TRUE THEN 1 END) AS mu_mimo_enabled,
                        COUNT(CASE WHEN lte_beamformingsupportdl = TRUE OR lte_beamformingsupportul = TRUE THEN 1 END) AS beamforming_enabled,
                        COUNT(CASE WHEN lte_carrierparameters_maxrange IS NOT NULL OR lte_preamblecellrange_ro IS NOT NULL THEN 1 END) AS coverage_range_configured,
                        COUNT(CASE WHEN lte_carrierparameters_cellload_avgnumofconnusers IS NOT NULL THEN 1 END) AS cell_load_configured
                    FROM cell_lte
                    WHERE iid = ANY($1::text[])
                    AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
                """
                rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            
            # Downtilt compliance count (requires join)
            downtilt_query = """
                SELECT 
                    COUNT(DISTINCT c.eid) AS total_with_antenna,
                    COUNT(CASE 
                        WHEN p.tilt BETWEEN 
                             COALESCE(p.constraints_minmechanicaltilt_value, 0) 
                             AND COALESCE(p.constraints_maxmechanicaltilt_value, 90) 
                        THEN 1 
                    END) AS downtilt_compliant
                FROM cell_lte c
                LEFT JOIN cell_physical_antenna p ON c.eid = p.cell_eid
                WHERE c.iid = ANY($1::text[])
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                AND p.cell_eid IS NOT NULL;
            """
            downtilt_rows = await self._fetch_query(project_name, downtilt_query, user_email, (entity_names,))
            
            if rows and len(rows) > 0:
                row = rows[0]
                downtilt_row = downtilt_rows[0] if downtilt_rows else {}
                
                total = row.get('total_cells', 0)
                eci_assigned = row.get('eci_assigned', 0)
                ecgi_assigned = row.get('ecgi_assigned', 0)
                tac_assigned = row.get('tac_assigned', 0)
                carrier_assigned = row.get('carrier_assigned', 0)
                rsi_assigned = row.get('rsi_assigned', 0)
                tx_power = row.get('tx_power_configured', 0)
                rs_power = row.get('rs_power_configured', 0)
                bandwidth = row.get('bandwidth_configured', 0)
                carrier_earfcn = row.get('carrier_earfcn_configured', 0)
                carrier_agg = row.get('carrier_aggregation_enabled', 0)
                su_mimo = row.get('su_mimo_enabled', 0)
                mu_mimo = row.get('mu_mimo_enabled', 0)
                beamforming = row.get('beamforming_enabled', 0)
                coverage_range = row.get('coverage_range_configured', 0)
                cell_load = row.get('cell_load_configured', 0)
                downtilt_compliant = downtilt_row.get('downtilt_compliant', 0)
                total_with_antenna = downtilt_row.get('total_with_antenna', 0)

                stats = {
                    "total": total,
                    "eci_assigned": eci_assigned,
                    "ecgi_assigned": ecgi_assigned,
                    "tac_assigned": tac_assigned,
                    "carrier_assigned": carrier_assigned,
                    "rsi_assigned": rsi_assigned,
                    "tx_power_configured": tx_power,
                    "rs_power_configured": rs_power,
                    "bandwidth_configured": bandwidth,
                    "carrier_earfcn_configured": carrier_earfcn,
                    "carrier_aggregation_enabled": carrier_agg,
                    "su_mimo_enabled": su_mimo,
                    "mu_mimo_enabled": mu_mimo,
                    "beamforming_enabled": beamforming,
                    "coverage_range_configured": coverage_range,
                    "cell_load_configured": cell_load,
                    "downtilt_compliant": downtilt_compliant,
                    "total_with_antenna": total_with_antenna,
                }

                md_data = build_cell_high_level_markdown(stats, self.get_config(), tech_label="LTE")
                stats = filter_high_level_stats_dict(stats, self.get_config())

                summary = f"High Level Stats (LTE): {total} cells - ECI: {eci_assigned}, TAC: {tac_assigned}, PCI: {carrier_assigned}, RSI: {rsi_assigned}, TxPower: {tx_power}, BW: {bandwidth}, CA: {carrier_agg}"
                
                return AuditFunctionResult(
                    summary=summary,
                    md_data=md_data,
                    raw_data=rows,
                    stats=stats
                )
            else:
                return AuditFunctionResult(
                    summary=f"High Level Stats (LTE): {len(entity_names)} cells analyzed",
                    md_data=f"### Cell High Level Statistics (LTE)\n\nNo data found for {len(entity_names)} cells.",
                    stats={"total": len(entity_names)}
                )
        except Exception as e:
            return AuditFunctionResult(
                summary=f"Error in {self.name}",
                md_data=f"Error: {str(e)}",
                error=str(e),
                success=False
            )


@audit_function_registry.register
class NonCompliantCellsLTE(BaseAuditFunction):
    name = "non_compliant_cells_lte"
    description = "Sample of non-compliant LTE cells — shows top 20 cells per issue (missing PCI, TAC, Tx Power, tilt out of range, PCI collision/mod 3 counts on same band"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.AGGREGATED, AuditCategory.STATISTICS]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            # Get sample non-compliant cells for each key parameter (LIMIT 20 each)
            query = """
                (SELECT iid AS "Cell Name", 'Missing PCI' AS "Issue",
                        lte_carrierparameters_physicalcellid::text AS "Value"
                 FROM cell_lte
                 WHERE iid = ANY($1::text[])
                 AND imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                 AND (lte_carrierparameters_physicalcellid IS NULL
                      OR lte_carrierparameters_physicalcellid = -1)
                 LIMIT 20)
                UNION ALL
                (SELECT iid, 'Missing TAC', lte_tac::text
                 FROM cell_lte
                 WHERE iid = ANY($1::text[])
                 AND imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                 AND lte_tac IS NULL
                 LIMIT 20)
                UNION ALL
                (SELECT iid, 'Missing Tx Power', lte_carrierparameters_maxtxpower::text
                 FROM cell_lte
                 WHERE iid = ANY($1::text[])
                 AND imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                 AND lte_carrierparameters_maxtxpower IS NULL
                 LIMIT 20)
                UNION ALL
                (SELECT iid, 'Missing Carrier/EARFCN', lte_carrierparameters_iid
                 FROM cell_lte
                 WHERE iid = ANY($1::text[])
                 AND imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                 AND lte_carrierparameters_iid IS NULL
                 LIMIT 20)
                UNION ALL
                (SELECT c.iid, 'Downtilt Out of Range',
                        'tilt=' || p.tilt::text || ' (min=' || COALESCE(p.constraints_minmechanicaltilt_value::text,'N/A') || ', max=' || COALESCE(p.constraints_maxmechanicaltilt_value::text,'N/A') || ')'
                 FROM cell_lte c
                 LEFT JOIN cell_physical_antenna p ON c.eid = p.cell_eid
                 WHERE c.iid = ANY($1::text[])
                 AND c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                 AND p.tilt IS NOT NULL
                 AND (p.tilt < COALESCE(p.constraints_minmechanicaltilt_value, 0)
                      OR p.tilt > COALESCE(p.constraints_maxmechanicaltilt_value, 90))
                 LIMIT 20);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))

            pci_count_query = """
                SELECT
                    COUNT(CASE WHEN c1.lte_carrierparameters_physicalcellid = c2.lte_carrierparameters_physicalcellid THEN 1 END) AS exact_collisions,
                    COUNT(CASE WHEN c1.lte_carrierparameters_physicalcellid != c2.lte_carrierparameters_physicalcellid
                                AND MOD(c1.lte_carrierparameters_physicalcellid, 3) = MOD(c2.lte_carrierparameters_physicalcellid, 3) THEN 1 END) AS mod3_conflicts
                FROM cell_lte c1
                JOIN cell_lte c2
                    ON c1.location_iid = c2.location_iid
                    AND c1.iid < c2.iid
                    AND c2.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                    AND COALESCE(c1.lte_carrierparameters_iid, '') = COALESCE(c2.lte_carrierparameters_iid, '')
                WHERE c1.iid = ANY($1::text[])
                AND c1.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                AND c1.lte_carrierparameters_physicalcellid IS NOT NULL
                AND c1.lte_carrierparameters_physicalcellid >= 0
                AND c2.lte_carrierparameters_physicalcellid IS NOT NULL
                AND c2.lte_carrierparameters_physicalcellid >= 0
                AND (
                    c1.lte_carrierparameters_physicalcellid = c2.lte_carrierparameters_physicalcellid
                    OR MOD(c1.lte_carrierparameters_physicalcellid, 3) = MOD(c2.lte_carrierparameters_physicalcellid, 3)
                );
            """
            pci_count_rows = await self._fetch_query(project_name, pci_count_query, user_email, (entity_names,))
            collision_count = pci_count_rows[0].get('exact_collisions', 0) if pci_count_rows else 0
            mod3_count = pci_count_rows[0].get('mod3_conflicts', 0) if pci_count_rows else 0

            if not rows and collision_count == 0 and mod3_count == 0:
                md_data = "### Non-Compliant Cells (LTE)\n\n**All cells are compliant** for PCI, TAC, Tx Power, Carrier/EARFCN, Downtilt, and PCI planning (no same-band collisions or mod 3 conflicts).\n"
                return AuditFunctionResult(
                    summary="Non-Compliant Cells (LTE): All clear — no issues found",
                    md_data=md_data, raw_data=rows, stats={"total": 0}
                )

            # Group by issue type for summary
            issues = {}
            for r in rows:
                issue = r.get('Issue', 'Unknown')
                issues[issue] = issues.get(issue, 0) + 1
            if collision_count > 0:
                issues['PCI Collision (same band)'] = collision_count
            if mod3_count > 0:
                issues['PCI mod 3 Conflict (RS interference)'] = mod3_count

            md_data = "### Non-Compliant Cells Sample (LTE)\n\n"
            md_data += f"**Showing up to 20 cells per issue type** (from {len(entity_names)} total cells). PCI collision/mod 3 rows are site-pair counts on the same band.\n\n"
            pci_pair_issues = {'PCI Collision (same band)', 'PCI mod 3 Conflict (RS interference)'}
            md_data += "| Issue | Count |\n|-------|------|\n"
            for issue, count in issues.items():
                suffix = "+" if count >= 20 and issue not in pci_pair_issues else ""
                md_data += f"| {issue} | {count}{suffix} |\n"
            md_data += "\n"
            md_data += generate_generic_markdown(self.name, self.description, rows, {"total": len(rows)})

            issue_summary = ", ".join(f"{k}: {v}{'+ ' if v >= 20 else ''}" for k, v in issues.items())
            return AuditFunctionResult(
                summary=f"Non-Compliant Cells (LTE): {issue_summary}",
                md_data=md_data, raw_data=rows, stats={"total": len(rows), **issues}
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)


# ==================== NEW TELECOM-STANDARD AUDIT FUNCTIONS (LTE) ====================

@audit_function_registry.register
class CellIdentityAuditLTE(BaseAuditFunction):
    name = "cell_identity_lte"
    description = "Cell Identity Audit — verifies ECI, ECGI, TAC, PCI assignment and PCI valid range (0-503) for LTE cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT
                    iid AS "Cell Name",
                    lte_eci AS "ECI",
                    lte_ecgi AS "ECGI",
                    lte_tac AS "TAC",
                    lte_carrierparameters_physicalcellid AS "PCI",
                    CASE
                        WHEN lte_eci IS NULL THEN 'Missing ECI'
                        WHEN lte_ecgi IS NULL THEN 'Missing ECGI'
                        WHEN lte_tac IS NULL THEN 'Missing TAC'
                        WHEN lte_carrierparameters_physicalcellid IS NULL THEN 'Missing PCI'
                        WHEN lte_carrierparameters_physicalcellid < 0 OR lte_carrierparameters_physicalcellid > 503 THEN 'PCI out of range (0-503)'
                        ELSE 'OK'
                    END AS "Status"
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = evaluate_configurable_rule(self.name, config, rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            return AuditFunctionResult(
                summary=f"Cell Identity (LTE): {stats['yes']}/{stats['total']} cells fully identified (ECI/ECGI/TAC/PCI)",
                md_data=md_data, raw_data=rows, stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)


@audit_function_registry.register
class RachRsiAuditLTE(BaseAuditFunction):
    name = "rach_rsi_lte"
    description = "RACH Root Sequence Index (RSI) audit — verifies RSI assignment and valid range (0-837) for LTE cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT
                    iid AS "Cell Name",
                    lte_firstassignedrsi AS "RSI",
                    lte_numberassignedrsi AS "Num RSI Assigned",
                    lte_zerocorrelationzone AS "Zero Correlation Zone",
                    CASE
                        WHEN lte_firstassignedrsi IS NULL THEN 'Missing'
                        WHEN lte_firstassignedrsi < 0 OR lte_firstassignedrsi > 837 THEN 'Out of range (0-837)'
                        ELSE 'OK'
                    END AS "Status"
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = evaluate_configurable_rule(self.name, config, rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            return AuditFunctionResult(
                summary=f"RACH RSI (LTE): {stats['yes']}/{stats['total']} cells have valid RSI assigned",
                md_data=md_data, raw_data=rows, stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)


@audit_function_registry.register
class RfPowerAuditLTE(BaseAuditFunction):
    name = "rf_power_lte"
    description = "RF Power audit — checks Max Tx Power, Reference Signal Power (RS PPRE), and flags unusual values for LTE cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT
                    iid AS "Cell Name",
                    lte_carrierparameters_maxtxpower AS "Max Tx Power (dBm)",
                    lte_carrierparameters_referencesignalppre AS "RS Power/RE (dBm)",
                    lte_carrierparameters_noisefigure AS "Noise Figure (dB)",
                    CASE
                        WHEN lte_carrierparameters_maxtxpower IS NULL THEN 'Missing Tx Power'
                        WHEN lte_carrierparameters_maxtxpower < 10 THEN 'Tx Power too low (<10 dBm)'
                        WHEN lte_carrierparameters_maxtxpower > 60 THEN 'Tx Power too high (>60 dBm)'
                        WHEN lte_carrierparameters_referencesignalppre IS NULL THEN 'Missing RS Power'
                        ELSE 'OK'
                    END AS "Status"
                FROM cell_lte
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = evaluate_configurable_rule(self.name, config, rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            return AuditFunctionResult(
                summary=f"RF Power (LTE): {stats['yes']}/{stats['total']} cells have valid Tx Power & RS Power",
                md_data=md_data, raw_data=rows, stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)


@audit_function_registry.register
class CarrierBandAuditLTE(BaseAuditFunction):
    name = "carrier_band_lte"
    description = "Carrier & Band audit — checks Bandwidth, EARFCN (Carrier ID), and validates LTE bandwidth values for LTE cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            # First try with bandwidth column — some DBs may not have it
            try:
                query = """
                    SELECT DISTINCT
                        iid AS "Cell Name",
                        lte_carrierparameters_bandwidth AS "Bandwidth (MHz)",
                        lte_carrierparameters_iid AS "Carrier/EARFCN",
                        lte_carrierparameters_eid AS "Carrier EID",
                        CASE
                            WHEN lte_carrierparameters_iid IS NULL THEN 'Missing Carrier/EARFCN'
                            WHEN lte_carrierparameters_bandwidth IS NULL THEN 'Missing Bandwidth'
                            ELSE 'OK'
                        END AS "Status"
                    FROM cell_lte
                    WHERE iid = ANY($1::text[])
                    AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
                """
                rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            except Exception:
                # Fallback: bandwidth column may not exist in this DB
                query = """
                    SELECT DISTINCT
                        iid AS "Cell Name",
                        lte_carrierparameters_iid AS "Carrier/EARFCN",
                        lte_carrierparameters_eid AS "Carrier EID",
                        CASE
                            WHEN lte_carrierparameters_iid IS NULL THEN 'Missing Carrier/EARFCN'
                            ELSE 'OK'
                        END AS "Status"
                    FROM cell_lte
                    WHERE iid = ANY($1::text[])
                    AND imported_at = (SELECT MAX(imported_at) FROM cell_lte);
                """
                rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            stats = calculate_status_stats(rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            return AuditFunctionResult(
                summary=f"Carrier & Band (LTE): {stats['yes']}/{stats['total']} cells have Carrier/EARFCN configured",
                md_data=md_data, raw_data=rows, stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)


@audit_function_registry.register
class PciCollisionAuditLTE(BaseAuditFunction):
    name = "pci_collision_lte"
    description = "PCI Collision & Confusion audit — detects same PCI on co-located LTE cells on the SAME band/carrier (EARFCN). Different bands can safely reuse PCIs."
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE, AuditCategory.SUMMARY]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            # Per-cell Status + peer cells. PCI NULL/-1 = not configured (no collision/mod3).
            # Collision/mod3 only compared for configured PCIs (>= 0) on the SAME band/carrier.
            query = """
                SELECT
                    c.iid AS "Cell Name",
                    c.location_iid AS "Site",
                    c.lte_carrierparameters_physicalcellid AS "PCI",
                    COALESCE(c.lte_carrierparameters_iid, 'N/A') AS "Carrier/EARFCN",
                    COALESCE(collision_peers.peers, mod3_peers.peers, 'N/A') AS "Collides With",
                    CASE
                        WHEN c.lte_carrierparameters_physicalcellid IS NULL
                             OR c.lte_carrierparameters_physicalcellid = -1
                        THEN 'PCI not configured'
                        WHEN collision_peers.peers IS NOT NULL
                        THEN 'PCI Collision (same band)'
                        WHEN mod3_peers.peers IS NOT NULL
                        THEN 'PCI mod 3 Conflict (RS interference)'
                        ELSE 'OK'
                    END AS "Status"
                FROM cell_lte c
                LEFT JOIN LATERAL (
                    SELECT string_agg(o.iid, ', ' ORDER BY o.iid) AS peers
                    FROM cell_lte o
                    WHERE o.location_iid = c.location_iid
                      AND o.iid <> c.iid
                      AND o.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                      AND COALESCE(o.lte_carrierparameters_iid, '') = COALESCE(c.lte_carrierparameters_iid, '')
                      AND c.lte_carrierparameters_physicalcellid IS NOT NULL
                      AND c.lte_carrierparameters_physicalcellid >= 0
                      AND o.lte_carrierparameters_physicalcellid IS NOT NULL
                      AND o.lte_carrierparameters_physicalcellid >= 0
                      AND o.lte_carrierparameters_physicalcellid = c.lte_carrierparameters_physicalcellid
                ) collision_peers ON TRUE
                LEFT JOIN LATERAL (
                    SELECT string_agg(o.iid, ', ' ORDER BY o.iid) AS peers
                    FROM cell_lte o
                    WHERE o.location_iid = c.location_iid
                      AND o.iid <> c.iid
                      AND o.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                      AND COALESCE(o.lte_carrierparameters_iid, '') = COALESCE(c.lte_carrierparameters_iid, '')
                      AND c.lte_carrierparameters_physicalcellid IS NOT NULL
                      AND c.lte_carrierparameters_physicalcellid >= 0
                      AND o.lte_carrierparameters_physicalcellid IS NOT NULL
                      AND o.lte_carrierparameters_physicalcellid >= 0
                      AND o.lte_carrierparameters_physicalcellid <> c.lte_carrierparameters_physicalcellid
                      AND MOD(o.lte_carrierparameters_physicalcellid, 3) = MOD(c.lte_carrierparameters_physicalcellid, 3)
                ) mod3_peers ON TRUE
                WHERE c.iid = ANY($1::text[])
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
                ORDER BY c.location_iid, c.iid;
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            stats = calculate_status_stats(rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            return AuditFunctionResult(
                summary=f"PCI Collision (LTE): {stats['yes']}/{stats['total']} cells compliant (no collision/mod3; PCI configured)",
                md_data=md_data, raw_data=rows, stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)
