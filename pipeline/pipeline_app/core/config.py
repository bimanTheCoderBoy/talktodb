"""
Pipeline configuration classes using Pydantic and environment variables.
"""
import os
from pathlib import Path
from typing import Annotated, Dict, List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env file from the current working directory
load_dotenv()


def _default_project_name() -> str:
    """Resolve the project name from environment with a stable fallback."""
    return os.getenv("PROJECT_NAME", "Nos_portugal")


def _default_query_filter() -> str:
    """Resolve API query filter, deriving from project when unset."""
    project_name = _default_project_name()
    return os.getenv("EDS_QUERY_FILTER", f'bvid = "{project_name}"')


class DBConfig(BaseModel):
    """Database configuration loaded from environment variables."""
    host: Annotated[str, Field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))]
    port: Annotated[int, Field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))]
    user: Annotated[str, Field(default_factory=lambda: os.getenv("DB_USER", "csv_user"))]
    password: Annotated[str, Field(default_factory=lambda: os.getenv("DB_PASSWORD", "csv_password"))]
    pool_size: Annotated[int, Field(default_factory=lambda: int(os.getenv("DB_POOL_SIZE", "5")))]
    max_overflow: Annotated[int, Field(default_factory=lambda: int(os.getenv("DB_POOL_MAX_OVERFLOW", "10")))]
    pool_pre_ping: Annotated[bool, Field(default_factory=lambda: bool(os.getenv("DB_POOL_PRE_PING", "True")))]
    pool_recycle: Annotated[int, Field(default_factory=lambda: int(os.getenv("DB_POOL_RECYCLE", "3600")))]
    rls_user: Annotated[str, Field(default_factory=lambda: os.getenv("RLS_DB_USER", "app_reader"))]
    rls_password: Annotated[str, Field(default_factory=lambda: os.getenv("RLS_USER_PASSWORD", "app_reader"))]


class APIConfig(BaseModel):
    """EDS API configuration loaded from environment variables."""
    base_url: Annotated[str, Field(default_factory=lambda: os.getenv("EDS_API_BASE_URL", "http://d48d-ast-app01.emea.teo.earth:8687/v1/EDS/Query/"))]
    api_key: Annotated[str, Field(default_factory=lambda: os.getenv("EDS_API_KEY", "teoco"))]
    max_results: Annotated[int, Field(default_factory=lambda: int(os.getenv("EDS_MAX_RESULTS", "100")))]
    timeout: Annotated[int, Field(default_factory=lambda: int(os.getenv("EDS_TIMEOUT", "300")))]
    query_filter: Annotated[Optional[str], Field(default_factory=_default_query_filter)]
    max_concurrent: Annotated[int, Field(default_factory=lambda: int(os.getenv("EDS_MAX_CONCURRENT", "50")))]
    queue_size: Annotated[int, Field(default_factory=lambda: int(os.getenv("EDS_QUEUE_SIZE", "10")))]

    def get_headers(self) -> Dict[str, str]:
        """Get API headers for requests."""
        return {    
            "Accept": "application/json",
            "api-key": self.api_key
        }


def _resolve_project_folder(root: Path, project_name: str) -> Path:
    """Case-insensitive lookup for a project subfolder under *root*.

    Scans existing directories and returns the first whose name matches
    *project_name* ignoring case.  If nothing matches, returns
    ``root / project_name`` so callers get a deterministic path that
    can be created or will produce a clear "not found" error downstream.
    """
    target = project_name.lower()
    if root.is_dir():
        for child in root.iterdir():
            if child.is_dir() and child.name.lower() == target:
                return child
    return root / project_name


class PathsConfig(BaseModel):
    """File path configurations loaded from environment variables."""
    oss_csv_folder: Annotated[str, Field(default_factory=lambda: os.getenv("OSS_CSV_FOLDER", "./teoco_data_store/oss-csv"))]
    update_folder: Annotated[str, Field(default_factory=lambda: os.getenv("UPDATE_FOLDER", "./teoco_data_store/discrepancy"))]
    csv_export_folder: Annotated[str, Field(default_factory=lambda: os.getenv("CSV_EXPORT_FOLDER", "./teoco_data_store/csv_export"))]

    def get_oss_csv_path(self, project_name: Optional[str] = None) -> Path:
        """Get the OSS CSV input folder.

        When *project_name* is provided, resolves to the matching project
        subfolder using case-insensitive lookup (e.g. ``oss-csv/Nos_Portugal``
        matches project name ``nos_portugal``).  Falls back to the exact name
        if no existing folder matches.
        """
        root = Path(self.oss_csv_folder)
        if not project_name:
            return root
        return _resolve_project_folder(root, project_name)

    def get_update_path(self) -> Path:
        """Get full path to update folder (for discrepancies/comparisons)."""
        return Path(self.update_folder)

    def get_csv_export_path(self) -> Path:
        """Get full path to CSV export folder (for export.csv files)."""
        return Path(self.csv_export_folder)



class EntityConfig(BaseModel):
    """Per-entity configuration for API query type and table mapping."""
    query_type: str  # E.g., "LocationObjectv214Type", "MUNodev214Type", "Cellv214Type"
    table_name: str  # E.g., "location", "mu", "cell"
    csv_filename_prefix: Optional[str] = None  # CSV filename prefix (defaults to table_name)

    def __init__(self, **data):
        super().__init__(**data)
        if self.csv_filename_prefix is None:
            self.csv_filename_prefix = self.table_name


class AuditColumnMapping:
    """Column mapping defaults for audit flows."""

    @classmethod
    def get_default_mappings(cls) -> Dict[str, str]:
        """Get default column mappings for Cell LTE audit.

        Keys must match the exact column headers in the 4G OSS CSV file.
        """
        return {
            "EARFCN DL":           "lte_carrierparameters_iid",
            "TAC":                 "lte_tac",
            "Max Tx Power":        "lte_carrierparameters_maxtxpower",
            "Max Scheduled Users": "lte_carrierparameters_maxscheduledusers",
            "# of Tx Elements":    "lte_sumimotxelems",
            "# of Rx Elements":    "lte_sumimorxelems",
            "Physical Cell ID":    "lte_carrierparameters_physicalcellid",
            # "Bandwidth (MHz)":     "lte_carrierparameters_bandwidth",
            "actTTIbundling":      "lte_carrierparameters_ttibundlingenabled",
            "High Speed Flag":     "lte_highspeedflag",
            "rootSeqIndex":        "lte_carrierparameters_pcigroup_ro"
            # "SU-MIMO Downlink":    "lte_sumimosupportdl",
            # "SU-MIMO Uplink":      "lte_sumimosupportul"
        }

    @classmethod
    def get_default_mappings_nr(cls) -> Dict[str, str]:
        """Get default column mappings for Cell NR audit."""
        return {
            "TAC": "nrt_tac",
            "Max Tx Power": "nrt_carrierparameters_maxtxpower",
            "Max Scheduled Users": "nrt_carrierparameters_cellbandwidthparts_maxscheduledusers",
            "# of Tx Elements": "nrt_sumimotxelems",
            "# of Rx Elements": "nrt_sumimorxelems",
            "Physical Cell ID": "nrt_carrierparameters_physicalcellid",
            "Bandwidth (MHz)": "nrt_carrierparameters_cellbandwidthparts_downlink_prbs",
            "SU-MIMO Downlink": "nrt_sumimosupportdl",
            "SU-MIMO Uplink": "nrt_sumimosupportul"
        }

    @classmethod
    def get_discrepancy_column_mappings(cls) -> Dict[str, str]:
        """Get default column mappings for discrepancy table i.e. csv name to db column name"""
        return {
            'cellname': 'cell_name',
                'enodeb name': 'enodeb_name',
                'enodeb_name': 'enodeb_name',
                'column': 'column_name',
                'oss_value': 'oss_value',
                'db_value': 'db_value',
                'location_eid': 'location_eid',
                'cell_eid': 'cell_eid',
                'technology': 'technology',
                'status': 'status',
                'checked_at': 'checked_at'
        }


class PipelineConfig(BaseModel):
    """Main pipeline configuration combining all sub-configs."""
    db: Annotated[DBConfig, Field(default_factory=DBConfig)]
    api: Annotated[APIConfig, Field(default_factory=APIConfig)]
    paths: Annotated[PathsConfig, Field(default_factory=PathsConfig)]
    project_name: Annotated[str, Field(default_factory=_default_project_name)]
    rls_user: Annotated[str, Field(default_factory=lambda: os.getenv("RLS_DB_USER", "app_reader"))]
    rls_password: Annotated[str, Field(default_factory=lambda: os.getenv("RLS_USER_PASSWORD", "app_reader"))]
    auto_audit_enabled: Annotated[bool, Field(
        default_factory=lambda: os.getenv("AUTOMATIC_AUDIT_FLOW", "false").lower() in ("true", "1", "yes"),
    )]

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        """Create PipelineConfig from environment variables."""
        return cls()

    def overwrite_project_name(self, new_project_name: str) -> None:
        """Overwrite runtime project and keep API filter in sync."""
        cleaned_name = new_project_name.strip()
        if not cleaned_name:
            raise ValueError("Project name cannot be empty.")

        self.project_name = cleaned_name
        self.api.query_filter = f'bvid = "{cleaned_name}"'


    def get_entity_configs(self) -> Dict[str, EntityConfig]:
        """Get default entity configurations."""
        return {
            "location": EntityConfig(
                query_type="LocationObjectv214Type",
                table_name="location"
            ),
            "mu_lte": EntityConfig(
                query_type="MUNodev214Type",
                table_name="mu_lte"
            ),
            "mu_nr": EntityConfig(
                query_type="MUNodev214Type",
                table_name="mu_nr"
            ),
            "cell_lte": EntityConfig(
                query_type="Cellv214Type",
                table_name="cell_lte"
            ),
            "cell_nr": EntityConfig(
                query_type="Cellv214Type",
                table_name="cell_nr"
            ),
            "cell_logical_antenna": EntityConfig(
                query_type="Cellv214Type",  # Uses cell data but extracts feeders
                table_name="cell_logical_antenna"
                
            ),
            "cell_physical_antenna": EntityConfig(
                query_type="Cellv214Type",  # Uses cell data but extracts feeders
                table_name="cell_physical_antenna"
                
            ),
        }

