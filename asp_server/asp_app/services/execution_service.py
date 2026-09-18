import asyncio
import json
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from fastapi import HTTPException

from asp_app.services.final_eveluation_service import FinalEvaluationService
from asp_app.services.update_actual_candidates_service import UpdateActualCandidatesService
from asp_app.config.acss_config import CoverageAPIConfig, get_coverage_api_config, join_paths
from asp_app.config.array_type_mapper import ArrayTypeMapper
from asp_app.db.schemas.coverage import CoverageUrlParameters, RunCoverageRequest
from asp_app.db.models import ACSSSession, ACSSStep, ACSSCandidateCoverageRun, ACSSCandidateEvaluation, SessionStatus, StepName, StepStatus
from asp_app.services.candidate_services.candidate_service import CandidateService
from asp_app.services.candidate_coverage_run_service import CandidateCoverageRunService
from redis import Redis
from asp_app.services.redis_service import RedisService
from asp_app.services.run_coverage_service import RunCoverageService
from asp_app.services.calculate_combinations_service import CalculateCombinationsService
from asp_app.db.schemas.execution import ExecutionStatusState, ExecutionStepState, ExecutionStepName, ExecutionStatus
from asp_app.db.schemas.setup import GoalType
from asp_app.services.candidate_services.candidate_evaluation_service import CandidateEvaluationService
from asp_app.services.map_encoding_service import MapEncodingService

logger = logging.getLogger(__name__)

def to_unc_path(path: str) -> str:
    """
    Convert a path like /host/path/parts to UNC format \\host\\path\\parts.
    Used for API payload output.location so the coverage service receives a valid UNC path.
    """
    if path is None:
        return ""
    if not path or not path.strip():
        return path
    normalized = path.strip().replace("\\", "/").strip("/")
    if not normalized:
        return path
    # Convert to UNC: /a/b/c -> \\a\\b\\c
    return "\\\\" + normalized.replace("/", "\\")

class ExecutionService:
    """Service for handling the 5-step execution process with a simple state structure."""

    @staticmethod
    async def _get_session(db: AsyncSession, session_id: UUID) -> ACSSSession:
        result = await db.execute(
            select(ACSSSession).where(ACSSSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        return session

    @staticmethod
    async def _get_execution_state(db: AsyncSession, session: ACSSSession) -> dict:
        """Returns the initial flat state for execution steps."""
        state = session.execution_status_state
        if not state:
            state = ExecutionStatusState(
                baselineCoverage=ExecutionStepState(status=ExecutionStatus.PENDING, progress=0, startTime=None, endTime=None),
                autoGenCandidates=ExecutionStepState(status=ExecutionStatus.PENDING, progress=0, startTime=None, endTime=None),
                creatingCandidates=ExecutionStepState(status=ExecutionStatus.PENDING, progress=0, startTime=None, endTime=None),
                runingCoverageForCandidates=ExecutionStepState(status=ExecutionStatus.PENDING, progress=0, startTime=None, endTime=None),
                calculateCombinations=ExecutionStepState(status=ExecutionStatus.PENDING, progress=0, startTime=None, endTime=None),
                calculation=ExecutionStepState(status=ExecutionStatus.PENDING, progress=0, startTime=None, endTime=None),
                finalEvaluation=ExecutionStepState(status=ExecutionStatus.PENDING, progress=0, startTime=None, endTime=None),
                updateActualCandidates=ExecutionStepState(status=ExecutionStatus.PENDING, progress=0, startTime=None, endTime=None),
                runningCoverageForBaselineAndCandidates=ExecutionStepState(status=ExecutionStatus.PENDING, progress=0, startTime=None, endTime=None),
                convertingBilsForInteractiveView=ExecutionStepState(status=ExecutionStatus.PENDING, progress=0, startTime=None, endTime=None)
            )
            session.execution_status_state = state.model_dump(mode="json")
            flag_modified(session, "execution_status_state")
            await db.commit()
            await db.refresh(session)
        return state

    @staticmethod
    async def run_execution(db: AsyncSession, session_id: UUID, redis_client: Redis, job_id: str, project_name: str):
        """Main entry point that runs 5 steps sequentially, each taking 30s."""

        session = await ExecutionService._get_session(db, session_id)
        if session.status == SessionStatus.COMPLETED:
            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                "Session already completed — nothing to run."
            )
            return {
                "status": "skipped",
                "message": "This session has already finished. Start a new session to run again.",
            }
        if session.status == SessionStatus.CANCELLED:
            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                "Session was cancelled — nothing to run."
            )
            return {
                "status": "skipped",
                "message": "This session was cancelled. Start a new session to run again.",
            }
        if session.status != SessionStatus.IN_PROGRESS:
           session.status=SessionStatus.IN_PROGRESS
           flag_modified(session, "status")
           await db.commit()
           await db.refresh(session)
        execution_state = await ExecutionService._get_execution_state(db, session)
        
        # Resolve technology from polygon arrayType (once, for all steps)
        polygon_state_init = (session.setup_state or {}).get("polygon") or {}
        tech = ArrayTypeMapper.to_technology(polygon_state_init.get("arrayType", "LTE_Best_RSRP"))

        # Publish initial state
        await RedisService.publish_execution_state(redis_client, job_id, session.execution_status_state)
        
        # ============ BASELINE COVERAGE STEP ============
       
        if session.execution_status_state["baselineCoverage"]["status"] == "pending" or  session.execution_status_state["baselineCoverage"]["status"] == "error":
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Running baseline coverage")
            # Create or get the step
            step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.step_name == StepName.BASELINE_COVERAGE,
                    ACSSStep.session_id == session_id,
                )
            )
            step = step_result.scalar_one_or_none()
            if not step:
                step = ACSSStep(step_name=StepName.BASELINE_COVERAGE, session_id=session_id)
                db.add(step)
                await db.commit()
                await db.refresh(step)
            
            # Prepare request data from setup_state
            polygon_state = session.setup_state.get("polygon", {})
            array_type = polygon_state.get("arrayType", "LTE_Best_RSRP")
            technology = polygon_state.get("technology", "LTE")
            boundary_coords = polygon_state.get("coords", [])
            baseline_cells_site_array = polygon_state.get("baselineCells", [])
            if not baseline_cells_site_array:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", "Baseline cells site array not found")
                raise HTTPException(status_code=400, detail="Baseline cells site array not found")
            if not array_type:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", "Array type not found")
                raise HTTPException(status_code=400, detail="Array type not found")
            if not boundary_coords:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", "Boundary coords not found")
                raise HTTPException(status_code=400, detail="Boundary coords not found")
            cells = []
            for site in baseline_cells_site_array:
                for cell in site.get("cells", []):
                    if cell.get("selected", True):
                        cells.append(cell.get("cell_iid"))
            
            if not boundary_coords or not array_type or not cells:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", "Missing required data: boundary_coords, array_type, or cells")
                raise HTTPException(status_code=400, detail="Missing required data for baseline coverage")
            
            # URL parameters
            url_params = CoverageUrlParameters(
                technology=technology, resolution="50", mode="Composite", 
                terminal="Multi-Tech Default", auto_approve=True
            )
            
            # Config and output location
            config = get_coverage_api_config()
            
            output_location = join_paths(config.payload_root_output_location, project_name, str(session_id))
            output_name = StepName.BASELINE_COVERAGE.value
            
            run_coverage_request = RunCoverageRequest(
                project_name=project_name, job_id=job_id,
                url_params=url_params, array_types=[array_type], cells=cells,
                boundary_coords=boundary_coords, baseconfig=config,
                output_location=to_unc_path(output_location), output_name=output_name
            )
            
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Calling RunCoverageService...")
            # RunCoverageService handles both step and execution_status_state updates
            result_step = await RunCoverageService.run(
                session, step,
                db, run_coverage_request, redis_client,
                execution_state_key=ExecutionStepName.BASELINE_COVERAGE
            )


        # ============ AUTO-GEN CANDIDATES STEP ============
        # Runs only for auto-gen sessions (autoGenConfig present).
        # Seed-aware idempotency lives inside run_autogen_step → _should_skip:
        # re-runs when filePath is empty OR when the persisted materialized_seed
        # differs from the currently-configured seed (Regenerate-with-different-seed).
        load_state = (session.setup_state or {}).get("loadCandidateGdl") or {}
        if load_state.get("autoGenConfig"):
            exec_state_now = session.execution_status_state or {}
            autogen_status = exec_state_now.get("autoGenCandidates", {}).get("status")
            if autogen_status in ("pending", "error"):
                await CandidateService._update_execution_state(
                    db=db, session=session,
                    execution_state_key=ExecutionStepName.AUTO_GEN_CANDIDATES,
                    status=ExecutionStatus.RUNNING, progress=0,
                    job_id=job_id, redis_client=redis_client,
                )
                await RedisService.publish_log(
                    redis_client, f"logs:{session_id}", "Running auto-gen v2 candidate synthesis"
                )
                try:
                    from asp_app.services.autogenv2.orchestrator import run_autogen_pipeline
                    session = await run_autogen_pipeline(db, session, redis_client, project_name, job_id)
                    await db.refresh(session)
                    await CandidateService._update_execution_state(
                        db=db, session=session,
                        execution_state_key=ExecutionStepName.AUTO_GEN_CANDIDATES,
                        status=ExecutionStatus.DONE, progress=100,
                        job_id=job_id, redis_client=redis_client, end_time=True,
                    )
                except Exception as e:
                    await CandidateService._update_execution_state(
                        db=db, session=session,
                        execution_state_key=ExecutionStepName.AUTO_GEN_CANDIDATES,
                        status=ExecutionStatus.ERROR, progress=0,
                        job_id=job_id, redis_client=redis_client, end_time=True,
                    )
                    raise


        exec_state = session.execution_status_state or {}
        creating_status = exec_state.get("creatingCandidates", {}).get("status")
        if creating_status in ("pending", "error"):
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Running creating candidates")
            # Create or get the step
            step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.step_name == StepName.CREATING_CANDIDATES,
                    ACSSStep.session_id == session_id,
                )
            )
            step = step_result.scalar_one_or_none()
            if not step:
                step = ACSSStep(step_name=StepName.CREATING_CANDIDATES, session_id=session_id)
                db.add(step)
                await db.commit()
                await db.refresh(step)
            

            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Calling CandidateService to create candidates...")
            gdl_path=session.setup_state.get("loadCandidateGdl", {}).get("filePath", None)
            if not gdl_path:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", "GDL file not found")
                raise HTTPException(status_code=400, detail="GDL file not found")

            result_step = await CandidateService.load_validate_and_create_candidates(
                db, session_id, redis_client, job_id, session, project_name, gdl_path,
                execution_state_key=ExecutionStepName.CREATING_CANDIDATES,
                step=step,
                tech=tech,
            )
        

        
 
        # Run coverage for all candidates (one step, one coverage run per candidate site)
        if session.execution_status_state["runingCoverageForCandidates"]["status"] == "pending" or session.execution_status_state["runingCoverageForCandidates"]["status"] == "error":
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Running coverage for candidates")
            #Create or get the step
            step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.step_name == StepName.RUNNING_COVERAGE_FOR_CANDIDATES,
                    ACSSStep.session_id == session_id,
                )
            )
            step = step_result.scalar_one_or_none()
            if not step:
                step = ACSSStep(step_name=StepName.RUNNING_COVERAGE_FOR_CANDIDATES, session_id=session_id)
                db.add(step)
                await db.commit()
                await db.refresh(step)
            else:
                step.status = StepStatus.PENDING
                flag_modified(step, "status")
                await db.commit()
                await db.refresh(step)

            polygon_state = session.setup_state.get("polygon", {})
            technology = polygon_state.get("technology", "LTE")
            url_params = CoverageUrlParameters(
                technology=technology, resolution="50", mode="Composite",
                terminal="Multi-Tech Default", auto_approve=True
            )
            config = get_coverage_api_config()
            boundary_coords = polygon_state.get("coords", [])
            if not boundary_coords:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", "Boundary coords not found")
                raise HTTPException(status_code=400, detail="Boundary coords not found")
            array_type = polygon_state.get("arrayType", "LTE_Best_RSRP")
            output_base_dir = join_paths(config.payload_root_output_location, project_name, str(session_id), StepName.RUNNING_COVERAGE_FOR_CANDIDATES.value)
            output_retrieval_base_dir = join_paths(config.coverage_root_output_retrieval_location, project_name, str(session_id), StepName.RUNNING_COVERAGE_FOR_CANDIDATES.value)
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Calling CandidateCoverageRunService...")
            await CandidateCoverageRunService.run(
                db=db,
                session=session,
                step=step,
                session_id=session_id,
                job_id=job_id,
                redis_client=redis_client,
                execution_state_key=ExecutionStepName.RUNNING_COVERAGE_FOR_CANDIDATES,
                url_params=url_params,
                boundary_coords=boundary_coords,
                array_type=array_type,
                config=config,
                project_name=project_name,
                output_base_dir=output_base_dir,
                output_retrieval_base_dir=output_retrieval_base_dir,
            )

        # ============ CALCULATE COMBINATIONS STEP ============
        if session.execution_status_state["calculateCombinations"]["status"] == "pending" or session.execution_status_state["calculateCombinations"]["status"] == "error":
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Running calculate combinations")
            #Create or get the step
            step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.step_name == StepName.CALCULATE_COMBINATIONS,
                    ACSSStep.session_id == session_id,
                )
            )
            step = step_result.scalar_one_or_none()
            if not step:
                step = ACSSStep(step_name=StepName.CALCULATE_COMBINATIONS, session_id=session_id)
                db.add(step)
                await db.commit()
                await db.refresh(step)

            #find the candidate loading step and get the sites
            candidate_loading_step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.step_name == StepName.CREATING_CANDIDATES,
                    ACSSStep.session_id == session_id,
                    ACSSStep.status == StepStatus.COMPLETED,
                )
            )
            candidate_loading_step = candidate_loading_step_result.scalar_one_or_none()
            if not candidate_loading_step:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", "Candidate Creating step not found for calculate combinations")
                raise HTTPException(status_code=400, detail="Candidate Creating step not found")
            site_iids = candidate_loading_step.step_metadata.get("location_iids", [])
            if not site_iids:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", "Site iids not found")
                raise HTTPException(status_code=400, detail="Site iids not found")

            #get the k value
            k_value = session.setup_state.get("defineGoal", {}).get("parameters", {}).get("k_value")
            if not k_value:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", "K value not found")
                raise HTTPException(status_code=400, detail="K value not found")
            if not isinstance(k_value, int):
                k_value = int(k_value)
                if not k_value:
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", "K value is not a valid integer")
                    raise HTTPException(status_code=400, detail="K value is not a valid integer")

            if k_value < 1:
                detail = f"K value must be ≥ 1, got {k_value}"
                await RedisService.publish_log(redis_client, f"logs:{session_id}", detail)
                raise HTTPException(status_code=400, detail=detail)
            if k_value > len(site_iids):
                # Clamp instead of erroring — "best K of N" still makes sense
                # when N < requested K (degenerate to "best N of N" = single
                # combination). Better than blocking the entire pipeline on a
                # validation that the user can't easily fix mid-run.
                clamped_msg = (
                    f"K value clamped: requested k_value={k_value} but only "
                    f"{len(site_iids)} candidate site(s) were created in EDS. "
                    f"Proceeding with k_value={len(site_iids)} "
                    f"(C({len(site_iids)},{len(site_iids)})=1 combination)."
                )
                await RedisService.publish_log(redis_client, f"logs:{session_id}", clamped_msg)
                k_value = len(site_iids)

            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Calling CalculateCombinationsService...")
            await CalculateCombinationsService.run(
                db=db,
                session=session,
                step=step,
                session_id=session_id,
                k_value=k_value,
                site_iids=site_iids,
                redis_client=redis_client,
                job_id=job_id,
                execution_state_key=ExecutionStepName.CALCULATE_COMBINATIONS,
            )
        
        # ============ CALCULATION STEP ============
        if session.execution_status_state["calculation"]["status"] == "pending" or session.execution_status_state["calculation"]["status"] == "error":
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Running calculation")
            # Create or get the step
            step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.step_name == StepName.CALCULATION,
                    ACSSStep.session_id == session_id,
                )
            )
            step = step_result.scalar_one_or_none()
            if not step:
                step = ACSSStep(step_name=StepName.CALCULATION, session_id=session_id)
                db.add(step)
                await db.commit()
                await db.refresh(step)

            # Prepare inputs: goal_type, goal_parameters, baseline_path, candidate_paths
            define_goal = session.setup_state.get("defineGoal", {}) or {}
            goal_type_str = define_goal.get("goalType", GoalType.INCREASE_RSRP.value)
            try:
                goal_type = GoalType(goal_type_str)
            except ValueError:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Unknown goal type: {goal_type_str}")
                raise HTTPException(status_code=400, detail=f"Unknown goal type: {goal_type_str}")
            goal_parameters = define_goal.get("parameters", {})

            config = get_coverage_api_config()
            array_type = session.setup_state.get("polygon", {}).get("arrayType", "LTE_Best_RSRP")
            if not array_type:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", "Array type not found")
                raise HTTPException(status_code=400, detail="Array type not found")
            # Baseline: BIL base path (no extension) for baseline coverage output
            baseline_path = join_paths(
                config.coverage_root_output_retrieval_location,
                project_name,
                str(session_id),
                StepName.BASELINE_COVERAGE.value,
                array_type
            )

            # Candidate paths from acss_candidate_coverage_run (site_iid, cov_path) where cov_status is True
            candidate_coverage_result = await db.execute(
                select(ACSSCandidateCoverageRun).where(
                    ACSSCandidateCoverageRun.session_id == session_id,
                    ACSSCandidateCoverageRun.cov_status.is_(True),
                ).order_by(ACSSCandidateCoverageRun.site_iid)
            )
            candidate_coverage_rows = list(candidate_coverage_result.scalars().all())
            candidate_paths: List[Tuple[str, str]] = [
                (row.site_iid, row.cov_path) for row in candidate_coverage_rows if row.cov_path
            ]
            if not candidate_paths:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", "Candidate paths not found")
                raise HTTPException(status_code=400, detail="Candidate paths not found")
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Calling CandidateEvaluationService...")
            await CandidateEvaluationService.run(
                db=db,
                session=session,
                step=step,
                session_id=session_id,
                goal_type=goal_type,
                goal_parameters=goal_parameters,
                baseline_path=baseline_path,
                candidate_paths=candidate_paths,
                redis_client=redis_client,
                job_id=job_id,
                execution_state_key=ExecutionStepName.CALCULATION,
            )

        # ============ FINAL EVALUATION STEP ============
        await db.refresh(session)
        fe_status = session.execution_status_state["finalEvaluation"]["status"]
        if fe_status == "pending" or fe_status == "error":
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Running final evaluation")
            # Create or get the step
            step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.step_name == StepName.FINAL_EVALUATION,
                    ACSSStep.session_id == session_id,
                )
            )
            step = step_result.scalar_one_or_none()
            if not step:
                step = ACSSStep(step_name=StepName.FINAL_EVALUATION, session_id=session_id)
                db.add(step)
                await db.commit()
                await db.refresh(step)

            step.status = StepStatus.IN_PROGRESS


            await FinalEvaluationService.run(
                db=db,
                session=session,
                step=step,
                session_id=session_id,
                job_id=job_id,
                redis_client=redis_client,
            )
            # Exit successfully — finalEvaluation is now WAITING_USER.
            # Do not raise: Celery would treat that as FAILURE and the UI
            # would show a red health error for a normal pause.
            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                "Execution paused for candidate selection. Waiting for user confirmation."
            )
            return {
                "status": "paused",
                "message": "Waiting for user to select a candidate",
            }

        # If finalEvaluation is still waiting_user (user hasn't confirmed yet), exit gracefully
        if fe_status == "waiting_user":
            # Check if user has confirmed selection in step_metadata
            fe_step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.step_name == StepName.FINAL_EVALUATION,
                    ACSSStep.session_id == session_id,
                )
            )
            fe_step = fe_step_result.scalar_one_or_none()
            selection = (fe_step.step_metadata or {}).get("selection", {}) if fe_step else {}
            if selection.get("status") != "confirmed":
                await RedisService.publish_log(
                    redis_client, f"logs:{session_id}",
                    "Final evaluation still waiting for user confirmation. Exiting."
                )
                # Re-publish WAITING_USER so frontend stays informed
                await RedisService.publish_execution_state(redis_client, job_id, session.execution_status_state)
                return

        # ============ UPDATE ACTUAL CANDIDATES STEP (delete non-selected candidates) ============
        await db.refresh(session)
        if True or session.execution_status_state["updateActualCandidates"]["status"] == "pending" or session.execution_status_state["updateActualCandidates"]["status"] == "error":
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Running update actual candidates (deleting non-selected)")
            step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.step_name == StepName.UPDATE_ACTUAL_CANDIDATES,
                    ACSSStep.session_id == session_id,
                )
            )
            step = step_result.scalar_one_or_none()
            if not step:
                step = ACSSStep(step_name=StepName.UPDATE_ACTUAL_CANDIDATES, session_id=session_id)
                db.add(step)
                await db.commit()
                await db.refresh(step)
            
            await UpdateActualCandidatesService.run(
                db=db,
                session=session,
                step=step,
                session_id=session_id,
                job_id=job_id,
                redis_client=redis_client,
                project_name=project_name,
            )

        # ============ RUNNING COVERAGE FOR BASELINE + SAVED CANDIDATES STEP ============
        await db.refresh(session)
        if session.execution_status_state["runningCoverageForBaselineAndCandidates"]["status"] in ("pending", "error"):
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Running coverage for baseline + saved candidates")

            # Create or get the step
            step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.step_name == StepName.RUNNING_COVERAGE_FOR_BASELINE_AND_CANDIDATES,
                    ACSSStep.session_id == session_id,
                )
            )
            step = step_result.scalar_one_or_none()
            if not step:
                step = ACSSStep(step_name=StepName.RUNNING_COVERAGE_FOR_BASELINE_AND_CANDIDATES, session_id=session_id)
                db.add(step)
                await db.commit()
                await db.refresh(step)

            # Build combined cells: baseline cells + saved candidate cells
            polygon_state = session.setup_state.get("polygon", {})
            array_type = polygon_state.get("arrayType", "LTE_Best_RSRP")
            technology = polygon_state.get("technology", "LTE")
            boundary_coords = polygon_state.get("coords", [])
            baseline_cells_site_array = polygon_state.get("baselineCells", [])

            cells_set = set()
            # Baseline cells
            for site in baseline_cells_site_array:
                for cell in site.get("cells", []):
                    if cell.get("selected", True):
                        cell_iid = cell.get("cell_iid")
                        if cell_iid:
                            cells_set.add(cell_iid)

            # Saved candidate cells
            saved_candidates = session.setup_state.get("savedCandidates", [])
            for site in saved_candidates:
                for cell in site.get("cells", []):
                    cell_iid = cell.get("cell_iid")
                    if cell_iid:
                        cells_set.add(cell_iid)

            cells = list(cells_set)

            if not boundary_coords or not array_type or not cells:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", "Missing required data for baseline + candidates coverage")
                raise HTTPException(status_code=400, detail="Missing required data for baseline + candidates coverage")

            url_params = CoverageUrlParameters(
                technology=technology, resolution="50", mode="Composite",
                terminal="Multi-Tech Default", auto_approve=True
            )

            config = get_coverage_api_config()
            output_location = join_paths(config.payload_root_output_location, project_name, str(session_id))
            output_name = StepName.RUNNING_COVERAGE_FOR_BASELINE_AND_CANDIDATES.value

            run_coverage_request = RunCoverageRequest(
                project_name=project_name, job_id=job_id,
                url_params=url_params, array_types=[array_type], cells=cells,
                boundary_coords=boundary_coords, baseconfig=config,
                output_location=to_unc_path(output_location), output_name=output_name
            )

            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Calling RunCoverageService with {len(cells)} combined cells (baseline + saved candidates)...")
            await RunCoverageService.run(
                session, step,
                db, run_coverage_request, redis_client,
                execution_state_key=ExecutionStepName.RUNNING_COVERAGE_FOR_BASELINE_AND_CANDIDATES
            )

        # ============ CONVERTING BILS FOR INTERACTIVE VIEW STEP ============
        await db.refresh(session)
        if session.execution_status_state["convertingBilsForInteractiveView"]["status"] in ("pending", "error"):
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "Converting BILs for interactive view")

            # Create or get the step
            step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.step_name == StepName.CONVERTING_BILS_FOR_INTERACTIVE_VIEW,
                    ACSSStep.session_id == session_id,
                )
            )
            step = step_result.scalar_one_or_none()
            if not step:
                step = ACSSStep(step_name=StepName.CONVERTING_BILS_FOR_INTERACTIVE_VIEW, session_id=session_id)
                db.add(step)
                await db.commit()
                await db.refresh(step)
            
            await MapEncodingService.run(
                db=db,
                session=session,
                step=step,
                session_id=session_id,
                job_id=job_id,
                redis_client=redis_client,
                project_name=project_name,
            )

            # Mark the overall session as completed
            await db.refresh(session)
            session.status = SessionStatus.COMPLETED
            flag_modified(session, "status")
            await db.commit()

            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                "BIL conversion complete. Execution finished."
            )