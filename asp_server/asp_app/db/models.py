import uuid
import enum
from sqlalchemy import Column, String, Text, Enum, ForeignKey, DateTime, ARRAY, Float, Boolean, Integer, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()



class SessionStatus(str, enum.Enum):
    """Enum for session status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, enum.Enum):
    """Enum for step status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepName(str, enum.Enum):
    """Enum for step names."""
    INIT = "init"
    EXTRACT_COORDS = "extract_coords"
    VALIDATE = "validate"
    PROCESS = "process"
    GENERATE_REPORT = "generate_report"
    FINALIZE = "finalize"
    
    # New execution steps
    BASELINE_COVERAGE = "baseline_coverage"
    CREATING_CANDIDATES = "creating_candidates"
    RUNNING_COVERAGE_FOR_CANDIDATES = "runing_coverage_for_candidates"
    CALCULATE_COMBINATIONS = "calculate_combinations"
    CALCULATION = "calculation"
    FINAL_EVALUATION = "final_evaluation"
    UPDATE_ACTUAL_CANDIDATES = "update_actual_candidates"
    RUNNING_COVERAGE_FOR_BASELINE_AND_CANDIDATES = "running_coverage_for_baseline_and_candidates"
    CONVERTING_BILS_FOR_INTERACTIVE_VIEW = "converting_bils_for_interactive_view"


class ACSSSession(Base):
    __tablename__ = "acss_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    project_name = Column(Text, nullable=False, index=True)
    user_id = Column(Text, nullable=False, index=True)
    project_cords = Column(ARRAY(Float, dimensions=2), nullable=True)
    status = Column(Enum(SessionStatus), nullable=False, default=SessionStatus.PENDING)
    current_step_id = Column(UUID(as_uuid=True), ForeignKey("acss_steps.id"), nullable=True)
    setup_state = Column(JSONB, nullable=True, default=dict)  
    execution_status_state = Column(JSONB, nullable=True, default=dict)
    job_id = Column(String, nullable=True) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())



    # Relationship to steps
    steps = relationship("ACSSStep", back_populates="session", foreign_keys="ACSSStep.session_id", cascade="all, delete-orphan",
        overlaps="current_step")
    current_step = relationship("ACSSStep", foreign_keys=current_step_id, overlaps="steps", uselist=False)
    candidate_evaluations = relationship("ACSSCandidateEvaluation", back_populates="session", cascade="all, delete-orphan")
    candidate_coverage_runs = relationship("ACSSCandidateCoverageRun", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ACSSSession(id={self.id}, project_name='{self.project_name}', status={self.status}, current_step_id={self.current_step_id})>"


class ACSSStep(Base):
    __tablename__ = "acss_steps"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("acss_sessions.id"), nullable=False, index=True)
    step_name = Column(Enum(StepName, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    status = Column(Enum(StepStatus), nullable=False, default=StepStatus.PENDING)
    step_metadata = Column(JSONB, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to session
    session = relationship("ACSSSession", back_populates="steps", foreign_keys=[session_id],
        overlaps="current_step")
    
    def __repr__(self):
        return f"<ACSSStep(id={self.id}, step_name={self.step_name}, status={self.status}, session_id={self.session_id})>"


class ACSSCandidateCoverageRun(Base):
    __tablename__ = "acss_candidate_coverage_run"
    __table_args__ = (PrimaryKeyConstraint("session_id", "site_iid"),)

    session_id = Column(UUID(as_uuid=True), ForeignKey("acss_sessions.id"), nullable=False, index=True)
    site_iid = Column(Text, nullable=False, index=True)
    cell_iids = Column(ARRAY(String), nullable=False)
    cov_status = Column(Boolean, default=False, nullable=False)
    cov_path = Column(Text, nullable=True)

    session = relationship("ACSSSession", back_populates="candidate_coverage_runs")





class ACSSCandidateEvaluation(Base):
    __tablename__ = "acss_candidate_evaluation"
    __table_args__ = (PrimaryKeyConstraint("session_id", "candidate_name"),)

    session_id = Column(UUID(as_uuid=True), ForeignKey("acss_sessions.id"), nullable=False, index=True)
    candidate_name = Column(Text, nullable=False)  # "|" separated site iids
    status = Column(Boolean, default=False, nullable=False)
    goal_value = Column(Float, nullable=True)
    result_details = Column(JSONB, nullable=True, default=dict)

    session = relationship("ACSSSession", back_populates="candidate_evaluations")


