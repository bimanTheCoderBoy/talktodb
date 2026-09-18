import asyncio
from uuid import UUID
import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.pool import NullPool

from asp_app.celery_app import celery_app
from asp_app.config.acss_config import get_redis_config, get_database_config
from asp_app.db.models import ACSSSession, ACSSStep, StepName, StepStatus
from asp_app.db.schemas.execution import ExecutionStatus
from asp_app.services.execution_service import ExecutionService
from asp_app.services.redis_service import RedisService

# Map execution_status_state keys (camelCase) to DB StepName enum
_EXECUTION_KEY_TO_STEP_NAME = {
    "baselineCoverage": StepName.BASELINE_COVERAGE,
    "creatingCandidates": StepName.CREATING_CANDIDATES,
    "runingCoverageForCandidates": StepName.RUNNING_COVERAGE_FOR_CANDIDATES,
    "calculateCombinations": StepName.CALCULATE_COMBINATIONS,
    "calculation": StepName.CALCULATION,
    "finalEvaluation": StepName.FINAL_EVALUATION,
    "updateActualCandidates": StepName.UPDATE_ACTUAL_CANDIDATES,
    "runningCoverageForBaselineAndCandidates": StepName.RUNNING_COVERAGE_FOR_BASELINE_AND_CANDIDATES,
    "convertingBilsForInteractiveView": StepName.CONVERTING_BILS_FOR_INTERACTIVE_VIEW,
}


@celery_app.task(name="acss_service", bind=True)
def run_execution_task(self, session_id: str, project_name: str):
    """
    Celery task that calls the ExecutionService.
    Creates fresh Redis and DB connections for each task to avoid event loop issues.
    """
    job_id = self.request.id
    redis_url = get_redis_config().redis_url
    db_config = get_database_config()
    db_url = db_config.get_database_url(project_name.lower())
    
    async def execute():
        # create a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Create fresh connections for this event loop
        redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # Use NullPool to avoid connection pooling issues across event loops
        engine = create_async_engine(db_url, poolclass=NullPool)
        sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        
        try:
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Execution worker allocated")
            
            async with sessionmaker() as db:
                result = await ExecutionService.run_execution(
                    db, UUID(session_id), redis_client, job_id, project_name
                )
                if isinstance(result, dict) and result.get("status") in ("paused", "skipped"):
                    return {
                        "status": result["status"],
                        "session_id": session_id,
                        "job_id": job_id,
                        "message": result.get(
                            "message",
                            "Waiting for user to select a candidate"
                            if result["status"] == "paused"
                            else "Nothing to run for this session",
                        ),
                    }
                return {"status": "success", "session_id": session_id, "job_id": job_id}
        except Exception as e:
            error_msg = getattr(e, "detail", None)
            if error_msg is None:
                error_msg = str(e)
            else:
                error_msg = str(error_msg)
            # Pause-for-user-confirmation is not a failure — exit the worker cleanly
            # so Celery reports SUCCESS instead of FAILURE / red HEALTH.
            if "Work Paused for user confirmation" in error_msg:
                await RedisService.publish_log(
                    redis_client, f"logs:{session_id}",
                    "Execution paused for candidate selection. Waiting for user confirmation."
                )
                return {
                    "status": "paused",
                    "session_id": session_id,
                    "job_id": job_id,
                    "message": "Waiting for user to select a candidate",
                }
            if "Session is already completed" in error_msg or "already finished" in error_msg.lower():
                await RedisService.publish_log(
                    redis_client, f"logs:{session_id}",
                    "Session already completed — nothing to run."
                )
                return {
                    "status": "skipped",
                    "session_id": session_id,
                    "job_id": job_id,
                    "message": "This session has already finished. Start a new session to run again.",
                }
            # Get the running step, set it to error, update execution_status_state, publish, then re-raise
            try:
                async with sessionmaker() as db:
                    await db.rollback()
                    result = await db.execute(
                        select(ACSSSession).where(ACSSSession.id == UUID(session_id))
                    )
                    session = result.scalar_one_or_none()
                    if session and session.execution_status_state:
                        state = dict(session.execution_status_state)
                        running_step_key = None
                        for step_key, step_data in state.items():
                            if isinstance(step_data, dict) and step_data.get("status") == ExecutionStatus.RUNNING.value:
                                state[step_key] = {**step_data, "status": ExecutionStatus.ERROR.value}
                                running_step_key = step_key
                                break
                        session.execution_status_state = state
                        flag_modified(session, "execution_status_state")
                        # Mark the corresponding ACSSStep row as failed
                        if running_step_key:
                            step_name = _EXECUTION_KEY_TO_STEP_NAME.get(running_step_key)
                            if step_name is not None:
                                step_result = await db.execute(
                                    select(ACSSStep).where(
                                        ACSSStep.session_id == UUID(session_id),
                                        ACSSStep.step_name == step_name,
                                    )
                                )
                                acss_step = step_result.scalar_one_or_none()
                                if acss_step:
                                    acss_step.status = StepStatus.FAILED
                        await db.commit()
                        await RedisService.publish_execution_state(redis_client, job_id, session.execution_status_state)
            except Exception:
                pass
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Execution failed: {error_msg}")
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Execution state set to error for running step.")
            # Re-raise a plain Exception so Celery HEALTH shows the message,
            # not an HTTPException(status_code=..., detail=...) dump.
            raise Exception(error_msg) from e
        finally:
            await redis_client.aclose()
            await engine.dispose()
    
    return asyncio.run(execute())
