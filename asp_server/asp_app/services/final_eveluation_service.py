from fastapi import HTTPException
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from asp_app.services.redis_service import RedisService
from asp_app.db.schemas.execution import ExecutionStepName, ExecutionStatus
from asp_app.services.run_coverage_service import RunCoverageService
from asp_app.db.models import ACSSSession, ACSSStep, StepStatus, ACSSCandidateEvaluation
from sqlalchemy.orm.attributes import flag_modified
from uuid import UUID


class FinalEvaluationService:
    """Final evaluation: same goal as execution_service — max goal_value and all tied candidates, using a scalar subquery."""

    @staticmethod
    async def run(
        db: AsyncSession,
        session: ACSSSession,
        step: ACSSStep,
        session_id: UUID,
        job_id: str,
        redis_client: Redis,
    ):
        step.status = StepStatus.IN_PROGRESS
        flag_modified(step, "status")
        await db.commit()

        await RunCoverageService._update_execution_state(
            db, session, ExecutionStepName.FINAL_EVALUATION, ExecutionStatus.RUNNING, 0, job_id, redis_client
        )

        try:
            # 1) Load ALL evaluated candidates (sorted best-first) — stored once, served by GET /review with zero extra queries
            all_eval_result = await db.execute(
                select(ACSSCandidateEvaluation)
                .where(
                    ACSSCandidateEvaluation.session_id == session_id,
                    ACSSCandidateEvaluation.status.is_(True),
                    ACSSCandidateEvaluation.goal_value.isnot(None),
                )
                .order_by(ACSSCandidateEvaluation.goal_value.desc())
            )
            all_eval_rows = list(all_eval_result.scalars().all())

            if not all_eval_rows:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", "No evaluated candidates found")
                raise HTTPException(status_code=400, detail="No evaluated candidates found for final evaluation")

            # 2) Determine max goal_value and which candidates are tied at that value
            max_goal_value = all_eval_rows[0].goal_value
            tied_names = {row.candidate_name for row in all_eval_rows if row.goal_value == max_goal_value}
            #Chandan Sir Change 
            total_evaluated = len(all_eval_rows)
            all_candidates = [
                {
                    "candidate_name": row.candidate_name,
                    "goal_value": row.goal_value,
                    "result_details": row.result_details or {},
                    "is_tied": row.candidate_name in tied_names,
                }
                for row in all_eval_rows
            ]
            tied_candidates = [c for c in all_candidates if c["is_tied"]]

            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"Final evaluation: max_goal_value={max_goal_value}, tied={len(tied_candidates)}, total_evaluated={len(all_candidates)}"
            )

            # Persist review data into step_metadata (include selection like execution_service)
            review_data = {
                "max_goal_value": max_goal_value,
                "tied_candidates": tied_candidates,
                "all_candidates": all_candidates,
                "total_evaluated": total_evaluated, 
                "selection": {
                    "status": "pending",
                    "selected_candidate_names": None,
                    "confirmed_at": None,
                },
            }
            step.step_metadata = review_data
            step.status = StepStatus.COMPLETED
            flag_modified(step, "step_metadata")
            flag_modified(step, "status")
            await db.commit()

            # Set finalEvaluation to WAITING_USER and exit the worker successfully
            await RunCoverageService._update_execution_state(
                db, session, ExecutionStepName.FINAL_EVALUATION,
                ExecutionStatus.WAITING_USER, 100, job_id, redis_client, end_time=True
            )
            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                "Final evaluation complete. Waiting for user to select a candidate."
            )
            return step

        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            error_msg = str(e)
            step.status = StepStatus.FAILED
            step.step_metadata = (step.step_metadata or {}) | {"error_message": error_msg}
            flag_modified(step, "status")
            flag_modified(step, "step_metadata")
            await db.commit()
            await RunCoverageService._update_execution_state(
                db, session, ExecutionStepName.FINAL_EVALUATION, ExecutionStatus.ERROR, 99, job_id, redis_client, end_time=True
            )
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Final evaluation error: {error_msg}")
            raise HTTPException(status_code=400, detail=f"Final evaluation failed: {error_msg}") from e