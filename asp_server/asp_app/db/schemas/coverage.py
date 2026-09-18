from uuid import UUID
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from asp_app.db.models import ACSSSession, ACSSStep, SessionStatus, StepName, StepStatus
from asp_app.config.acss_config import CoverageAPIConfig

class CoverageUrlParameters(BaseModel):
    technology: str = Field(..., description="Technology")
    resolution: str = Field(..., description="Resolution")
    mode: str = Field(..., description="Mode")
    terminal: str = Field(..., description="Terminal")
    auto_approve: bool = Field(..., description="Auto approve")
    height: Optional[str] = Field(default=None, description="Height")
    carrier: Optional[str] = Field(default=None, description="Carrier")

class RunCoverageRequest(BaseModel):
    # session: ACSSSession = Field(..., description="ACSS session")
    # step: ACSSStep = Field(..., description="ACSS step")
    project_name: str = Field(..., description="Name of the project")
    job_id: str = Field(..., description="ID of the Celery job")
    url_params: CoverageUrlParameters = Field(..., description="URL parameters")
    array_types: List[str] = Field(..., description="Array types")
    cells: List[str] = Field(..., description="Cells")
    boundary_coords: List[List[float]] = Field(..., description="Boundary coordinates")
    baseconfig: CoverageAPIConfig = Field(..., description="Coverage API configuration")
    output_location: str = Field(..., description="Output location")
    output_name: str = Field(..., description="Output name")
