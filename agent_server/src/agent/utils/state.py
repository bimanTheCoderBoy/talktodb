from langchain_core.messages import AnyMessage, HumanMessage
from pydantic import BaseModel
from typing import Optional, List, Annotated, Dict, Any
import operator


# ── CUSTOM Reducers ──────────────────────────────────────────────────────────

RESET_SENTINEL = "__RESET__"
# for parallel execution we need a reducer and we can't use operator.add beacue we cannot reset it when required

def resettable_add(existing: list, new: list) -> list:
    """Like operator.add, but resets the list when [RESET_SENTINEL] is received."""
    if new and len(new) == 1 and new[0] == RESET_SENTINEL:
        return []
    return existing + new


# ── Shared / reusable models ──────────────────────────────────────────

class CoverageUrlConfig(BaseModel):
    """API URL query-parameter settings for one technology."""
    technology: str = "LTE"
    resolution: str = "50"
    mode: str = "Composite"
    terminal: str = "Multi-Tech Default"
    height: Optional[str] = None
    carrier: Optional[str] = None
    autoApprove: bool = True


class ArrayTypeOption(BaseModel):
    """Single selectable array-type shown in the parameter modal."""
    value: str
    label: str
    isSelected: bool = False


class TechParameters(BaseModel):
    """Per-technology parameter selections from the interrupt modal."""
    arrayTypes: List[ArrayTypeOption] = []


class TechOutput(BaseModel):
    """Per-technology output path/name chosen in the interrupt modal."""
    path: str = ""
    name: str = ""


class TechExecution(BaseModel):
    """
    Per-technology execution result written by coverage_run_tech_pipeline.
    One instance lives at coverage_state.lte and another at coverage_state.nr.
    """
    iids: Optional[List[str]] = None
    array_types: List[str] = []
    output_path: str = ""
    output_name: str = ""
    url_config: Optional[CoverageUrlConfig] = None
    payload_file: Optional[str] = None
    token: Optional[str] = None
    api_called: bool = False
    poll_count: int = 0
    success: Optional[bool] = None
    error: Optional[str] = None


# ── Coverage State ────────────────────────────────────────────────────
#
#  Single nested model that holds ALL coverage-related data across every
#  phase:  cell-discovery  →  interrupt modal  →  execution  →  results.

class CoverageState(BaseModel):

    # ── Phase 1: Cell discovery (build phase) ─────────────────────────
    # Populated by get_cell_iids_node
    iids: Optional[List[str]] = None

    # ── Phase 2: Interrupt modal (user approval) ──────────────────────
    # Populated by iids_map_payload_interrupt after user approves/edits
    boundaries: Optional[List[List[float]]] = None
    is_user_defined_polygon: Optional[bool] = None
    parameters: Optional[Dict[str, TechParameters]] = None
    output: Optional[Dict[str, TechOutput]] = None
    url_parameter_settings: Optional[Dict[str, CoverageUrlConfig]] = None
    user_approved: Optional[bool] = None

    # ── Phase 3: Per-technology execution results ─────────────────────
    # Written by coverage_tech_aggregation from tech_results after the
    # parallel Send pipelines finish.
    lte: Optional[TechExecution] = None
    nr: Optional[TechExecution] = None



# ── Main graph state ──────────────────────────────────────────────────

class State(BaseModel):
    # ── Core message channels ─────────────────────────────────────────
    input_message: HumanMessage
    # Append-only UI-facing message log
    messages: Annotated[List[AnyMessage], operator.add] = []
    # Internal message context for the master agent LLM loop
    main_message_context: List[AnyMessage] = []
    # Internal message context for the coverage IID-discovery LLM loop
    coverage_message_context: List[AnyMessage] = []
    coverage_message_context_clean_flag: bool = False

    # ── Nested coverage state (all phases) ────────────────────────────
    coverage_state: Optional[CoverageState] = CoverageState()

    # ── Parallel execution reducer channels ───────────────────────────
    # tech_results: collects dicts returned by each Send branch of
    # coverage_run_tech_pipeline.  Uses resettable_add so parallel
    # branches append results, but the list can be cleared with
    # [RESET_SENTINEL] at the start of a fresh coverage run.
    tech_results: Annotated[List[Dict[str, Any]], resettable_add] = []
    # Map viewer result dict, written by coverage_map_viewer_node
    coverage_map_result: Optional[Dict[str, Any]] = None
    # Report generation result dict, written by coverage_generate_reports_node
    coverage_report_result: Optional[Dict[str, Any]] = None

    # ── Global metadata ───────────────────────────────────────────────
    error: Optional[str] = None
    project_name: Optional[str] = None
    user_email: Optional[str] = None

    # Encryption: accumulated hash-to-value entries for decrypt
    encryption_entries: List[Dict[str, Any]] = []


class ctx_schema_State(BaseModel):
    user_email: str = ""
    project_name: str = ""
