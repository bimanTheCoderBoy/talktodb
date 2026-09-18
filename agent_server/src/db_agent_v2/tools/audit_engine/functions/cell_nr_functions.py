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
class CarrierAssignmentAuditNR(BaseAuditFunction):
    name = "carrier_assignment_nr"
    description = "Analyzes carrier assignment (PCI) for 5G NR cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", nrt_carrierparameters_physicalcellid AS pci
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows, lambda r: calculate_configured_stats(r, ["pci"])
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Carrier Assignment (NR): {stats['yes']}/{stats['total']} cells have PCI configured",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class CarrierAggregationAuditNR(BaseAuditFunction):
    name = "carrier_aggregation_nr"
    description = "Checks whether the carrier aggregation (CA) parameter is configured per cell (TRUE/FALSE). NULL means not configured."
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", nrt_carrierparameters_caenabledatcell
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows,
                lambda r: calculate_configured_stats(r, ["nrt_carrierparameters_caenabledatcell"]),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Carrier Aggregation (NR): {stats['yes']}/{stats['total']} cells have CA parameter configured",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class SuMimoAuditNR(BaseAuditFunction):
    name = "su_mimo_nr"
    description = "Check if SU-MIMO is configured for uplink/downlink in 5G NR cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", nrt_sumimosupportdl, nrt_sumimosupportul
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows,
                lambda r: calculate_configured_stats(r, ["nrt_sumimosupportdl", "nrt_sumimosupportul"]),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"SU-MIMO (NR): {stats['yes']}/{stats['total']} cells have SU-MIMO parameters configured",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class MuMimoAuditNR(BaseAuditFunction):
    name = "mu_mimo_nr"
    description = "Retrieve MU-MIMO terms assigned to a 5G NR cell"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", nrt_mumimosupportdl, nrt_mumimosupportul,
                       nrt_mumimotermsdl, nrt_mumimotermsul
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name,
                config,
                rows,
                lambda r: calculate_configured_stats(
                    r,
                    ["nrt_mumimosupportdl", "nrt_mumimosupportul", "nrt_mumimotermsdl", "nrt_mumimotermsul"],
                ),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"MU-MIMO (NR): {stats['yes']}/{stats['total']} cells have MU-MIMO parameters configured",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class RxTxElementsAuditNR(BaseAuditFunction):
    name = "rx_tx_elements_nr"
    description = "Get number of TX and RX elements for 5G NR cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", nrt_sumimotxelems, nrt_sumimorxelems
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows,
                lambda r: calculate_configured_stats(r, ["nrt_sumimotxelems", "nrt_sumimorxelems"]),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"RX/TX Elements (NR): {stats['yes']}/{stats['total']} cells have RX/TX element counts configured",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class BeamformingSupportAuditNR(BaseAuditFunction):
    name = "beamforming_support_nr"
    description = "Checks which 5G NR cells have single-beam (beamforming) enabled on the logical antenna"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE, AuditCategory.SUMMARY]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            # Note: NR cells may not have beamforming columns in the same way as LTE
            # Using singlebeamenabled from cell_logical_antenna if available, or checking carrier parameters
            query = """
                SELECT DISTINCT c.iid AS "Cell Name", 
                       CASE WHEN l.singlebeamenabled = TRUE THEN 'Yes' ELSE 'No' END AS beamforming_support
                FROM cell_nr c
                LEFT JOIN cell_logical_antenna l ON c.eid = l.cell_eid
                WHERE c.iid = ANY($1::text[])
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = evaluate_configurable_rule(self.name, config, rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Beamforming (NR): {stats['yes']}/{stats['total']} cells have beamforming enabled",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class SignalThresholdsAuditNR(BaseAuditFunction):
    name = "signal_thresholds_nr"
    description = "Retrieve SS-RSRP and SINR thresholds per 5G NR cell"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", 
                       nrt_carrierparameters_ssrsrpthreshold,
                       nrt_carrierparameters_sinrthreshold,
                       nrt_carrierparameters_csirsrpthreshold
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows,
                lambda r: calculate_configured_stats(r, [
                    "nrt_carrierparameters_ssrsrpthreshold",
                    "nrt_carrierparameters_sinrthreshold",
                    "nrt_carrierparameters_csirsrpthreshold",
                ]),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Signal Thresholds (NR): {stats['yes']}/{stats['total']} cells have thresholds configured",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class CoverageRangeAuditNR(BaseAuditFunction):
    name = "coverage_range_nr"
    description = "Get estimated 5G NR cell coverage range"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE, AuditCategory.SUMMARY]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", 
                       nrt_carrierparameters_maxrange,
                       nrt_csrange AS coverage_range
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows,
                lambda r: calculate_configured_stats(r, ["nrt_carrierparameters_maxrange", "coverage_range"]),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Coverage Range (NR): {stats['yes']}/{stats['total']} cells have coverage range configured",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class InterferenceAuditNR(BaseAuditFunction):
    name = "interference_nr"
    description = "Find 5G NR cells with high inter-tech interference"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", 
                       nrt_carrierparameters_intertechinterference_ltenoiserisecellter,
                       nrt_carrierparameters_noiserisecelltermtotalul_ro
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows,
                lambda r: calculate_configured_stats(r, [
                    "nrt_carrierparameters_intertechinterference_ltenoiserisecellter",
                    "nrt_carrierparameters_noiserisecelltermtotalul_ro",
                ]),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Interference (NR): {stats['yes']}/{stats['total']} cells have interference parameters configured",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class CellLoadAuditNR(BaseAuditFunction):
    name = "cell_load_nr"
    description = "Retrieve average connected users and load for 5G NR cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE, AuditCategory.SUMMARY]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name",
                       nrt_carrierparameters_cellbandwidthparts_avgnumofconnusers,
                       nrt_carrierparameters_cellbandwidthparts_cellloadpcntdl,
                       nrt_carrierparameters_cellbandwidthparts_cellloadpcntul
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows,
                lambda r: calculate_configured_stats(r, [
                    "nrt_carrierparameters_cellbandwidthparts_avgnumofconnusers",
                    "nrt_carrierparameters_cellbandwidthparts_cellloadpcntdl",
                    "nrt_carrierparameters_cellbandwidthparts_cellloadpcntul",
                ]),
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Cell Load (NR): {stats['yes']}/{stats['total']} cells have load parameters configured",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class SecurityAuditNR(BaseAuditFunction):
    name = "security_audit_nr"
    description = "Check who last modified a 5G NR cell"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT iid AS "Cell Name", security_modifyuser, security_modifydate
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            stats = {"total": len(rows)}
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Security (NR): Analyzed {len(rows)} cells",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class CoverageAndHeightAuditNR(BaseAuditFunction):
    name = "coverage_and_height_nr"
    description = "5G NR Cell Coverage and Antenna Height"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE, AuditCategory.SUMMARY]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT 
                    c.iid AS "Cell Name",
                    l.primarymodel_radiuskm AS coverage_km,
                    p.height AS antenna_height_m
                FROM cell_nr c
                JOIN cell_logical_antenna l 
                    ON c.eid = l.cell_eid
                JOIN cell_physical_antenna p 
                    ON c.eid = p.cell_eid
                WHERE c.iid = ANY($1::text[])
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows, lambda r: calculate_configured_stats(r, ["coverage_km", "antenna_height_m"])
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Coverage & Height (NR): {stats['yes']}/{stats['total']} cells have coverage/height data configured",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class AntennaOrientationAuditNR(BaseAuditFunction):
    name = "antenna_orientation_nr"
    description = "Antenna Orientation (Azimuth/Tilt) for 5G NR cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT 
                    c.iid AS "Cell Name",
                    p.azimuth, 
                    p.tilt
                FROM cell_nr c
                JOIN cell_physical_antenna p 
                    ON c.eid = p.cell_eid
                WHERE c.iid = ANY($1::text[])
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = apply_configurable_or_default(
                self.name, config, rows, lambda r: calculate_configured_stats(r, ["azimuth", "tilt"])
            )
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Orientation (NR): {stats['yes']}/{stats['total']} cells have azimuth/tilt configured",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class DowntiltComplianceAuditNR(BaseAuditFunction):
    name = "downtilt_compliance_nr"
    description = "Antenna Downtilt Compliance Check for 5G NR cells"
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
                FROM cell_nr c
                JOIN location l 
                    ON c.location_eid = l.eid
                LEFT JOIN cell_physical_antenna p 
                    ON c.eid = p.cell_eid
                WHERE c.iid = ANY($1::text[])
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                ORDER BY c.eid, p.imported_at DESC NULLS LAST;
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = evaluate_configurable_rule(self.name, config, rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            
            return AuditFunctionResult(
                summary=f"Downtilt Compliance (NR): {stats['yes']}/{stats['total']} cells compliant",
                md_data=md_data,
                raw_data=rows,
                stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)

@audit_function_registry.register
class CellHighLevelStatsNR(BaseAuditFunction):
    name = "cell_high_level_stats_nr"
    description = "High level statistics for large 5G NR cell populations"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.AGGREGATED, AuditCategory.STATISTICS]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT
                    COUNT(*) AS total_cells,
                    COUNT(CASE WHEN nrt_tac IS NOT NULL THEN 1 END) AS tac_assigned,
                    COUNT(CASE WHEN nrt_carrierparameters_physicalcellid IS NOT NULL THEN 1 END) AS carrier_assigned,
                    COUNT(CASE WHEN nrt_carrierparameters_firstassignedrsi IS NOT NULL THEN 1 END) AS rsi_assigned,
                    COUNT(CASE WHEN nrt_carrierparameters_maxtxpower IS NOT NULL THEN 1 END) AS tx_power_configured,
                    COUNT(CASE WHEN nrt_carrierparameters_cellbandwidthparts_downlink_startarfcn IS NOT NULL THEN 1 END) AS dl_arfcn_configured,
                    COUNT(CASE WHEN nrt_carrierparameters_cellbandwidthparts_downlink_prbs IS NOT NULL THEN 1 END) AS dl_prbs_configured,
                    COUNT(CASE WHEN nrt_carrierparameters_caenabledatcell = TRUE THEN 1 END) AS carrier_aggregation_enabled,
                    COUNT(CASE WHEN nrt_sumimosupportdl = TRUE OR nrt_sumimosupportul = TRUE THEN 1 END) AS su_mimo_enabled,
                    COUNT(CASE WHEN nrt_mumimosupportdl = TRUE OR nrt_mumimosupportul = TRUE THEN 1 END) AS mu_mimo_enabled,
                    COUNT(CASE WHEN nrt_carrierparameters_maxrange IS NOT NULL OR nrt_csrange IS NOT NULL THEN 1 END) AS coverage_range_configured,
                    COUNT(CASE WHEN nrt_carrierparameters_cellbandwidthparts_avgnumofconnusers IS NOT NULL THEN 1 END) AS cell_load_configured
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            
            # Beamforming support count (requires join with logical antenna)
            beamforming_query = """
                SELECT 
                    COUNT(DISTINCT c.eid) AS total_with_antenna,
                    COUNT(CASE WHEN l.singlebeamenabled = TRUE THEN 1 END) AS beamforming_enabled
                FROM cell_nr c
                LEFT JOIN cell_logical_antenna l ON c.eid = l.cell_eid
                WHERE c.iid = ANY($1::text[])
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            beamforming_rows = await self._fetch_query(project_name, beamforming_query, user_email, (entity_names,))
            
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
                FROM cell_nr c
                LEFT JOIN cell_physical_antenna p ON c.eid = p.cell_eid
                WHERE c.iid = ANY($1::text[])
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                AND p.cell_eid IS NOT NULL;
            """
            downtilt_rows = await self._fetch_query(project_name, downtilt_query, user_email, (entity_names,))
            
            if rows and len(rows) > 0:
                row = rows[0]
                beamforming_row = beamforming_rows[0] if beamforming_rows else {}
                downtilt_row = downtilt_rows[0] if downtilt_rows else {}
                
                total = row.get('total_cells', 0)
                tac_assigned = row.get('tac_assigned', 0)
                carrier_assigned = row.get('carrier_assigned', 0)
                rsi_assigned = row.get('rsi_assigned', 0)
                tx_power = row.get('tx_power_configured', 0)
                dl_arfcn = row.get('dl_arfcn_configured', 0)
                dl_prbs = row.get('dl_prbs_configured', 0)
                carrier_agg = row.get('carrier_aggregation_enabled', 0)
                su_mimo = row.get('su_mimo_enabled', 0)
                mu_mimo = row.get('mu_mimo_enabled', 0)
                coverage_range = row.get('coverage_range_configured', 0)
                cell_load = row.get('cell_load_configured', 0)
                beamforming = beamforming_row.get('beamforming_enabled', 0)
                total_with_beamforming = beamforming_row.get('total_with_antenna', 0)
                downtilt_compliant = downtilt_row.get('downtilt_compliant', 0)
                total_with_antenna = downtilt_row.get('total_with_antenna', 0)

                stats = {
                    "total": total,
                    "tac_assigned": tac_assigned,
                    "carrier_assigned": carrier_assigned,
                    "rsi_assigned": rsi_assigned,
                    "tx_power_configured": tx_power,
                    "dl_arfcn_configured": dl_arfcn,
                    "dl_prbs_configured": dl_prbs,
                    "carrier_aggregation_enabled": carrier_agg,
                    "su_mimo_enabled": su_mimo,
                    "mu_mimo_enabled": mu_mimo,
                    "beamforming_enabled": beamforming,
                    "coverage_range_configured": coverage_range,
                    "cell_load_configured": cell_load,
                    "downtilt_compliant": downtilt_compliant,
                    "total_with_antenna": total_with_antenna,
                    "total_with_beamforming": total_with_beamforming,
                }

                md_data = build_cell_high_level_markdown(stats, self.get_config(), tech_label="NR")
                if total_with_beamforming > 0 or total_with_antenna > 0:
                    md_data += (
                        f"\n*Note: Beamforming calculated from {total_with_beamforming} cells with antenna data. "
                        f"Downtilt compliance calculated from {total_with_antenna} cells with antenna data.*\n"
                    )
                stats = filter_high_level_stats_dict(stats, self.get_config())

                summary = f"High Level Stats (NR): {total} cells - TAC: {tac_assigned}, PCI: {carrier_assigned}, RSI: {rsi_assigned}, TxPower: {tx_power}, ARFCN: {dl_arfcn}, CA: {carrier_agg}"
                
                return AuditFunctionResult(
                    summary=summary,
                    md_data=md_data,
                    raw_data=rows,
                    stats=stats
                )
            else:
                return AuditFunctionResult(
                    summary=f"High Level Stats (NR): {len(entity_names)} cells analyzed",
                    md_data=f"### Cell High Level Statistics (NR)\n\nNo data found for {len(entity_names)} cells.",
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
class NonCompliantCellsNR(BaseAuditFunction):
    name = "non_compliant_cells_nr"
    description = "Sample of non-compliant 5G NR cells — shows top 20 cells per issue (missing PCI, TAC, Tx Power, tilt out of range, PCI collision/mod 3 counts on same band"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.AGGREGATED, AuditCategory.STATISTICS]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                (SELECT iid AS "Cell Name", 'Missing PCI' AS "Issue",
                        nrt_carrierparameters_physicalcellid::text AS "Value"
                 FROM cell_nr
                 WHERE iid = ANY($1::text[])
                 AND imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                 AND (nrt_carrierparameters_physicalcellid IS NULL
                      OR nrt_carrierparameters_physicalcellid = -1)
                 LIMIT 20)
                UNION ALL
                (SELECT iid, 'Missing TAC', nrt_tac::text
                 FROM cell_nr
                 WHERE iid = ANY($1::text[])
                 AND imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                 AND nrt_tac IS NULL
                 LIMIT 20)
                UNION ALL
                (SELECT iid, 'Missing Tx Power', nrt_carrierparameters_maxtxpower::text
                 FROM cell_nr
                 WHERE iid = ANY($1::text[])
                 AND imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                 AND nrt_carrierparameters_maxtxpower IS NULL
                 LIMIT 20)
                UNION ALL
                (SELECT c.iid, 'Downtilt Out of Range',
                        'tilt=' || p.tilt::text || ' (min=' || COALESCE(p.constraints_minmechanicaltilt_value::text,'N/A') || ', max=' || COALESCE(p.constraints_maxmechanicaltilt_value::text,'N/A') || ')'
                 FROM cell_nr c
                 LEFT JOIN cell_physical_antenna p ON c.eid = p.cell_eid
                 WHERE c.iid = ANY($1::text[])
                 AND c.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                 AND p.tilt IS NOT NULL
                 AND (p.tilt < COALESCE(p.constraints_minmechanicaltilt_value, 0)
                      OR p.tilt > COALESCE(p.constraints_maxmechanicaltilt_value, 90))
                 LIMIT 20);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))

            pci_count_query = """
                SELECT
                    COUNT(CASE WHEN c1.nrt_carrierparameters_physicalcellid = c2.nrt_carrierparameters_physicalcellid THEN 1 END) AS exact_collisions,
                    COUNT(CASE WHEN c1.nrt_carrierparameters_physicalcellid != c2.nrt_carrierparameters_physicalcellid
                                AND MOD(c1.nrt_carrierparameters_physicalcellid, 3) = MOD(c2.nrt_carrierparameters_physicalcellid, 3) THEN 1 END) AS mod3_conflicts
                FROM cell_nr c1
                JOIN cell_nr c2
                    ON c1.location_iid = c2.location_iid
                    AND c1.iid < c2.iid
                    AND c2.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                    AND COALESCE(c1.nrt_carrierparameters_iid, '') = COALESCE(c2.nrt_carrierparameters_iid, '')
                WHERE c1.iid = ANY($1::text[])
                AND c1.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                AND c1.nrt_carrierparameters_physicalcellid IS NOT NULL
                AND c1.nrt_carrierparameters_physicalcellid >= 0
                AND c2.nrt_carrierparameters_physicalcellid IS NOT NULL
                AND c2.nrt_carrierparameters_physicalcellid >= 0
                AND (
                    c1.nrt_carrierparameters_physicalcellid = c2.nrt_carrierparameters_physicalcellid
                    OR MOD(c1.nrt_carrierparameters_physicalcellid, 3) = MOD(c2.nrt_carrierparameters_physicalcellid, 3)
                );
            """
            pci_count_rows = await self._fetch_query(project_name, pci_count_query, user_email, (entity_names,))
            collision_count = pci_count_rows[0].get('exact_collisions', 0) if pci_count_rows else 0
            mod3_count = pci_count_rows[0].get('mod3_conflicts', 0) if pci_count_rows else 0

            if not rows and collision_count == 0 and mod3_count == 0:
                md_data = "### Non-Compliant Cells (NR)\n\n**All cells are compliant** for PCI, TAC, Tx Power, Downtilt, and PCI planning (no same-band collisions or mod 3 conflicts).\n"
                return AuditFunctionResult(
                    summary="Non-Compliant Cells (NR): All clear — no issues found",
                    md_data=md_data, raw_data=rows, stats={"total": 0}
                )

            issues = {}
            for r in rows:
                issue = r.get('Issue', 'Unknown')
                issues[issue] = issues.get(issue, 0) + 1
            if collision_count > 0:
                issues['PCI Collision (same band)'] = collision_count
            if mod3_count > 0:
                issues['PCI mod 3 Conflict (PSS interference)'] = mod3_count

            md_data = "### Non-Compliant Cells Sample (NR)\n\n"
            md_data += f"**Showing up to 20 cells per issue type** (from {len(entity_names)} total cells). PCI collision/mod 3 rows are site-pair counts on the same band.\n\n"
            pci_pair_issues = {'PCI Collision (same band)', 'PCI mod 3 Conflict (PSS interference)'}
            md_data += "| Issue | Count |\n|-------|------|\n"
            for issue, count in issues.items():
                suffix = "+" if count >= 20 and issue not in pci_pair_issues else ""
                md_data += f"| {issue} | {count}{suffix} |\n"
            md_data += "\n"
            md_data += generate_generic_markdown(self.name, self.description, rows, {"total": len(rows)})

            issue_summary = ", ".join(f"{k}: {v}{'+ ' if v >= 20 else ''}" for k, v in issues.items())
            return AuditFunctionResult(
                summary=f"Non-Compliant Cells (NR): {issue_summary}",
                md_data=md_data, raw_data=rows, stats={"total": len(rows), **issues}
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)


# ==================== NEW TELECOM-STANDARD AUDIT FUNCTIONS (NR) ====================

@audit_function_registry.register
class CellIdentityAuditNR(BaseAuditFunction):
    name = "cell_identity_nr"
    description = "Cell Identity Audit — verifies TAC, PCI assignment and PCI valid range (0-1007) for 5G NR cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT
                    iid AS "Cell Name",
                    nrt_tac AS "TAC",
                    nrt_carrierparameters_physicalcellid AS "PCI",
                    CASE
                        WHEN nrt_tac IS NULL THEN 'Missing TAC'
                        WHEN nrt_carrierparameters_physicalcellid IS NULL THEN 'Missing PCI'
                        WHEN nrt_carrierparameters_physicalcellid < 0 OR nrt_carrierparameters_physicalcellid > 1007 THEN 'PCI out of range (0-1007)'
                        ELSE 'OK'
                    END AS "Status"
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = evaluate_configurable_rule(self.name, config, rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            return AuditFunctionResult(
                summary=f"Cell Identity (NR): {stats['yes']}/{stats['total']} cells fully identified (TAC/PCI)",
                md_data=md_data, raw_data=rows, stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)


@audit_function_registry.register
class RachRsiAuditNR(BaseAuditFunction):
    name = "rach_rsi_nr"
    description = "RACH Root Sequence Index (RSI) audit — verifies RSI assignment for 5G NR cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT
                    iid AS "Cell Name",
                    nrt_carrierparameters_firstassignedrsi AS "RSI",
                    CASE
                        WHEN nrt_carrierparameters_firstassignedrsi IS NULL THEN 'Missing'
                        ELSE 'OK'
                    END AS "Status"
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = evaluate_configurable_rule(self.name, config, rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            return AuditFunctionResult(
                summary=f"RACH RSI (NR): {stats['yes']}/{stats['total']} cells have valid RSI assigned",
                md_data=md_data, raw_data=rows, stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)


@audit_function_registry.register
class RfPowerAuditNR(BaseAuditFunction):
    name = "rf_power_nr"
    description = "RF Power audit — checks Max Tx Power and flags unusual values for 5G NR cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT
                    iid AS "Cell Name",
                    nrt_carrierparameters_maxtxpower AS "Max Tx Power (dBm)",
                    nrt_carrierparameters_noisefigure AS "Noise Figure (dB)",
                    CASE
                        WHEN nrt_carrierparameters_maxtxpower IS NULL THEN 'Missing Tx Power'
                        WHEN nrt_carrierparameters_maxtxpower < 10 THEN 'Tx Power too low (<10 dBm)'
                        WHEN nrt_carrierparameters_maxtxpower > 70 THEN 'Tx Power too high (>70 dBm)'
                        ELSE 'OK'
                    END AS "Status"
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = evaluate_configurable_rule(self.name, config, rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            return AuditFunctionResult(
                summary=f"RF Power (NR): {stats['yes']}/{stats['total']} cells have valid Tx Power",
                md_data=md_data, raw_data=rows, stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)


@audit_function_registry.register
class CarrierBandAuditNR(BaseAuditFunction):
    name = "carrier_band_nr"
    description = "Carrier & Band audit — checks DL/UL ARFCN, DL/UL PRBs (bandwidth) for 5G NR cells"
    entity_types = [EntityType.CELL]
    categories = [AuditCategory.DETAILED, AuditCategory.MODERATE]

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            query = """
                SELECT DISTINCT
                    iid AS "Cell Name",
                    nrt_carrierparameters_cellbandwidthparts_downlink_startarfcn AS "DL Start ARFCN",
                    nrt_carrierparameters_cellbandwidthparts_uplink_startarfcn AS "UL Start ARFCN",
                    nrt_carrierparameters_cellbandwidthparts_downlink_prbs AS "DL PRBs",
                    nrt_carrierparameters_cellbandwidthparts_uplink_prbs AS "UL PRBs",
                    nrt_carrierparameters_cellbandwidthparts_downlink_numerology AS "DL Numerology",
                    nrt_carrierparameters_iid AS "Carrier ID",
                    CASE
                        WHEN nrt_carrierparameters_cellbandwidthparts_downlink_startarfcn IS NULL THEN 'Missing DL ARFCN'
                        WHEN nrt_carrierparameters_cellbandwidthparts_downlink_prbs IS NULL THEN 'Missing DL PRBs'
                        ELSE 'OK'
                    END AS "Status"
                FROM cell_nr
                WHERE iid = ANY($1::text[])
                AND imported_at = (SELECT MAX(imported_at) FROM cell_nr);
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            config = self.get_config()
            rows, stats = evaluate_configurable_rule(self.name, config, rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            return AuditFunctionResult(
                summary=f"Carrier & Band (NR): {stats['yes']}/{stats['total']} cells have ARFCN & PRBs configured",
                md_data=md_data, raw_data=rows, stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)


@audit_function_registry.register
class PciCollisionAuditNR(BaseAuditFunction):
    name = "pci_collision_nr"
    description = "PCI Collision & Confusion audit — detects same PCI and PCI mod 3 conflicts on co-located 5G NR cells on the SAME band/carrier (ARFCN). Different bands can safely reuse PCIs."
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
                    c.nrt_carrierparameters_physicalcellid AS "PCI",
                    COALESCE(c.nrt_carrierparameters_iid, 'N/A') AS "Carrier/ARFCN",
                    COALESCE(collision_peers.peers, mod3_peers.peers, 'N/A') AS "Collides With",
                    CASE
                        WHEN c.nrt_carrierparameters_physicalcellid IS NULL
                             OR c.nrt_carrierparameters_physicalcellid = -1
                        THEN 'PCI not configured'
                        WHEN collision_peers.peers IS NOT NULL
                        THEN 'PCI Collision (same band)'
                        WHEN mod3_peers.peers IS NOT NULL
                        THEN 'PCI mod 3 Conflict (PSS interference)'
                        ELSE 'OK'
                    END AS "Status"
                FROM cell_nr c
                LEFT JOIN LATERAL (
                    SELECT string_agg(o.iid, ', ' ORDER BY o.iid) AS peers
                    FROM cell_nr o
                    WHERE o.location_iid = c.location_iid
                      AND o.iid <> c.iid
                      AND o.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                      AND COALESCE(o.nrt_carrierparameters_iid, '') = COALESCE(c.nrt_carrierparameters_iid, '')
                      AND c.nrt_carrierparameters_physicalcellid IS NOT NULL
                      AND c.nrt_carrierparameters_physicalcellid >= 0
                      AND o.nrt_carrierparameters_physicalcellid IS NOT NULL
                      AND o.nrt_carrierparameters_physicalcellid >= 0
                      AND o.nrt_carrierparameters_physicalcellid = c.nrt_carrierparameters_physicalcellid
                ) collision_peers ON TRUE
                LEFT JOIN LATERAL (
                    SELECT string_agg(o.iid, ', ' ORDER BY o.iid) AS peers
                    FROM cell_nr o
                    WHERE o.location_iid = c.location_iid
                      AND o.iid <> c.iid
                      AND o.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                      AND COALESCE(o.nrt_carrierparameters_iid, '') = COALESCE(c.nrt_carrierparameters_iid, '')
                      AND c.nrt_carrierparameters_physicalcellid IS NOT NULL
                      AND c.nrt_carrierparameters_physicalcellid >= 0
                      AND o.nrt_carrierparameters_physicalcellid IS NOT NULL
                      AND o.nrt_carrierparameters_physicalcellid >= 0
                      AND o.nrt_carrierparameters_physicalcellid <> c.nrt_carrierparameters_physicalcellid
                      AND MOD(o.nrt_carrierparameters_physicalcellid, 3) = MOD(c.nrt_carrierparameters_physicalcellid, 3)
                ) mod3_peers ON TRUE
                WHERE c.iid = ANY($1::text[])
                AND c.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
                ORDER BY c.location_iid, c.iid;
            """
            rows = await self._fetch_query(project_name, query, user_email, (entity_names,))
            stats = calculate_status_stats(rows)
            md_data = generate_generic_markdown(self.name, self.description, rows, stats)
            return AuditFunctionResult(
                summary=f"PCI Collision (NR): {stats['yes']}/{stats['total']} cells compliant (no collision/mod3; PCI configured)",
                md_data=md_data, raw_data=rows, stats=stats
            )
        except Exception as e:
            return AuditFunctionResult(summary=f"Error in {self.name}", md_data=f"Error: {str(e)}", error=str(e), success=False)
