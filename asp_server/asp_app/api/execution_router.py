from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from redis import Redis

from typing import List

from asp_app.services.session_service import SessionService
from asp_app.services.redis_service import RedisService
from asp_app.services.run_coverage_service import RunCoverageService
from asp_app.db.schemas.execution import RunExecutionResponse, ExecutionStepName, ExecutionStatus
from asp_app.db.models import ACSSSession, ACSSStep, StepName, SessionStatus
from asp_app.db.database import get_db_session
from asp_app.db.redis import get_redis_client
from asp_app.tasks.execution_tasks import run_execution_task
from asp_app.celery_app import celery_app

router = APIRouter(
    prefix="/execution",
    tags=["Execution"]
)

@router.post("/{acss_session_id}/run", response_model=RunExecutionResponse)
async def run_execution(
    acss_session_id: UUID,
    x_project_name: str = Header(..., description="Project name for database connection"),
    db: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    Start the 5-step execution process using Celery.
    SSE streaming: GET /api/v1/redis/execution/{job_id}
    Health check: GET /api/v1/execution/{job_id}/health

    If the session was cancelled at candidate selection, reopens the review
    modal instead of starting a failing Celery job.
    If the session already finished successfully, returns a graceful rejection
    (no Celery task) so HEALTH does not show FAILURE.
    """
    session_result = await db.execute(
        select(ACSSSession).where(ACSSSession.id == acss_session_id)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    fe_status = (session.execution_status_state or {}).get("finalEvaluation", {}).get("status")

    # User cancelled candidate selection — reopen review instead of failing
    if (
        session.status in (SessionStatus.COMPLETED, SessionStatus.CANCELLED)
        and fe_status == ExecutionStatus.CANCELLED.value
    ):
        step_result = await db.execute(
            select(ACSSStep).where(
                ACSSStep.step_name == StepName.FINAL_EVALUATION,
                ACSSStep.session_id == acss_session_id,
            )
        )
        fe_step = step_result.scalar_one_or_none()
        has_candidates = bool(
            fe_step
            and fe_step.step_metadata
            and fe_step.step_metadata.get("all_candidates")
        )
        if has_candidates:
            session.status = SessionStatus.IN_PROGRESS
            flag_modified(session, "status")
            job_id = session.job_id or ""
            await RunCoverageService._update_execution_state(
                db, session, ExecutionStepName.FINAL_EVALUATION,
                ExecutionStatus.WAITING_USER, 100, job_id, redis_client,
                end_time=True,
            )
            await RedisService.publish_log(
                redis_client, f"logs:{acss_session_id}",
                "Candidate selection reopened. Please select a candidate to continue."
            )
            return RunExecutionResponse(
                message="Candidate selection was cancelled earlier. Please select a candidate to continue.",
                session_id=acss_session_id,
                job_id=job_id or None,
                status="needs_review",
            )

    if session.status == SessionStatus.COMPLETED:
        await RedisService.publish_log(
            redis_client, f"logs:{acss_session_id}",
            "Cannot start execution — this session has already finished."
        )
        return RunExecutionResponse(
            message="This session has already finished. Start a new session to run again.",
            session_id=acss_session_id,
            job_id=None,
            status="rejected",
        )

    if session.status == SessionStatus.CANCELLED:
        await RedisService.publish_log(
            redis_client, f"logs:{acss_session_id}",
            "Cannot start execution — this session was cancelled."
        )
        return RunExecutionResponse(
            message="This session was cancelled. Start a new session to run again.",
            session_id=acss_session_id,
            job_id=None,
            status="rejected",
        )

    task = run_execution_task.delay(str(acss_session_id), x_project_name)
    result = await SessionService.update_session_job_id(db, acss_session_id, task.id, redis_client)
    return RunExecutionResponse(
        message=result.get("message", "Execution started"),
        session_id=acss_session_id,
        job_id=task.id,
        status="started",
    )


def _celery_failure_message(result) -> str:
    """Extract a user-friendly message from a Celery FAILURE result."""
    exc = result.result
    detail = getattr(exc, "detail", None)
    if detail is not None:
        return str(detail)
    text = str(exc) if exc is not None else "Unknown error"
    # Strip FastAPI HTTPException repr: HTTPException(status_code=400, detail='...')
    if "detail=" in text:
        for quote in ("'", '"'):
            marker = f"detail={quote}"
            if marker in text:
                start = text.index(marker) + len(marker)
                end = text.rfind(quote)
                if end > start:
                    return text[start:end]
    return text


@router.get("/{job_id}/health")
async def get_job_health(job_id: str):
    """Get Celery task health status."""
    try:
        result = celery_app.AsyncResult(job_id)
        payload = {
            "task_id": job_id,
            "status": result.status,
            "error": _celery_failure_message(result) if result.status == "FAILURE" else None,
        }
        # Surface pause / skipped result so the UI can show a graceful message
        if result.status == "SUCCESS" and isinstance(result.result, dict):
            status = result.result.get("status")
            if status == "paused":
                payload["message"] = result.result.get(
                    "message", "Waiting for user to select a candidate"
                )
                payload["paused"] = True
            elif status == "skipped":
                payload["message"] = result.result.get(
                    "message", "Nothing to run for this session"
                )
                payload["skipped"] = True
        return payload
    except Exception as e:
        return {"task_id": job_id, "status": "UNKNOWN", "error": str(e)}


# ============ REVIEW APIs (pause / resume) ============

@router.get("/{acss_session_id}/review")
async def get_review(
    acss_session_id: UUID,
    x_project_name: str = Header(..., description="Project name for database connection"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Returns the final-evaluation review data pre-computed by FinalEvaluationService.
    All candidates, tied flags, and stats are stored in step_metadata — no extra DB queries.
    Frontend calls this when it detects finalEvaluation.status === 'waiting_user'.
    """
    step_result = await db.execute(
        select(ACSSStep).where(
            ACSSStep.step_name == StepName.FINAL_EVALUATION,
            ACSSStep.session_id == acss_session_id,
        )
    )
    step = step_result.scalar_one_or_none()
    if not step or not step.step_metadata:
        raise HTTPException(status_code=404, detail="Final evaluation review data not found")

    meta = step.step_metadata
    return {
        "session_id": str(acss_session_id),
        "max_goal_value": meta.get("max_goal_value"),
        "tied_candidates": meta.get("tied_candidates", []),
        "all_candidates": meta.get("all_candidates", []),
        "total_evaluated": meta.get("total_evaluated", 0),
        "selection": meta.get("selection", {}),
    }


class ConfirmReviewRequest(BaseModel):
    selected_candidate_names: List[str] = Field(..., description="List of candidate_name values the user chose")


@router.post("/{acss_session_id}/review/confirm")
async def confirm_review(
    acss_session_id: UUID,
    body: ConfirmReviewRequest,
    x_project_name: str = Header(..., description="Project name for database connection"),
    db: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Confirm the user's candidate selection (one or more candidates).
    Saves the choices into FINAL_EVALUATION step_metadata and sets
    finalEvaluation execution-status to DONE so the next /run call
    proceeds to updateActualCandidates.
    """
    if not body.selected_candidate_names:
        raise HTTPException(status_code=400, detail="At least one candidate must be selected")

    step_result = await db.execute(
        select(ACSSStep).where(
            ACSSStep.step_name == StepName.FINAL_EVALUATION,
            ACSSStep.session_id == acss_session_id,
        )
    )
    step = step_result.scalar_one_or_none()
    if not step or not step.step_metadata:
        raise HTTPException(status_code=404, detail="Final evaluation review data not found")

    # Validate against pre-stored all_candidates in step_metadata (no extra DB query)
    valid_names = {
        c["candidate_name"]
        for c in step.step_metadata.get("all_candidates", [])
    }
    invalid = [n for n in body.selected_candidate_names if n not in valid_names]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Selected candidate(s) not found among evaluated candidates: {invalid}"
        )

    # Update selection in step_metadata
    step.step_metadata["selection"] = {
        "status": "confirmed",
        "selected_candidate_names": body.selected_candidate_names,
        # Keep backward-compat key (first selected, used by downstream if list not found)
        "selected_candidate_name": body.selected_candidate_names[0],
        "confirmed_at": datetime.utcnow().isoformat(),
    }
    flag_modified(step, "step_metadata")
    await db.commit()

    # Update execution_status_state: finalEvaluation -> DONE
    session_result = await db.execute(
        select(ACSSSession).where(ACSSSession.id == acss_session_id)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    job_id = session.job_id or ""
    await RunCoverageService._update_execution_state(
        db, session, ExecutionStepName.FINAL_EVALUATION,
        ExecutionStatus.DONE, 100, job_id, redis_client
    )

    return {
        "session_id": str(acss_session_id),
        "message": "Candidate selection confirmed",
        "selection": step.step_metadata["selection"],
    }


@router.post("/{acss_session_id}/review/close")
async def close_review(
    acss_session_id: UUID,
    x_project_name: str = Header(..., description="Project name for database connection"),
    db: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Close the review without selecting any candidate (user cancelled).
    Sets session status to CANCELLED and finalEvaluation to CANCELLED.
    """
    session_result = await db.execute(
        select(ACSSSession).where(ACSSSession.id == acss_session_id)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update session status to CANCELLED (user abandoned candidate selection)
    session.status = SessionStatus.CANCELLED
    flag_modified(session, "status")

    # Update execution_status_state: finalEvaluation -> CANCELLED
    job_id = session.job_id or ""
    await RunCoverageService._update_execution_state(
        db, session, ExecutionStepName.FINAL_EVALUATION,
        ExecutionStatus.CANCELLED, 100, job_id, redis_client,
        end_time=True
    )

    await RedisService.publish_log(
        redis_client, f"logs:{acss_session_id}",
        "Candidate selection cancelled by user. Session marked as cancelled."
    )

    return {
        "session_id": str(acss_session_id),
        "message": "Candidate selection cancelled by user",
        "status": "cancelled",
        "execution_status_state": session.execution_status_state,
    }
