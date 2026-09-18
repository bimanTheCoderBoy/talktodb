"""Service to compute C(n,k) combinations from site iids and persist them to candidate_evaluation."""

import math
from itertools import combinations
from typing import List
from uuid import UUID

from fastapi import HTTPException
from redis import Redis
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from asp_app.db.models import ACSSSession, ACSSStep, ACSSCandidateEvaluation, StepStatus
from asp_app.db.schemas.execution import ExecutionStepName, ExecutionStatus
from asp_app.services.redis_service import RedisService
from asp_app.services.run_coverage_service import RunCoverageService


class CalculateCombinationsService:
    """Computes all k-combinations of site iids and inserts rows into candidate_evaluation."""
    
    @staticmethod
    async def run(
        db: AsyncSession,
        session: ACSSSession,
        step: ACSSStep,
        session_id: UUID,
        k_value: int,
        site_iids: List[str],
        redis_client: Redis,
        job_id: str,
        execution_state_key: ExecutionStepName = ExecutionStepName.CALCULATE_COMBINATIONS,
    ) -> ACSSStep:
        """
        Get k and site_iids, compute C(n,k), generate all combinations, and insert into candidate_evaluation.
        Updates step status and execution_status_state (via RunCoverageService._update_execution_state).
        """
        n = len(site_iids)
        step.status = StepStatus.IN_PROGRESS
        flag_modified(step, "status")
        await db.commit()

        await RunCoverageService._update_execution_state(
            db, session, execution_state_key, ExecutionStatus.RUNNING, 0, job_id, redis_client
        )

        try:
            total = math.comb(n, k_value)
            await RedisService.publish_log(redis_client,
                f"logs:{session_id}",
                f"Calculate combinations: C({n},{k_value}) = {total} combinations",
            )

            await RunCoverageService._update_execution_state(
                db, session, execution_state_key, ExecutionStatus.RUNNING, 20, job_id, redis_client
            )
            #delete any existing candidate combinations
            await db.execute(delete(ACSSCandidateEvaluation).where(ACSSCandidateEvaluation.session_id == session_id))
            await db.commit()

            rows = []
            for combo in combinations(site_iids, k_value):
                candidate_name = "|".join(sorted(combo))
                rows.append(
                    ACSSCandidateEvaluation(
                        session_id=session_id,
                        candidate_name=candidate_name,
                        status=False,
                        goal_value=None,
                    )
                )

            if rows:
                db.add_all(rows)
            await db.commit()

            step.status = StepStatus.COMPLETED
            step.step_metadata = step.step_metadata or {}
            step.step_metadata["total_combinations"] = total
            step.step_metadata["k"] = k_value
            step.step_metadata["n_sites"] = n
            flag_modified(step, "status")
            flag_modified(step, "step_metadata")
            await db.commit()

            await RunCoverageService._update_execution_state(
                db, session, execution_state_key, ExecutionStatus.DONE, 100, job_id, redis_client, end_time=True
            )
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Inserted {total} candidate combinations into candidate_evaluation")
            return step

        except HTTPException:
            raise
        except Exception as e:
            error_msg = str(e)
            step.status = StepStatus.FAILED
            step.step_metadata = (step.step_metadata or {}) | {"error_message": error_msg}
            flag_modified(step, "status")
            flag_modified(step, "step_metadata")
            await db.commit()
            await RunCoverageService._update_execution_state(
                db, session, execution_state_key, ExecutionStatus.ERROR, 99, job_id, redis_client, end_time=True
            )
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Calculate combinations error: {error_msg}")
            raise HTTPException(status_code=400, detail=f"Calculate combinations failed: {error_msg}")
