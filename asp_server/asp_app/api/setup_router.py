import os
import shutil

from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import FileResponse
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from asp_app.db.schemas.setup import (
    PutPolygonRequest,
    DefineGoalRequest,
    PolygonUpdateResponse,
    GdlUploadResponse,
    GoalUpdateResponse,
    GoalsListResponse,
    GoalOptionResponse,
    GoalParamResponse,
    SetupStateResponse,
    CellsInBoundsRequest,
    CellsInBoundsResponse,
    EdsCleanupResponse,
    AutoGenConfigRequest,
    AutoGenConfigResponse,
    AntennaTemplatesResponse,
    AntennaTemplateOption,
    CandidateDeleteResponse,
    PopulationRasterStatusResponse,
    TiltMappingResponse,
    TiltMappingUploadResponse,
    TiltMappingDeleteResponse,
)
from asp_app.config.acss_config import (
    get_goals,
    get_tilt_mapping_path,
    get_tilt_mapping_sample_path,
)
from asp_app.services.setup_service import SetupService
from asp_app.services.cells_service import CellsService
from asp_app.services.candidate_services.candidate_service import CandidateService
from asp_app.services.autogenv2.orchestrator import save_autogen_config, delete_candidate
from asp_app.services.autogen.template_loader import load_antenna_templates
from asp_app.services.autogen.tilt_mapping import load_tilt_mapping, dump_mapping, reload_tilt_mapping
from asp_app.services.autogen.population_weight import get_population_status
from asp_app.db.database import get_db_session, get_rls_db_session
from asp_app.db.redis import get_redis_client
from redis import Redis

router = APIRouter(
    prefix="/setup",
    tags=["Setup"]
)


@router.get("/goals", response_model=GoalsListResponse)
async def get_goals_list():
    """
    Get the list of available goal types for the Define Goal step.
    No session required. Used by the frontend to populate the goal-type dropdown.
    """
    goals = get_goals()
    return GoalsListResponse(
        goals=[
            GoalOptionResponse(
                id=g.id,
                label=g.label,
                params=[
                    GoalParamResponse(
                        id=p.id,
                        label=p.label,
                        type=p.type,
                        options=p.options,
                        min=p.min,
                        max=p.max,
                    )
                    for p in g.params
                ],
            )
            for g in goals
        ]
    )


@router.put("/{acss_session_id}/polygon", response_model=PolygonUpdateResponse)
async def put_polygon(
    acss_session_id: UUID,
    polygon_data: PutPolygonRequest,
    db: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    Update polygon and boundary coordinates for a session.
    Optionally includes baseline_cells and array_type for baseline coverage.
    """
    session = await SetupService.put_polygon(db, acss_session_id, polygon_data, redis_client)
    return PolygonUpdateResponse(
        session_id=session.id,
        polygon=session.setup_state.get("polygon", {})
    )


@router.post("/{acss_session_id}/cells-in-bounds", response_model=CellsInBoundsResponse)
async def get_cells_in_bounds(
    acss_session_id: UUID,
    request: CellsInBoundsRequest,
    db: AsyncSession = Depends(get_rls_db_session),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    Get all cells within the specified boundary polygon.
    
    This endpoint queries the project database for cells whose locations
    fall within the provided boundary coordinates.
    
    Returns sites grouped with their cells, with all cells selected by default.
    """
    return await CellsService.get_cells_in_bounds(db, request.boundary_coords, redis_client, acss_session_id)


@router.get("/{acss_session_id}/gdl/download")
async def download_gdl_csv(
    acss_session_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Return selected columns from the stored GDL file as JSON.

    Works for both manually uploaded and auto-generated GDL files.
    The frontend converts this to a CSV for download.
    """
    return await SetupService.get_gdl_for_download(db, acss_session_id)


@router.post("/{acss_session_id}/gdl", response_model=GdlUploadResponse)
async def upload_gdl(
    acss_session_id: UUID,
    file: UploadFile = File(..., description="CSV or Excel file containing candidate GDL data"),
    db: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    Upload candidate GDL file for a session.
    
    Accepts CSV (.csv) or Excel (.xlsx, .xls) files.
    The file will be stored in teoco_data_store/candidate_gdls/.
    """
    session = await SetupService.upload_gdl(db, acss_session_id, file, redis_client)
    return GdlUploadResponse(
        session_id=session.id,
        load_candidate_gdl=session.setup_state.get("loadCandidateGdl", {})
    )


@router.put("/{acss_session_id}/goal", response_model=GoalUpdateResponse)
async def define_goal(
    acss_session_id: UUID,
    goal_data: DefineGoalRequest,
    db: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    Define the optimization goal for a session.
    Currently supports:
    - increase_rsrp: Increase RSRP by 'x' dBm for best 'k' cells
    """
    session = await SetupService.define_goal(db, acss_session_id, goal_data, redis_client)
    
    return GoalUpdateResponse(
        session_id=session.id,
        define_goal=session.setup_state.get("defineGoal", {})
    )


@router.delete("/{acss_session_id}/eds-cleanup", response_model=EdsCleanupResponse)
async def cleanup_eds_sites(
    acss_session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client),
):
    """Delete the last-created candidate sites from EDS for a session."""
    project_name = request.headers.get("x-project-name", "")
    result = await CandidateService.cleanup_eds_sites_for_session(
        db, acss_session_id, project_name, redis_client,
    )
    return EdsCleanupResponse(
        session_id=acss_session_id,
        deleted=result["deleted"],
        errors=result.get("errors", {}),
    )


# ============ AUTO-GEN ROUTES ============


@router.get("/antenna-templates", response_model=AntennaTemplatesResponse)
async def get_antenna_templates():
    """List available antenna templates for the auto-gen template dropdown."""
    catalog = load_antenna_templates()
    return AntennaTemplatesResponse(
        default=catalog.get("default", ""),
        templates=[
            AntennaTemplateOption(
                name=name,
                description=t.get("description"),
                tilt_range=t.get("tilt_range"),
                default_tilt=t.get("gdl_defaults", {}).get(
                    "Property: Logical Antenna: Electrical Tilt (deg)"
                ),
            )
            for name, t in catalog.get("templates", {}).items()
        ],
    )


@router.get("/population-raster-status", response_model=PopulationRasterStatusResponse)
async def population_raster_status(request: Request):
    """Check if a population raster is available for the project."""
    project_name = request.headers.get("x-project-name", "")
    return PopulationRasterStatusResponse(**get_population_status(project_name))


@router.get("/tilt-mapping", response_model=TiltMappingResponse)
async def get_tilt_mapping_status():
    """Return the current tilt-to-beam-pattern mapping status."""
    mapping = load_tilt_mapping()
    bands = dump_mapping()
    return TiltMappingResponse(
        available=bool(mapping),
        entry_count=sum(len(v) for v in mapping.values()),
        bands=bands,
        path=get_tilt_mapping_path() if mapping else None,
    )


@router.post("/tilt-mapping", response_model=TiltMappingUploadResponse)
async def upload_tilt_mapping(
    file: UploadFile = File(..., description="CSV file with band_code,tilt_deg,beam_pattern_name columns"),
):
    """Upload a tilt-to-beam-pattern mapping CSV."""
    path = get_tilt_mapping_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    mapping = reload_tilt_mapping()
    bands_count = {band: len(tilts) for band, tilts in mapping.items()}
    return TiltMappingUploadResponse(
        accepted=True,
        entry_count=sum(bands_count.values()),
        bands=bands_count,
    )


@router.delete("/tilt-mapping", response_model=TiltMappingDeleteResponse)
async def delete_tilt_mapping():
    """Remove the operator-uploaded tilt mapping CSV."""
    path = get_tilt_mapping_path()
    if os.path.exists(path):
        os.remove(path)
    reload_tilt_mapping()
    return TiltMappingDeleteResponse(deleted=True)


@router.get("/tilt-mapping/sample")
async def get_tilt_mapping_sample():
    """Download the reference tilt-mapping sample CSV."""
    path = get_tilt_mapping_sample_path()
    if not os.path.exists(path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Sample tilt mapping file not found")
    return FileResponse(
        path,
        media_type="text/csv",
        filename="tilt_mapping_sample.csv",
    )


@router.post("/{acss_session_id}/autogen-config", response_model=AutoGenConfigResponse)
async def post_autogen_config(
    acss_session_id: UUID,
    config: AutoGenConfigRequest,
    db: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client),
):
    """Save the user's auto-gen settings into setup_state."""
    session = await save_autogen_config(db, acss_session_id, config, redis_client)
    return AutoGenConfigResponse(
        session_id=session.id,
        load_candidate_gdl=session.setup_state.get("loadCandidateGdl", {}),
    )


@router.delete("/{acss_session_id}/candidate/{site_iid}", response_model=CandidateDeleteResponse)
async def delete_autogen_candidate(
    acss_session_id: UUID,
    site_iid: str,
    db: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client),
):
    """Delete one auto-generated candidate site after user review."""
    result = await delete_candidate(db, acss_session_id, site_iid, redis_client)
    return CandidateDeleteResponse(**result)
