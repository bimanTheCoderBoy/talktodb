from uuid import UUID
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class SetupStatus(str, Enum):
    """Status for each setup item."""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class GoalType(str, Enum):
    """Available goal types."""
    INCREASE_RSRP = "increase_rsrp"
    RSRP_THRESHOLD = "rsrp_threshold"


# ============ REQUEST SCHEMAS ============

class PutPolygonRequest(BaseModel):
    """Request schema for updating polygon coordinates."""
    polygon_coords: List[List[float]] = Field(
        ..., 
        description="Array of [lon, lat] coordinates for SIM_AREA polygon"
    )
    boundary_coords: List[List[float]] = Field(
        ..., 
        description="Array of [lon, lat] coordinates for boundary polygon"
    )
    boundary_radius: Optional[float] = Field(
        ...,
        description="Boundary expansion radius in km"
    )
    baseline_cells: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of site objects with their selected cells for baseline coverage"
    )
    array_type: Optional[str] = Field(
        default=None,
        description="Selected array type (e.g., 'LTE_Best_RSRP', 'LTE_DL_Loss')"
    )
    technology: Optional[str] = Field(
        default=None,
        description="Coverage technology (e.g., 'LTE', 'FiveG')"
    )
    selected_band: Optional[str] = Field(
        default=None,
        description="Band selected by the user in the baseline cell selection modal"
    )


class CellsInBoundsRequest(BaseModel):
    """Request schema for getting cells within boundary."""
    boundary_coords: List[List[float]] = Field(
        ...,
        description="Array of [lon, lat] coordinates defining the boundary polygon"
    )


class DefineGoalRequest(BaseModel):
    """Request schema for defining the goal. Parameters are goal-specific (generic dict)."""
    goal_type: GoalType = Field(
        default=GoalType.INCREASE_RSRP,
        description="Type of goal"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Goal-specific parameters (keys depend on goal_type)"
    )

    @model_validator(mode="after")
    def validate_goal_params(self):
        from asp_app.config.acss_config import get_goals
        goals = get_goals()
        goal = next((g for g in goals if g.id == self.goal_type.value), None)
        if not goal:
            return self
        for p in goal.params:
            val = self.parameters.get(p.id)
            if val is None or val == "":
                raise ValueError(f"Goal {self.goal_type.value} requires parameter '{p.id}'")
            if p.type == "number":
                try:
                    num = float(val)
                except (TypeError, ValueError):
                    raise ValueError(f"Parameter '{p.id}' must be a number")
                if p.min is not None and num < p.min:
                    raise ValueError(f"Parameter '{p.id}' must be >= {p.min}")
                if p.max is not None and num > p.max:
                    raise ValueError(f"Parameter '{p.id}' must be <= {p.max}")
        return self


# ============ STATE SCHEMAS ============

class LoadProjectState(BaseModel):
    """State for load project setup item."""
    status: SetupStatus = SetupStatus.PENDING


class PolygonState(BaseModel):
    """State for polygon selection setup item."""
    status: SetupStatus = SetupStatus.PENDING
    coords: Optional[List[List[float]]] = None
    boundary_radius: float = 5.0
    boundary_coords: Optional[List[List[float]]] = None
    vertices: int = 0
    timestamp: Optional[str] = None
    baseline_cells: Optional[List[Dict[str, Any]]] = None
    array_type: Optional[str] = None


class LoadCandidateGdlState(BaseModel):
    """State for load candidate GDL setup item."""
    status: SetupStatus = SetupStatus.PENDING
    file_name: Optional[str] = None
    file_path: Optional[str] = None


class DefineGoalState(BaseModel):
    """State for define goal setup item. Parameters are goal-specific (generic dict)."""
    status: SetupStatus = SetupStatus.PENDING
    goal_type: GoalType = Field(default=GoalType.INCREASE_RSRP, alias="goalType")
    parameters: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class SetupState(BaseModel):
    """Complete setup state object."""
    load_project: LoadProjectState = Field(default_factory=LoadProjectState)
    polygon: PolygonState = Field(default_factory=PolygonState)
    load_candidate_gdl: LoadCandidateGdlState = Field(default_factory=LoadCandidateGdlState)
    define_goal: DefineGoalState = Field(default_factory=DefineGoalState)

    class Config:
        from_attributes = True


# ============ RESPONSE SCHEMAS ============

class GoalParamResponse(BaseModel):
    """Single parameter spec for a goal (for dynamic UI)."""
    id: str
    label: str
    type: str  # number, text, select
    options: List[Any] = Field(default_factory=list)
    min: Optional[float] = None
    max: Optional[float] = None


class GoalOptionResponse(BaseModel):
    """Single goal option for the goals list API."""
    id: str
    label: str
    params: List[GoalParamResponse] = Field(default_factory=list)


class GoalsListResponse(BaseModel):
    """Response containing the list of available goals."""
    goals: List[GoalOptionResponse]


class SetupStateResponse(BaseModel):
    """Response schema containing setup state."""
    session_id: UUID
    setup_state: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class PolygonUpdateResponse(BaseModel):
    """Response after updating polygon."""
    session_id: UUID
    polygon: PolygonState
    message: str = "Polygon updated successfully"

    class Config:
        from_attributes = True


class GdlUploadResponse(BaseModel):
    """Response after uploading GDL file."""
    session_id: UUID
    load_candidate_gdl: LoadCandidateGdlState
    message: str = "GDL file uploaded successfully"

    class Config:
        from_attributes = True


class GoalUpdateResponse(BaseModel):
    """Response after updating goal."""
    session_id: UUID
    define_goal: DefineGoalState
    message: str = "Goal defined successfully"

    class Config:
        from_attributes = True


# ============ CELLS IN BOUNDS SCHEMAS ============

class CellInfo(BaseModel):
    """Cell information within a site."""
    cell_iid: str
    azimuth: Optional[float] = None
    band: Optional[str] = None
    pci: Optional[int] = None
    technology: Optional[str] = None
    selected: bool = True
    antenna_device: Optional[str] = None
    master_pattern: Optional[str] = None
    antenna_height: Optional[float] = None
    mechanical_tilt: Optional[float] = None
    max_tx_power: Optional[float] = None


class SiteWithCells(BaseModel):
    """Site with its cells."""
    site_iid: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    technology: List[str] = []
    cells: List[CellInfo] = []


class CellsInBoundsResponse(BaseModel):
    """Response containing cells within boundary."""
    sites: List[SiteWithCells]
    total_sites: int
    total_cells: int

    class Config:
        from_attributes = True


# ============ AUTO-GEN SCHEMAS ============

class AutoGenConfigRequest(BaseModel):
    n: int = Field(default=5, ge=1, le=10, description="Number of candidates to auto-generate (1-10)")
    threshold_dbm: float = Field(default=-110.0, ge=-200.0, le=0.0, description="Poor-coverage RSRP threshold in dBm (-200 to 0); pixels below this are clustered")
    template_name: Optional[str] = Field(default=None, description="Antenna template name (optional, used by v1 only)")
    seed: int = Field(default=0, ge=0, description="Determinism seed; non-zero permutes input order for alternative placements")
    electrical_tilt_deg: Optional[float] = Field(default=None, ge=0.0, le=15.0, description="Electrical tilt override (optional, used by v1 only)")
    enable_population_weighting: bool = Field(default=True, description="Weight candidate-site selection by population density if raster exists")


class AutoGenConfigResponse(BaseModel):
    session_id: UUID
    load_candidate_gdl: dict


class TiltRange(BaseModel):
    """Inclusive electrical-tilt range supported by a specific antenna model."""
    min: float
    max: float


class AntennaTemplateOption(BaseModel):
    name: str
    description: str | None = None
    tilt_range: TiltRange | None = Field(
        default=None,
        description="Per-antenna electrical-tilt bounds. Frontend uses this to constrain the tilt input.",
    )
    default_tilt: float | None = Field(
        default=None,
        description="The template's baked-in default electrical tilt; the frontend pre-fills this when the template is picked.",
    )


class AntennaTemplatesResponse(BaseModel):
    default: str
    templates: list[AntennaTemplateOption]


class CandidateDeleteResponse(BaseModel):
    session_id: UUID
    deleted_site_iid: str
    remaining_count: int


class PopulationRasterStatusResponse(BaseModel):
    """Response for GET /setup/population-raster-status — tells the
    AutoGenPanel whether the "Prioritise by population density" checkbox
    should render as enabled (with population total in the hint) or
    disabled-with-hint ("no raster uploaded for project X")."""
    available: bool
    filename: Optional[str] = None
    total_population: Optional[float] = None
    error: Optional[str] = None


class EdsCleanupResponse(BaseModel):
    """Result of DELETE /setup/{session}/eds-cleanup — testing helper that
    deletes the last-created candidate sites from EDS.

    `deleted` is a per-tier count (cell/mu/location) of objects requested to
    delete. `errors` keys any tier whose delete failed; absent keys mean the
    delete succeeded or there was nothing to delete in that tier.
    """
    session_id: UUID
    deleted: Dict[str, int]
    errors: Dict[str, str] = Field(default_factory=dict)


class TiltMappingResponse(BaseModel):
    """Result of GET /setup/tilt-mapping — view of the operator-uploaded
    tilt → beam-pattern CSV.

    ``available`` is False when no CSV has been uploaded yet. ``bands`` is
    keyed by band code (``"07"``, ``"18"``, ...) → ``{tilt_deg_str: uid}``.
    ``entry_count`` is the total (band, tilt) rows across all bands.
    """
    available: bool
    entry_count: int = 0
    bands: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    path: Optional[str] = None


class TiltMappingUploadResponse(BaseModel):
    """Result of POST /setup/tilt-mapping — confirms how many rows the
    uploaded CSV parsed into, per band, so the operator can verify the
    upload matches what they expected."""
    accepted: bool
    entry_count: int
    bands: Dict[str, int] = Field(default_factory=dict)
    message: str = "Tilt mapping uploaded successfully"


class TiltMappingDeleteResponse(BaseModel):
    """Result of DELETE /setup/tilt-mapping — confirms the CSV was removed
    (auto-gen falls back to continuous tilt clamp until a new one is
    uploaded)."""
    deleted: bool
    message: str = "Tilt mapping removed"
