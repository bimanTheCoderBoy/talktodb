from pydantic import BaseModel, Field
from typing import List


class ProjectCordsResponse(BaseModel):
    """Response for GET /api/v1/project-cords."""
    project_name: str = Field(..., description="Project name that was queried")
    cords: List[List[float]] = Field(
        ...,
        description="Outer polygon coordinates as [[lon, lat], ...]",
    )
