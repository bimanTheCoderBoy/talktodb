from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.openapi.models import ParameterInType
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_db_session, get_user_db_session
from api.schemas.user_config import UserProjectConfigCreate, UserProjectConfigResponse, CellsInPolygonRequest
from api.services.user_config_service import UserConfigService
from fastapi import Request

router = APIRouter(
    prefix="/api/v1",
    tags=["User Project Config"],
)


@router.get("/user-project-config", response_model=UserProjectConfigResponse)
async def get_user_project_config(
    request: Request,
    project_name: str = Query(..., description="Project name"),
    email: str = Query(None, description="Lookup email (admin override). Falls back to auth token email."),
    db: AsyncSession = Depends(get_user_db_session),
):
    """
    Retrieve a saved user project configuration.

    Uses the composite key (email + project_name) to look up.
    If ``email`` query param is provided it is used directly (admin use),
    otherwise the authenticated user's email from the token is used.
    Returns 404 if no saved configuration exists.
    """
    isAdmin = "CONFIG_MANAGEMENT" in request.state.user.get("roles", [])
    print(request.state.user)
    if not isAdmin and email:
        raise HTTPException(status_code=401, detail="You are not authorized to access this resource")
    if not email:
        email = request.state.user.get("email", False)
    if not email:
        raise HTTPException(status_code=401, detail="Unauthorized")
    row = await UserConfigService.get(db=db, email=email, project_name=project_name)
    if row is None:
        raise HTTPException(status_code=404, detail="No saved project config found")
    return row


@router.post("/user-project-config", response_model=UserProjectConfigResponse)
async def create_or_update_user_project_config(
    request: Request,
    body: UserProjectConfigCreate,
    db: AsyncSession = Depends(get_user_db_session),
):
    """
    Create or update a user project configuration.

    Uses the composite key (email + project_name) to upsert.
    Stored in the fixed "user" database (no ``x-project-name`` header needed).

    **Body**:
    - ``project_name``: project name (required)
    - ``cords``: list of [lon, lat] coordinate pairs (optional)
    - ``cell_ids``: list of cell ID strings (optional)
    """
    isAdmin = "CONFIG_MANAGEMENT" in request.state.user.get("roles", [])
    if not isAdmin and body.email:
        raise HTTPException(status_code=401, detail="You are not authorized to update this resource")


    if not body.email:
        body.email = request.state.user.get("email", False)
    if not body.email:
        raise HTTPException(status_code=401, detail="Unauthorized")
    row = await UserConfigService.upsert(db=db, data=body)
    return row


@router.post("/user-project-config/cells-in-polygon", response_model=List[str])
async def get_cells_in_polygon(
    request: Request,
    body: CellsInPolygonRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get the cells in the polygon.
    """
    email = request.state.user.get("email", False)
    if not email:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await UserConfigService.get_cells_in_polygon(cords=body.cords, db=db)
    