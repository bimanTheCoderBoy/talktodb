from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CellsInPolygonRequest(BaseModel):
    """Request body for POST /api/v1/user-project-config/cells-in-polygon."""
    cords: List[List[float]] = Field(..., description="List of [lon, lat] coordinate pairs forming the polygon ring")


class UserProjectConfigCreate(BaseModel):
    """Request body for POST /api/v1/user-project-config."""
    email: str = Field(None, description="User email")
    project_name: str = Field(..., description="Project name")
    cords: Optional[List[List[float]]] = Field(default_factory=list, description="List of [lon, lat] coordinate pairs")
    cell_iids: Optional[List[str]] = Field(default_factory=list, description="List of cell IDs")


class UserProjectConfigResponse(BaseModel):
    """Response for user_project_config operations."""
    email: str
    project_name: str
    cords: Optional[List[List[float]]] = Field(default_factory=list)
    cell_iids: Optional[List[str]] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
