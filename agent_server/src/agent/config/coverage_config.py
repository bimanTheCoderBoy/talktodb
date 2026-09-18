from pathlib import Path
from pydantic import BaseModel, Field
from typing import Annotated
import os

_PAYLOAD_TEMPLATE = Path(__file__).parent.parent / "constants" / "coverage_api_payload" / "cwe_lte.json"


def normalize_path_for_platform(path: str) -> str:
    """
    Normalize path separators for the current platform.
    Converts Windows backslashes to forward slashes for Linux/Docker compatibility.
    """
    if not path:
        return path
    # Always use forward slashes for consistency (works on both Windows and Linux)
    return path.replace("\\", "/")


def join_paths(*paths: str) -> str:
    """
    Join paths using forward slashes for cross-platform compatibility.
    Filters out empty strings and normalizes separators.
    """
    normalized = [normalize_path_for_platform(p).strip("/") for p in paths if p]
    return "/" + "/".join(normalized) if normalized else ""


def to_unc_path(path: str) -> str:
    """
    Convert a path like /host/path/parts to UNC format \\host\\path\\parts.
    Used for API payload output.location so the coverage service receives a valid UNC path.
    """
    if not path or not path.strip():
        return path
    normalized = path.strip().replace("\\", "/").strip("/")
    if not normalized:
        return path
    parts = [p for p in normalized.split("/") if p]
    if not parts:
        return path
    return "\\\\" + "\\".join(parts)


def path_for_bil_retrieval(path: str) -> str:
    """
    Format path for BIL file retrieval only. OS-aware:
    - Windows: UNC format (\\host\\path\\parts) for network/share access.
    - Linux/Docker: keep Linux structure (forward slashes, e.g. /mnt/mapdata/...).
    Do not use for coverage API payload; use to_unc_path for that.
    """
    if not path or not path.strip():
        return path
    normalized = path.strip().replace("\\", "/").strip("/")
    if not normalized:
        return path
    parts = [p for p in normalized.split("/") if p]
    if not parts:
        return path
    if os.name == "nt":
        return "\\\\" + "\\".join(parts)
    return "/" + "/".join(parts)


class CoverageAPIConfig(BaseModel):
    """Configuration for Coverage API settings."""
    create_coverage_endpoint: Annotated[str, Field(default=os.getenv("COVERAGE_API_CREATE_COVERAGE_ENDPOINT", ""))]
    status_polling_endpoint: Annotated[str, Field(default=os.getenv("COVERAGE_API_STATUS_POLLING_ENDPOINT", ""))]
    api_key: Annotated[str, Field(default=os.getenv("TEOCO_COVERAGE_API_KEY", ""))]
    payload_store: Annotated[str, Field(default=os.getenv("COVERAGE_API_PAYLOAD_STORE", "Rest_CWE"))]
    maximum_payload_folder_length: Annotated[int, Field(default=int(os.getenv("MAXIMUM_COVERAGE_API_PAYLOAD_FOLDER_LENGTH", "30")))]
    payload_output_type: Annotated[str, Field(default=os.getenv("COVERAGE_API_PAYLOAD_OUTPUT_TYPE", ""))]
    payload_output_name: Annotated[str, Field(default=os.getenv("COVERAGE_API_PAYLOAD_OUTPUT_NAME", ""))]
    payload_root_output_location: Annotated[str, Field(default=os.getenv("ROOT_OUTPUT_LOCATION_ROOT_OUTPUT_LOCATION", ""))]
    payload_default_output_location: Annotated[str, Field(default=os.getenv("COVERAGE_API_PAYLOAD_DEFAULT_OUTPUT_LOACTION", ""))]
    payload_template_path: Annotated[str, Field(default=str(_PAYLOAD_TEMPLATE))]
    # Separate path for retrieving BIL files (supports cross-platform Docker mounting)
    bil_file_root_retrieval_path: Annotated[str, Field(default=os.getenv("BIL_FILE_ROOT_RETRIEVAL_PATH", ""))]


class CoverageReportConfig(BaseModel):
    """Configuration for Coverage Report settings."""
    kml_folder_root_path: Annotated[str, Field(default=os.getenv("COVERAGE_KML_FOLDER_ROOT_PATH", "./KML_Folder"))]
    report_folder_path: Annotated[str, Field(default=os.getenv("COVERAGE_REPORT_FOLDER_PATH", "./Report_Folder"))]
    maximum_report_folder_length: Annotated[int, Field(default=int(os.getenv("MAXIMUM_COVERAGE_REPORT_FOLDER_LENGTH", "30")))]


# Maximum number of times a tool can be called consecutively
MAXIMUM_TOOL_RECURSION_LIMIT = int(os.getenv("COVERAGE_MAX_TOOL_RECURSION_LIMIT", "10"))

COVERAGE_PNG_ENCODING_PATH = os.getenv("COVERAGE_PNG_ENCODING_PATH")

# Maximum number of days to keep PNG encoding folders before cleanup (default: 7 days)
MAX_COVERAGE_PNG_VALIDITY_IN_DAYS = int(os.getenv("MAX_COVERAGE_PNG_VALIDITY_IN_DAYS", "7"))


import os
from pydantic import BaseModel, Field
from typing import Annotated

IS_LOCAL_LLM_PROVIDER = os.getenv("IS_LOCAL_LLM_PROVIDER", "false") == "true"
class Coverage_IID_Executor_LLMConfig(BaseModel):
    """LLM configuration for Coverage Agent."""
    api_key: Annotated[str, Field(default=os.getenv("OPENROUTER_API_KEY"))]
    base_url: Annotated[str, Field(default=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))]
    model: Annotated[str, Field(default=os.getenv("OPENROUTER_MODEL_COVERAGE_IID_EXECUTOR", "google/gemini-2.0-flash-001"))]
    temperature: Annotated[float, Field(default=float(os.getenv("COVERAGE_LLM_TEMPERATURE", "0.2")))]
    max_retries: Annotated[int, Field(default=int(os.getenv("OPENROUTER_MAX_RETRIES", "3")))]
    request_timeout: Annotated[int, Field(default=int(os.getenv("OPENROUTER_REQUEST_TIMEOUT", "30")))]
    disable_streaming: Annotated[bool, Field(default=True)]
    if not IS_LOCAL_LLM_PROVIDER:
            extra_body: Annotated[dict, Field(default={
         "provider": {"order": os.getenv("PROVIDER_ORDER", "google-vertex,deepinfra,parasail,atlas-cloud,novita").split(","), "allow_fallbacks": True},
    })]     
    # reasoning:Annotated[dict, Field(default={
    #     "effort": "medium",
    #     "summary": "auto"
    # })]

