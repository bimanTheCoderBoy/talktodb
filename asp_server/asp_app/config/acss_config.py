import os
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Annotated, Any
from functools import lru_cache

_THIS_DIR = Path(__file__).resolve().parent


def normalize_path_for_platform(path: str) -> str:
    """
    Normalize path separators for the current platform.
    Converts Windows backslashes to forward slashes for Linux/Docker compatibility.
    """
    if not path:
        return path
    return path.replace("\\", "/")


def join_paths(*paths: str) -> str:
    """
    Join paths using forward slashes for cross-platform compatibility.
    Filters out empty strings and normalizes separators.
    """
    normalized = [normalize_path_for_platform(p).strip("/") for p in paths if p]
    return "/" + "/".join(normalized) if normalized else ""


class ACSSConfig(BaseModel):
    """Main ACSS Application Configuration."""
    app_name: Annotated[str, Field(default=os.getenv("ACSS_APP_NAME", "ACSS Backend"))]
    app_version: Annotated[str, Field(default=os.getenv("ACSS_APP_VERSION", "1.0.0"))]
    debug: Annotated[bool, Field(default=os.getenv("ACSS_DEBUG", "false").lower() == "true")]
    host: Annotated[str, Field(default=os.getenv("ACSS_HOST", "0.0.0.0"))]
    port: Annotated[int, Field(default=int(os.getenv("ACSS_PORT", "8001")))]
    gdl_storage_dir: Annotated[str, Field(default=os.getenv("GDL_STORAGE_DIR", "./teoco_data_store/candidate_gdls"))]
    acss_result_dir: Annotated[str, Field(default=os.getenv("ACSS_RESULT_DIR", "./teoco_data_store/acss_results"))]
    acss_map_encoded_dir: Annotated[str, Field(default=os.getenv("ACSS_MAP_ENCODED_DIR", "./teoco_data_store/acss_map_encoded_files"))]
    # Per-project population rasters used optionally by ASP / ACSS auto-gen
    # to weight candidate-site selection by population density. Layout:
    #   <population_rasters_dir>/<project_name_lowercase>/<file>.tif
    # When the per-project subfolder is absent or empty, the auto-gen step
    # falls through to uniform weighting (no behaviour change).
    population_rasters_dir: Annotated[str, Field(default=os.getenv("POPULATION_RASTERS_DIR", "./teoco_data_store/population_rasters"))]
    

class DatabaseConfig(BaseModel):
    """Database Configuration."""
    db_user: Annotated[str, Field(default=os.getenv("ACSS_DB_USER", "csv_user"))]
    db_password: Annotated[str, Field(default=os.getenv("ACSS_DB_PASSWORD", "csv_password"))]
    db_host: Annotated[str, Field(default=os.getenv("ACSS_DB_HOST", "localhost"))]
    db_port: Annotated[int, Field(default=int(os.getenv("ACSS_DB_PORT", "5432")))]
    pool_size: Annotated[int, Field(default=int(os.getenv("ACSS_DB_POOL_SIZE", "10")))]
    max_overflow: Annotated[int, Field(default=int(os.getenv("ACSS_DB_MAX_OVERFLOW", "20")))]
    
    def get_database_url(self, db_name: str) -> str:
        """Generate database URL for a specific database."""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{db_name}"


class KMLConfig(BaseModel):
    """Configuration for KML Processing."""
    kml_folder_root_path: Annotated[str, Field(default=os.getenv("ACSS_KML_FOLDER_ROOT_PATH", "./teoco_data_store/KML_files"))]



class CORSConfig(BaseModel):
    """CORS Configuration."""
    allow_origins: Annotated[list, Field(default_factory=lambda: os.getenv("ACSS_CORS_ORIGINS", "*").split(","))]
    allow_credentials: Annotated[bool, Field(default=os.getenv("ACSS_CORS_CREDENTIALS", "true").lower() == "true")]
    allow_methods: Annotated[list, Field(default_factory=lambda: os.getenv("ACSS_CORS_METHODS", "*").split(","))]
    allow_headers: Annotated[list, Field(default_factory=lambda: os.getenv("ACSS_CORS_HEADERS", "*").split(","))]



class RedisConfig(BaseModel):
    """Redis Configuration."""
    redis_url: Annotated[str, Field(default=os.getenv("REDIS_URL", "redis://localhost:6379"))]


class CoverageAPIConfig(BaseModel):
    """Configuration for Coverage API settings."""
    create_coverage_endpoint: Annotated[str, Field(default=os.getenv("COVERAGE_API_CREATE_ENDPOINT", ""))]
    status_polling_endpoint: Annotated[str, Field(default=os.getenv("COVERAGE_API_STATUS_ENDPOINT", ""))]
    api_key: Annotated[str, Field(default=os.getenv("COVERAGE_API_KEY", ""))]
    payload_store: Annotated[str, Field(default=os.getenv("COVERAGE_PAYLOAD_STORE", "./teoco_data_store/acss_coverage_payloads"))]
    payload_output_type: Annotated[str, Field(default=os.getenv("COVERAGE_OUTPUT_TYPE", "BILGRC"))]
    payload_root_output_location: Annotated[str, Field(default=os.getenv("COVERAGE_ROOT_OUTPUT_LOCATION", ""))]
    coverage_root_output_retrieval_location: Annotated[str, Field(default=os.getenv("COVERAGE_ROOT_OUTPUT_RETRIEVAL_LOCATION", ""))]
    # default_output_location: Annotated[str, Field(default=os.getenv("COVERAGE_DEFAULT_OUTPUT_LOCATION", ""))]
    max_polls: Annotated[int, Field(default=int(os.getenv("COVERAGE_MAX_POLLS", "360")))]
    poll_interval: Annotated[int, Field(default=int(os.getenv("COVERAGE_POLL_INTERVAL", "10")))]
    payload_template_path: Annotated[str, Field(default=str(_THIS_DIR.parent / "constants" / "coverage_payloads" / "cwe_lte_template.json"))]

class CandidateConfig(BaseModel):
    """Configuration for columns."""
    columns_config_path: Annotated[str, Field(default=str(_THIS_DIR / "json_config" / "lte" / "columns.json"))]
    eds_create_url: Annotated[str, Field(default=os.getenv("EDS_CREATE_URL", ""))]
    eds_delete_url: Annotated[str, Field(default=os.getenv("EDS_DELETE_URL", ""))]


class GoalParamSpec(BaseModel):
    """Spec for a single goal parameter (drives UI and validation)."""
    id: str
    label: str
    type: Annotated[str, Field(description="One of: number, text, select")]
    options: Annotated[list[Any], Field(default_factory=list)]  # for select type
    min: Annotated[float | None, Field(default=None, description="Inclusive min for number params")]
    max: Annotated[float | None, Field(default=None, description="Inclusive max for number params")]


class GoalOption(BaseModel):
    """Single goal option for the Define Goal step."""
    id: str
    label: str
    params: Annotated[list[GoalParamSpec], Field(default_factory=list)]


# List of available goals; add new goals here without touching request/UI code
GOALS: list[GoalOption] = [
    GoalOption(
        id="increase_rsrp",
        label="Increase RSRP by x %",
        params=[
            GoalParamSpec(
                id="x_value",
                label="X Value (% increase)",
                type="number",
                min=0,
                max=100,
            ),
            GoalParamSpec(id="k_value", label="K Value (best combinations)", type="select", options=[1, 2]),
        ],
    ),
    GoalOption(
        id="rsrp_threshold",
        label="Make sure RSRP threshold will be x",
        params=[
            GoalParamSpec(id="threshold_value", label="Threshold (x)", type="number"),
            GoalParamSpec(id="k_value", label="K Value (best combinations)", type="select", options=[1, 2]),
        ],
    ),
]


def get_goals() -> list[GoalOption]:
    """Return the list of available goal options for the UI."""
    return list(GOALS)


@lru_cache()
def get_acss_config() -> ACSSConfig:
    """Get cached ACSS configuration."""
    return ACSSConfig()


@lru_cache()
def get_database_config() -> DatabaseConfig:
    """Get cached database configuration."""
    return DatabaseConfig()


@lru_cache()
def get_kml_config() -> KMLConfig:
    """Get cached KML configuration."""
    return KMLConfig()


@lru_cache()
def get_cors_config() -> CORSConfig:
    """Get cached CORS configuration."""
    return CORSConfig()

@lru_cache()
def get_redis_config() -> RedisConfig:
    """Get cached Redis configuration."""
    return RedisConfig()


@lru_cache()
def get_coverage_api_config() -> CoverageAPIConfig:
    """Get cached Coverage API configuration."""
    return CoverageAPIConfig()

@lru_cache()
def get_candidate_config() -> CandidateConfig:
    """Get cached Candidate configuration."""
    return CandidateConfig()


def get_antenna_template_catalog_path() -> str:
    """Return the absolute path to the static antenna template catalog JSON.

    The catalog lives alongside the other json_config files and is consumed
    by services.autogen.template_loader.load_antenna_templates in plan 02-04.
    """
    return str(_THIS_DIR / "json_config" / "antenna_templates.json")


def get_tilt_mapping_sample_path() -> str:
    """Absolute path to the read-only **sample** tilt → beam-pattern CSV.

    Shipped with the image (not user-writable). Served via
    ``GET /setup/tilt-mapping/sample`` so engineers can download a working
    starter file, edit it for their antenna inventory, and re-upload via
    ``POST /setup/tilt-mapping``.

    The sample carries all bands and tilts derived from the example
    ASSET export (``ANTENNA-LIST001.xml`` at repo root) — engineers
    keep what's relevant, delete the rest, or replace entirely.
    """
    return str(_THIS_DIR / "json_config" / "tilt_mapping.sample.csv")


def get_tilt_mapping_path() -> str:
    """Absolute path to the operator-uploaded tilt → beam-pattern CSV.

    Schema (header row required)::

        band_code,tilt_deg,beam_pattern_name
        07,2.0,ERICSSON_AIR3237_B78K_P\\07_20
        07,7.0,ERICSSON_AIR3237_B78K_P\\07_70
        ...

    ``band_code`` is the two-digit band identifier embedded in the beam-pattern
    UID (``07`` → 787 MHz, ``18`` → 1859 MHz, ...).
    ``tilt_deg`` is the electrical tilt the named beam pattern actually carries.
    ``beam_pattern_name`` is the GDL device/pattern UID the EDS Create payload
    will reference.

    The file is **uploaded by the engineer** via ``POST /setup/tilt-mapping``
    and lives at this path. When absent, the auto-gen step falls back to a
    continuous tilt-range clamp (no beam-pattern resolution).

    Override path with the ``TILT_MAPPING_CSV_PATH`` env var.
    """
    override = os.environ.get("TILT_MAPPING_CSV_PATH")
    if override:
        return override
    return str(_THIS_DIR / "json_config" / "tilt_mapping.csv")