from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_db_session
from api.schemas.cells import SitesCellsRequest, SitesCellsResponse
from api.services.cells_service import CellsService
from api.db.database import get_user_db_session

router = APIRouter(
    prefix="/api",
    tags=["Sites & Cells"],
)


@router.post("/sites-cells", response_model=SitesCellsResponse)
async def get_sites_cells(
    request: Request,    
    body: SitesCellsRequest,
    db: AsyncSession = Depends(get_db_session),
    user_db: AsyncSession = Depends(get_user_db_session),
):
    """
    Retrieve sites and cells within a boundary polygon.

    The project database is selected via the ``x-project-name`` header.

    **Body**:
    - ``cords``: boundary polygon as ``[[lon, lat], ...]`` (required, min 3 points)
    - ``state``, ``address1``, ``town``: optional text filters (case-insensitive partial match)

    Returns sites with their associated cells filtered by the polygon.
    """
    email = request.state.user.get("email", False) 
    return await CellsService.get_sites_cells(
        db=db,
        user_db=user_db,
        x_project_name=request.headers.get("x-project-name"),
        cords=body.cords,
        auth_scope=body.auth_scope,
        email=email,
    )
