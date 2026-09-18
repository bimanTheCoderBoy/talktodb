from uuid import UUID
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ACSSSessionCreate(BaseModel):
    acss_session_id: UUID = Field(..., description="ID of the ACSS session")
    project_name: str = Field(..., min_length=1, description="Name of the project")
    user_id: str = Field(None, description="ID of the user")


class ACSSSessionResponse(BaseModel):
    id: UUID
    project_name: str
    project_cords: Optional[List[List[float]]]
    status: SessionStatus
    current_step_id: Optional[UUID]
    setup_state: Optional[Dict[str, Any]] = None
    execution_status_state: Optional[Dict[str, Any]] = None
    job_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
