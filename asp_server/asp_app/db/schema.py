# from pydantic import BaseModel, Field
# from typing import Optional, List, Any
# from datetime import datetime
# from uuid import UUID
# from enum import Enum


# # Enums matching database enums
# class SessionStatus(str, Enum):
#     """Session status enum."""
#     PENDING = "pending"
#     IN_PROGRESS = "in_progress"
#     COMPLETED = "completed"
#     FAILED = "failed"
#     CANCELLED = "cancelled"


# class StepStatus(str, Enum):
#     """Step status enum."""
#     PENDING = "pending"
#     IN_PROGRESS = "in_progress"
#     COMPLETED = "completed"
#     FAILED = "failed"
#     SKIPPED = "skipped"


# class StepName(str, Enum):
#     """Step name enum."""
#     INIT = "init"
#     EXTRACT_COORDS = "extract_coords"
#     VALIDATE = "validate"
#     PROCESS = "process"
#     GENERATE_REPORT = "generate_report"
#     FINALIZE = "finalize"


# # ============== ACSS Step Schemas ==============

# class ACSSStepBase(BaseModel):
#     """Base schema for ACSS Step."""
#     step_name: StepName
#     status: StepStatus = StepStatus.PENDING
#     metadata: Optional[dict] = Field(default_factory=dict)


# class ACSSStepCreate(ACSSStepBase):
#     """Schema for creating a new step."""
#     session_id: UUID


# class ACSSStepUpdate(BaseModel):
#     """Schema for updating a step."""
#     status: Optional[StepStatus] = None
#     metadata: Optional[dict] = None


# class ACSSStepResponse(ACSSStepBase):
#     """Schema for step response."""
#     id: UUID
#     session_id: UUID
#     created_at: datetime
#     updated_at: Optional[datetime] = None
    
#     class Config:
#         from_attributes = True


# # ============== ACSS Session Schemas ==============

# class ACSSSessionBase(BaseModel):
#     """Base schema for ACSS Session."""
#     project_name: str = Field(..., min_length=1, description="Name of the project")


# # class ACSSSessionCreate(ACSSSessionBase):
# #      acss_session_id: UUID = Field(..., description="ID of the ACSS session")
# #      project_name: str = Field(..., min_length=1, description="Name of the project")
    


# class ACSSSessionUpdate(BaseModel):
#     """Schema for updating a session."""
#     project_name: Optional[str] = Field(None, min_length=1)
#     project_cords: Optional[List[List[float]]] = None
#     status: Optional[SessionStatus] = None
#     current_step: Optional[UUID] = None


# class ACSSSessionResponse(ACSSSessionBase):
#     """Schema for session response."""
#     id: UUID
#     project_cords: Optional[List[List[float]]] = None
#     status: SessionStatus
#     current_step: Optional[UUID] = None
    
#     class Config:
#         from_attributes = True


# class ACSSSessionWithStepsResponse(ACSSSessionResponse):
#     """Schema for session response with steps included."""
#     steps: List[ACSSStepResponse] = []
    
#     class Config:
#         from_attributes = True


# # ============== Project Coordinates Schemas ==============



# class ProjectCoordsRequest(BaseModel):
#     """Request model for getting project coordinates from KML."""
#     folder_path: str = Field(..., description="Path to folder containing KML files (relative to KML root)")
#     method: Optional[str] = Field(
#         default="bounding_box",
#         description="Method for polygon extraction: bounding_box, convex_hull, or concave_hull"
#     )


# class ProjectCoordsResponse(BaseModel):
#     """Response model for project coordinates."""
#     success: bool = Field(..., description="Whether the operation was successful")
#     coordinates: Optional[List[List[float]]] = Field(
#         None, 
#         description="List of [longitude, latitude] coordinate pairs forming the bounding polygon"
#     )
#     folder_path: str = Field(..., description="The folder path that was processed")
#     method: str = Field(..., description="The extraction method used")
#     message: Optional[str] = Field(None, description="Additional message or error details")


# # ============== Generic Response Schemas ==============

# class ErrorResponse(BaseModel):
#     """Standard error response model."""
#     success: bool = False
#     error: str
#     detail: Optional[str] = None


# class SuccessResponse(BaseModel):
#     """Generic success response."""
#     success: bool = True
#     message: str
#     data: Optional[Any] = None
