from uuid import UUID
from typing import Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime
import enum


class RunExecutionResponse(BaseModel):
    message: str
    session_id: UUID = Field(..., description="ID of the ACSS session")
    job_id: Optional[str] = Field(None, description="ID of the Celery job (absent when run was not started)")
    status: str = Field(
        "started",
        description="started | rejected | needs_review",
    )

    class Config:
        from_attributes = True


class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    WAITING_USER = "waiting_user"
    CANCELLED = "cancelled"


class ExecutionStepName(str, enum.Enum):
    BASELINE_COVERAGE = "baselineCoverage"
    AUTO_GEN_CANDIDATES = "autoGenCandidates"
    CREATING_CANDIDATES = "creatingCandidates"
    RUNNING_COVERAGE_FOR_CANDIDATES = "runingCoverageForCandidates"
    CALCULATE_COMBINATIONS = "calculateCombinations"
    CALCULATION = "calculation"
    FINAL_EVALUATION = "finalEvaluation"
    UPDATE_ACTUAL_CANDIDATES = "updateActualCandidates"
    RUNNING_COVERAGE_FOR_BASELINE_AND_CANDIDATES = "runningCoverageForBaselineAndCandidates"
    CONVERTING_BILS_FOR_INTERACTIVE_VIEW = "convertingBilsForInteractiveView"


class ExecutionStepState(BaseModel):
    """State for a single execution step."""
    status: ExecutionStatus = ExecutionStatus.PENDING
    progress: int = 0
    startTime: Optional[datetime] = None  
    endTime: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExecutionStatusState(BaseModel):
    """Complete execution status state matching frontend structure."""
    baselineCoverage: ExecutionStepState = Field(default_factory=ExecutionStepState)
    autoGenCandidates: ExecutionStepState = Field(default_factory=ExecutionStepState)
    creatingCandidates: ExecutionStepState = Field(default_factory=ExecutionStepState)
    runingCoverageForCandidates: ExecutionStepState = Field(default_factory=ExecutionStepState)
    calculateCombinations: ExecutionStepState = Field(default_factory=ExecutionStepState)
    calculation: ExecutionStepState = Field(default_factory=ExecutionStepState)
    finalEvaluation: ExecutionStepState = Field(default_factory=ExecutionStepState)
    updateActualCandidates: ExecutionStepState = Field(default_factory=ExecutionStepState)
    runningCoverageForBaselineAndCandidates: ExecutionStepState = Field(default_factory=ExecutionStepState)
    convertingBilsForInteractiveView: ExecutionStepState = Field(default_factory=ExecutionStepState)

    class Config:
        from_attributes = True