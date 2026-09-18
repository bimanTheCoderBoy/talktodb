import asyncio
from uuid import UUID
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from fastapi import HTTPException
from redis.asyncio import Redis

from asp_app.config.acss_config import join_paths
from asp_app.db.models import ACSSSession, ACSSStep, ACSSCandidateCoverageRun, StepStatus
from asp_app.db.schemas.coverage import CoverageUrlParameters
from asp_app.db.schemas.execution import ExecutionStepName, ExecutionStatus
from asp_app.services.run_coverage_service import RunCoverageService
from asp_app.services.redis_service import RedisService


def _to_unc_path(path: str) -> str:
    """Convert path to UNC format for coverage API output.location."""
    if not path or not path.strip():
        return path or ""
    normalized = path.strip().replace("\\", "/").strip("/")
    if not normalized:
        return path
    return "\\\\" + normalized.replace("/", "\\")


class CandidateCoverageRunService:
    """Runs coverage for each candidate site in one step; updates acss_candidate_coverage_run and progress."""

    @staticmethod
    async def run(
        db: AsyncSession,
        session: ACSSSession,
        step: ACSSStep,
        session_id: UUID,
        job_id: str,
        redis_client: Redis,
        execution_state_key: ExecutionStepName,
        url_params: CoverageUrlParameters,
        boundary_coords: List[List[float]],
        array_type: str,
        config,
        project_name: str,
        output_base_dir: str,
        output_retrieval_base_dir: str,
    ) -> ACSSStep:
        """
        Load candidate coverage rows with cov_status=False; for each, run coverage,
        update row (cov_status, cov_path) and progress. Fail step on first failure.
        """
        session_id_val = session.id
        await RedisService.publish_log(redis_client, f"logs:{session_id_val}", "Starting coverage run for all candidates...")

        # Load rows where cov_status = False
        result = await db.execute(
            select(ACSSCandidateCoverageRun).where(
                ACSSCandidateCoverageRun.session_id == session_id_val,
                ACSSCandidateCoverageRun.cov_status.is_(False),
            ).order_by(ACSSCandidateCoverageRun.site_iid)
        )
        rows: List[ACSSCandidateCoverageRun] = list(result.scalars().all())

        if not rows:
            await RedisService.publish_log(redis_client, f"logs:{session_id_val}", "No pending candidate coverages; marking step complete.")
            step.status = StepStatus.COMPLETED
            flag_modified(step, "status")
            await db.commit()
            await RunCoverageService._update_execution_state(
                db, session, execution_state_key, ExecutionStatus.DONE, 100, job_id, redis_client, end_time=True
            )
            return step

        total = len(rows)
        runnable_count = sum(1 for r in rows if (r.cell_iids or []))
        if runnable_count == 0:
            await RedisService.publish_log(redis_client, f"logs:{session_id_val}", "No candidate sites with cells; marking step complete.")
            step.status = StepStatus.COMPLETED
            flag_modified(step, "status")
            await db.commit()
            await RunCoverageService._update_execution_state(
                db, session, execution_state_key, ExecutionStatus.DONE, 100, job_id, redis_client, end_time=True
            )
            return step

        step.status = StepStatus.IN_PROGRESS
        flag_modified(step, "status")
        await db.commit()
        await RunCoverageService._update_execution_state(
            db, session, execution_state_key, ExecutionStatus.RUNNING, 0, job_id, redis_client
        )

        try:
            done_count = 0
            array_types = [array_type]

            for row in rows:
                site_iid = row.site_iid
                cells = list(row.cell_iids) if row.cell_iids else []
                if not cells:
                    await RedisService.publish_log(redis_client, f"logs:{session_id_val}", f"Skipping site {site_iid}: no cells")
                    continue

                # Per-candidate coverage folder: output_base_dir/site_iid
                candidate_output_dir =output_base_dir
                output_location_unc = _to_unc_path(candidate_output_dir)
                output_name = site_iid

                await RedisService.publish_log(redis_client, f"logs:{session_id_val}", f"Running coverage for candidate site {site_iid} ({done_count + 1}/{runnable_count})...")

                # Payload
                await RunCoverageService.make_payload(
                    config=config,
                    session=session,
                    step=step,
                    job_id=job_id,
                    url_params=url_params,
                    array_types=array_types,
                    cells=cells,
                    boundary_coords=boundary_coords,
                    output_location=output_location_unc,
                    output_name=output_name,
                    redis_client=redis_client,
                    db=db,
                )

                # Call coverage API
                await RunCoverageService.call_coverage(
                    db=db,
                    step=step,
                    session=session,
                    project_name=project_name,
                    redis_client=redis_client,
                    url_params=url_params,
                    config=config,
                )

                # Poll until done
                poll_count = 0
                max_polls = config.max_polls
                poll_interval = config.poll_interval
                await RedisService.publish_log(redis_client, f"logs:{session_id_val}", f"Polling for {site_iid} (every {poll_interval}s)...")

                while poll_count < max_polls:
                    poll_count += 1
                    run_code, status_msg = await RunCoverageService.poll_coverage(step, config)
                    coverage_meta = step.step_metadata.get("coverage", {})
                    coverage_meta["poll_count"] = poll_count
                    step.step_metadata["coverage"] = coverage_meta
                    flag_modified(step, "step_metadata")
                    await db.commit()

                    denom = runnable_count if runnable_count else 1
                    overall_progress = int((done_count / denom) * 100) + int((poll_count / max_polls) * (100 / denom))
                    overall_progress = min(overall_progress, 99)
                    await RunCoverageService._update_execution_state(
                        db, session, execution_state_key, ExecutionStatus.RUNNING, overall_progress, job_id, redis_client
                    )
                    await RedisService.publish_log(redis_client, f"logs:{session_id_val}", f"  {site_iid} poll #{poll_count}: {status_msg}")

                    if run_code == 1:
                        # Update ACSSCandidateCoverageRun with status and coverage folder path
                        stored_cov_path = join_paths(output_retrieval_base_dir,output_name, array_type)
                        row.cov_status = True
                        row.cov_path = stored_cov_path
                        flag_modified(row, "cov_status")
                        flag_modified(row, "cov_path")
                        coverage_meta["status"] = "completed"
                        step.step_metadata["coverage"] = coverage_meta
                        flag_modified(step, "step_metadata")
                        await db.commit()
                        done_count += 1
                        progress = int((done_count / runnable_count) * 100) if runnable_count else 100
                        await RunCoverageService._update_execution_state(
                            db, session, execution_state_key, ExecutionStatus.RUNNING, progress, job_id, redis_client
                        )
                        await RedisService.publish_log(redis_client, f"logs:{session_id_val}", f"  Completed {site_iid} ({done_count}/{runnable_count}); cov_path={stored_cov_path}")
                        break
                    elif run_code == 2:
                        # Update ACSSCandidateCoverageRun: mark failed, clear path
                        row.cov_status = False
                        row.cov_path = None
                        flag_modified(row, "cov_status")
                        flag_modified(row, "cov_path")
                        error_msg = f"Coverage failed for site {site_iid}: {status_msg}"
                        step.status = StepStatus.FAILED
                        flag_modified(step, "status")
                        coverage_meta["status"] = "failed"
                        coverage_meta["error_message"] = status_msg
                        step.step_metadata["coverage"] = coverage_meta
                        flag_modified(step, "step_metadata")
                        await db.commit()
                        progress_pct = int((done_count / runnable_count) * 100) if runnable_count else 0
                        await RunCoverageService._update_execution_state(
                            db, session, execution_state_key, ExecutionStatus.ERROR, progress_pct, job_id, redis_client, end_time=True
                        )
                        await RedisService.publish_log(redis_client, f"logs:{session_id_val}", f"  {error_msg}")
                        raise HTTPException(status_code=400, detail=error_msg)

                    await asyncio.sleep(poll_interval)

                else:
                    # Update ACSSCandidateCoverageRun: mark failed (timeout), clear path
                    row.cov_status = False
                    row.cov_path = None
                    flag_modified(row, "cov_status")
                    flag_modified(row, "cov_path")
                    error_msg = f"Coverage for site {site_iid} did not complete within {max_polls} polls"
                    step.status = StepStatus.FAILED
                    flag_modified(step, "status")
                    coverage_meta = step.step_metadata.get("coverage", {})
                    coverage_meta["status"] = "failed"
                    coverage_meta["error_message"] = error_msg
                    step.step_metadata["coverage"] = coverage_meta
                    flag_modified(step, "step_metadata")
                    await db.commit()
                    progress_pct = int((done_count / runnable_count) * 100) if runnable_count else 0
                    await RunCoverageService._update_execution_state(
                        db, session, execution_state_key, ExecutionStatus.ERROR, progress_pct, job_id, redis_client, end_time=True
                    )
                    await RedisService.publish_log(redis_client, f"logs:{session_id_val}", error_msg)
                    raise HTTPException(status_code=400, detail=error_msg)

            # All candidates done
            step.status = StepStatus.COMPLETED
            flag_modified(step, "status")
            await db.commit()
            await RunCoverageService._update_execution_state(
                db, session, execution_state_key, ExecutionStatus.DONE, 100, job_id, redis_client, end_time=True
            )
            await RedisService.publish_log(redis_client, f"logs:{session_id_val}", f"All {runnable_count} candidate coverages completed.")
            return step

        except HTTPException:
            raise
        except Exception as e:
            error_msg = f"Error during candidate coverage run: {str(e)}"
            step.status = StepStatus.FAILED
            flag_modified(step, "status")
            await db.commit()
            await RunCoverageService._update_execution_state(
                db, session, execution_state_key, ExecutionStatus.ERROR, 99, job_id, redis_client, end_time=True
            )
            await RedisService.publish_log(redis_client, f"logs:{session_id_val}", error_msg)
            raise
