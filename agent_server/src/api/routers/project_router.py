from fastapi import APIRouter, HTTPException, Query, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from api.db.database import get_db_session
from api.schemas.project import ProjectCordsResponse
from api.services.project_service import ProjectService

router = APIRouter(
    prefix="/api/v1",
    tags=["Project"],
)


@router.get("/project-cords", response_model=ProjectCordsResponse)
async def get_project_cords(
    x_project_name: str = Header(..., description="Project name (maps to KML folder)"),
):
    """
    Return the outer bounding-box polygon for a project's KML files.

    **Query params**:
    - ``project_name``: name of the project whose KML folder will be read

    Returns ``{"project_name": "...", "cords": [[lon, lat], ...]}``.
    """
    try:
        cords = await ProjectService.get_outer_polygon_from_kml(x_project_name)
        return ProjectCordsResponse(project_name=x_project_name, cords=cords)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get project coordinates: {str(e)}",
        )

