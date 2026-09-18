from pydantic.dataclasses import dataclass
import os
from pydantic import BaseModel, Field
from typing import Annotated, Dict, List, Any, Tuple
from pathlib import Path
from typing import Optional
from enum import Enum

IS_LOCAL_LLM_PROVIDER = os.getenv("IS_LOCAL_LLM_PROVIDER", "false") == "true"
class SQLGeneratorLLMConfig(BaseModel):
    """LLM configuration for SQL Generator."""
    api_key: Annotated[str, Field(default=os.getenv("OPENROUTER_API_KEY"))]
    base_url: Annotated[str, Field(default=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))]
    model: Annotated[str, Field(default=os.getenv("OPENROUTER_MODEL_SQL_GENERATOR", "google/gemini-2.0-flash-001"))]
    temperature: Annotated[float, Field(default=float(os.getenv("DB_AGENT_LLM_TEMPERATURE", "0.1")))]
    max_tokens: Annotated[int, Field(default=4096)]
    disable_streaming: Annotated[bool, Field(default=True)]
    if not IS_LOCAL_LLM_PROVIDER:
            extra_body: Annotated[dict, Field(default={

            "provider": {"order": os.getenv("PROVIDER_ORDER", "google-vertex,deepinfra,parasail,atlas-cloud,novita").split(","), "allow_fallbacks": True},
    })]

class DBconfig(BaseModel):
    host:Annotated[str, Field(default=os.getenv("DB_HOST"))]
    port:Annotated[int, Field(default=os.getenv("DB_PORT"))]
    user:Annotated[str, Field(default=os.getenv("DB_USER"))]
    password:Annotated[str, Field(default=os.getenv("DB_PASSWORD"))]
    min_size:Annotated[int, Field(default=1)]
    max_size:Annotated[int, Field(default=10)]

@dataclass
class AssetDBRagToolConfig :
    MAX_RETRIES:Annotated[int, Field(default=int(os.getenv("ASSET_DB_RAG_MAX_RETRIES", "3")))]
    llm:Annotated[dict, Field(default=SQLGeneratorLLMConfig().model_dump())]



#----------------------------------------Audit Engine Config----------------------------------------

class AuditCategory(str, Enum):
    """Audit categories based on entity count"""
    NONE = "none"           # 0 entities
    DETAILED = "detailed"   # 1-10 entities - full detailed analysis
    MODERATE = "moderate"   # 11-50 entities - moderate detail
    SUMMARY = "summary"     # 51-300 entities - summary level
    AGGREGATED = "aggregated"  # 301-1000 entities - aggregated queries
    STATISTICS = "statistics"  # 1000+ entities - high-level stats only


@dataclass
class AuditCategoryConfig:
    """Configuration for audit category thresholds"""
    thresholds: Dict[AuditCategory, Tuple[int, int]] = Field(default_factory=lambda: {
        AuditCategory.NONE: (0, 0),
        AuditCategory.DETAILED: (1, 10),
        AuditCategory.MODERATE: (11, 50),
        AuditCategory.SUMMARY: (51, 300),
        AuditCategory.AGGREGATED: (301, 1000),
        AuditCategory.STATISTICS: (1001, float('inf')),
    })
    
    def get_category(self, count: int) -> AuditCategory:
        """Determine category based on entity count"""
        if count == 0:
            return AuditCategory.NONE
        for category, (min_val, max_val) in self.thresholds.items():
            if min_val <= count <= max_val:
                return category
        return AuditCategory.STATISTICS


@dataclass
class AuditEngineToolConfig:
    """Configuration for Audit Engine tool"""
    category_config: AuditCategoryConfig = Field(default_factory=AuditCategoryConfig)


#----------------------------------------newly added config----------------------------------------

@dataclass
class DiscrepancyColumnAliases:
    """Shared column aliases for discrepancy data"""
    CELL_NAME: str = "Cell Name"
    ENODEB_NAME: str = "Site Name"
    COLUMN_NAME: str = "Network Parameter Name"
    OSS_VALUE: str = "OSS Value"
    DB_VALUE: str = "Asset Value"
    CHECKED_AT: str = "Discrepancy Found At"
    STATUS: str = "Status"


@dataclass
class EDSAPIConfig:
    """EDS API configuration"""
    api_base_url: Annotated[str, Field(default_factory=lambda: os.environ.get('EDS_API_BASE_URL', ''))]
    api_key: Annotated[str, Field(default_factory=lambda: os.environ.get('TEOCO_API_KEY', ''))]
    timeout: Annotated[int, Field(default_factory=lambda: int(os.environ.get('EDS_API_TIMEOUT', '60')))]
    max_retries: Annotated[int, Field(default_factory=lambda: int(os.environ.get('EDS_API_MAX_RETRIES', '2')))]

    def get_headers(self) -> Dict[str, str]:
        """Get API headers"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "api-key": self.api_key
        }

    def get_update_types(self) -> List[Dict[str, Any]]:
        """Get update type configurations"""
        return [
            {
                "data_type": "Cellv214Type",
                "api_endpoint": "Cellv214Type",
                "base_structure": {
                    "$type": "Cellv214Type"
                }
            },
            {
                "data_type": "LocationObjectv214Type",
                "api_endpoint": "LocationObjectv214Type",
                "base_structure": {
                    "$type": "LocationObjectv214Type"
                }
            },
            {
                "data_type": "MUNodev214Type",
                "api_endpoint": "MUNodev214Type",
                "base_structure": {
                    "$type": "MUNodev214Type"
                }
            }
        ]


@dataclass
class FilePathsConfig:
    """File and directory path configurations"""
    # EDS Fixer tools directory (where export folders will be created)
    eds_fixer_dir: Annotated[Path, Field(default_factory=lambda: Path(__file__).parent.parent / "tools" / "eds_fixer")]
    
    # Export directories (configurable via environment variable)
    json_export_folder: Annotated[str, Field(default_factory=lambda: os.getenv("EDS_JSON_EXPORT_FOLDER", "./json_export"))]
    
    def get_json_export_path(self) -> Path:
        """Get full path to JSON export folder"""
        return Path(self.json_export_folder)


@dataclass
class ColumnMappingConfig:
    """Column name mappings for database operations (postgres_table_updater.py uses to map csv column names to postgresql col names)"""
    column_mappings: Annotated[Dict[str, str], Field(default_factory=lambda: {
        #LTE mappings
        "TAC": "lte_tac",
        "Max Tx Power": "lte_carrierparameters_maxtxpower",
        "actTTIbundling": "lte_carrierparameters_ttibundlingenabled",
        "Physical Cell ID": "lte_carrierparameters_physicalcellid",
        "Group": "lte_carrierparameters_pcigroup_ro",
        "Code": "lte_carrierparameters_pcicode_ro",
        "Num Cyclic Shift": "lte_numcyclicshift",
        "Prach Config Index": "lte_prachconfigurationindex",
        "Prach Frequency Offset": "lte_prachfrequencyoffset",
        "AutoCalculateMethod": "lte_carrierparameters_autocalculatemethod",
        "ReferenceSignalPPRE": "lte_carrierparameters_referencesignalppre",
        "Max Scheduled Users": "lte_carrierparameters_maxscheduledusers",
        "MaxScheduledUsers": "lte_carrierparameters_maxscheduledusers",
        "Bandwidth": "lte_carrierparameters_bandwidth",
        "of TX Elements": "lte_sumimotxelems",
        "of RX Elements": "lte_sumimorxelems",
        "# of Tx Elements": "lte_sumimotxelems",
        "# of Rx Elements": "lte_sumimorxelems",
        "High Speed Flag": "lte_highspeedflag",
        "rootSeqIndex": "lte_firstassignedrsi",
        "SU-MIMO Downlink": "lte_sumimosupportdl",
        "SU-MIMO Uplink": "lte_sumimosupportul",
        "MCC": "mcc",
        "MNC": "mnc",
        #NR-specific mappings - only 1 for now as 5g discrepency data is dummy 
        "Bandwidth (MHz)": "nrt_carrierparameters_cellbandwidthparts_downlink_prbs",
    })]
    
    def get_column_mapping(self, column_name: str, technology: Optional[str] = None) -> Optional[str]:
        """Get column mapping for a given column name and technology."""
        # First try direct mapping
        if column_name in self.column_mappings:
            mapped = self.column_mappings[column_name]
            
            # If technology is specified, adjust mapping accordingly
            if technology:
                tech_upper = technology.upper()
                
                # If mapping is already for the correct technology, return as-is
                if tech_upper == "NR" and mapped.startswith("nrt_"):
                    return mapped
                elif tech_upper == "LTE" and mapped.startswith("lte_"):
                    return mapped
                
                # If mapping is for wrong technology, try to convert
                if tech_upper == "NR" and mapped.startswith("lte_"):
                    # Convert LTE mapping to NR equivalent
                    nr_mapping = mapped.replace("lte_", "nrt_", 1)
                    # Handle special cases with different structures
                    if "carrierparameters_maxscheduledusers" in mapped:
                        return "nrt_carrierparameters_cellbandwidthparts_maxscheduledusers"
                    elif "carrierparameters_bandwidth" in mapped:
                        # Bandwidth is handled differently in NR (no direct equivalent in base mapping)
                        return None  # Use explicit "Bandwidth (MHz)" mapping instead
                    return nr_mapping
                elif tech_upper == "LTE" and mapped.startswith("nrt_"):
                    # Convert NR mapping to LTE equivalent
                    lte_mapping = mapped.replace("nrt_", "lte_", 1)
                    if "cellbandwidthparts_maxscheduledusers" in mapped:
                        return "lte_carrierparameters_maxscheduledusers"
                    elif "cellbandwidthparts_downlink_prbs" in mapped:
                        # Bandwidth (MHz) maps to bandwidth in LTE
                        return "lte_carrierparameters_bandwidth"
                    return lte_mapping
            
            # Return mapping as-is if no technology specified or mapping is technology-neutral
            return mapped
        
        return None


@dataclass
class EDSColumnMappingConfig:
    """Column name mappings for EDS API JSON conversion (tool.py uses to map csv column names to EDS API JSON paths)"""
    eds_column_mappings: Annotated[Dict[str, str], Field(default_factory=lambda: {
        #LTE mappings
        "TAC": "lte.tac",
        "Max Tx Power": "lte.carrierParameters.maxTxPower",
        "actTTIbundling": "ttiBundlingEnabled",
        "Physical Cell ID": "lte.physicalCellID",
        "Group": "pciGroup_RO",
        "Code": "pciCode_RO",
        "Num Cyclic Shift": "NumCyclicShift",
        "Prach Config Index": "PrachConfigIndex",
        "Prach Frequency Offset": "PrachFrequencyOffset",
        "AutoCalculateMethod": "carrierParameters.AutoCalculateMethod",
        "ReferenceSignalPPRE": "carrierParameters.ReferenceSignalPPRE",
        "Max Scheduled Users": "carrierParameters.MaxScheduledUsers",
        "MaxScheduledUsers": "carrierParameters.MaxScheduledUsers",
        "Bandwidth": "lte.carrierParameters.bandwidth",
        "of TX Elements": "lte.suMimoTxElems",
        "of RX Elements": "lte.suMimoRxElems",
        "# of Tx Elements": "lte.suMimoTxElems",
        "# of Rx Elements": "lte.suMimoRxElems",
        "High Speed Flag": "lte.highSpeedFlag",
        "rootSeqIndex": "lte.firstAssignedRSI",
        "SU-MIMO Downlink": "lte.suMimoSupportDL",
        "SU-MIMO Uplink": "lte.suMimoSupportUL",
        "MCC": "mcc",
        "MNC": "mnc",
        #NR mappings 
        "Bandwidth (MHz)": "nrt.carrierParameters.cellBandwidthParts.downlink.prbs",
        # Additional NR-specific mappings (same column names as LTE but different paths)
        # These will be handled by get_eds_column_mapping based on technology
    })]
    
    value_conversions: Annotated[Dict[str, str], Field(default_factory=lambda: {
        "TAC": "int",
        "Max Tx Power": "float",
        "actTTIbundling": "bool",
        "Physical Cell ID": "int",
        "Group": "int",
        "Code": "int",
        "Num Cyclic Shift": "int",
        "Prach Config Index": "int",
        "Prach Frequency Offset": "int",
        "AutoCalculateMethod": "str",
        "ReferenceSignalPPRE": "float",
        "Max Scheduled Users": "int",
        "MaxScheduledUsers": "int",
        "Bandwidth": "float",
        "Bandwidth (MHz)": "int",
        "of TX Elements": "int",
        "of RX Elements": "int",
        "# of Tx Elements": "int",
        "# of Rx Elements": "int",
        "High Speed Flag": "bool",
        "rootSeqIndex": "int",
        "SU-MIMO Downlink": "bool",
        "SU-MIMO Uplink": "bool",
        "MCC": "int",
        "MNC": "int",
    })]
    
    def get_eds_column_mapping(self, column_name: str, technology: Optional[str] = None) -> Optional[str]:
        """Get EDS API JSON path for a given column name and technology."""
        if column_name not in self.eds_column_mappings:
            return None
        
        json_path = self.eds_column_mappings[column_name]
        
        # Adjust path based on technology if needed
        if technology:
            tech_upper = technology.upper()
            
            # If path is already for the correct technology, return as-is
            if tech_upper == "NR" and json_path.startswith("nrt."):
                # Already correct for NR
                return json_path
            elif tech_upper == "LTE" and json_path.startswith("lte."):
                # Already correct for LTE
                return json_path
            
            # Convert paths between technologies
            if tech_upper == "NR":
                # Handle special cases FIRST (before general conversion)
                if "MaxScheduledUsers" in json_path or "Max Scheduled Users" in column_name:
                    return "nrt.carrierParameters.cellBandwidthParts.maxScheduledUsers"
                elif "bandwidth" in json_path.lower() and "cellbandwidthparts" not in json_path.lower() and "Bandwidth (MHz)" not in column_name:
                    # Bandwidth in LTE maps to cellBandwidthParts.downlink.prbs in NR
                    return "nrt.carrierParameters.cellBandwidthParts.downlink.prbs"
                
                # Convert LTE paths to NR paths
                if json_path.startswith("lte."):
                    json_path = json_path.replace("lte.", "nrt.", 1)
                elif json_path.startswith("carrierParameters."):
                    # Paths without lte. prefix need nrt. prefix
                    json_path = f"nrt.carrierParameters.{json_path.split('.', 1)[1]}"
                # Handle paths that are at root level (like pciGroup_RO, ttiBundlingEnabled, etc.)
                # These should remain at root level for both LTE and NR
                elif not json_path.startswith("lte.") and not json_path.startswith("nrt.") and "." not in json_path:
                    # Root level fields stay at root level
                    pass
                elif not json_path.startswith("lte.") and not json_path.startswith("nrt.") and json_path.startswith(("mcc", "mnc")):
                    # MCC and MNC stay at root level
                    pass
            elif tech_upper == "LTE":
                # Convert NR paths to LTE paths
                if json_path.startswith("nrt."):
                    json_path = json_path.replace("nrt.", "lte.", 1)
                # Handle special cases
                if "cellBandwidthParts.maxScheduledUsers" in json_path:
                    return "lte.carrierParameters.maxScheduledUsers"
                elif "cellBandwidthParts.downlink.prbs" in json_path:
                    # Bandwidth (MHz) in NR maps to bandwidth in LTE
                    return "lte.carrierParameters.bandwidth"
                elif json_path.startswith("carrierParameters."):
                    # Paths without nrt. prefix need lte. prefix
                    json_path = f"lte.carrierParameters.{json_path.split('.', 1)[1]}"
        
        return json_path


@dataclass
class MinimalPayloadConfig:
    """Minimal payload structure for EDS API updates"""
    
    def get_minimal_cell_structure(self, cell_name: str, bvid: str, technology: str = "LTE") -> Dict[str, Any]:
        """
        Get minimal cell structure for EDS API payload.
        Only includes required fields. Parameters to be updated are added dynamically.
        
        Args:
            cell_name: The cell identifier (iid)
            bvid: The BVID value (e.g., "Jersey")
            technology: The technology type ("LTE" or "NR")
            
        Returns:
            Minimal cell structure dictionary
        """
        # Normalize technology
        tech_upper = technology.upper() if technology else "LTE"
        technology_fixed=False
        if tech_upper in ("NR", "5G", "5G NR"):
            tech_active = "NR"
            technology_fixed = True
        else:
            tech_active = "LTE"
            technology_fixed = False
        
        return {
            "$type": "Cellv214Type",
            "technology": {
                "fixed": technology_fixed,
                "active": tech_active
            },
            "iid": cell_name,
            "bvid": bvid
        }


@dataclass
class EDSFixerToolConfig:
    """Configuration for EDS Fixer tool"""
    # EDS API configuration
    eds_api: Annotated[EDSAPIConfig, Field(default_factory=lambda: EDSAPIConfig())]
    
    # File paths configuration
    file_paths: Annotated[FilePathsConfig, Field(default_factory=lambda: FilePathsConfig())]
    
    # Column mappings configuration (for PostgreSQL database operations)
    column_mappings: Annotated[ColumnMappingConfig, Field(default_factory=lambda: ColumnMappingConfig())]
    
    # EDS column mappings configuration (for EDS API JSON conversion)
    eds_column_mappings: Annotated[EDSColumnMappingConfig, Field(default_factory=lambda: EDSColumnMappingConfig())]
    
    # Minimal payload configuration
    minimal_payload: Annotated[MinimalPayloadConfig, Field(default_factory=lambda: MinimalPayloadConfig())]

    # Shared discrepancy column aliases
    discrepancy_aliases: Annotated[DiscrepancyColumnAliases, Field(default_factory=lambda: DiscrepancyColumnAliases())]

    # Maximum cells per EDS API batch (mirrors update_eds_tool convention)
    max_batch_size: Annotated[int, Field(default_factory=lambda: int(
        os.getenv("EDS_FIXER_MAX_BATCH_SIZE", os.getenv("MAX_BATCH_SIZE", "100"))
    ))]
