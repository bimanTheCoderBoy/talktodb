import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from fastapi import HTTPException
from urllib.parse import quote
import httpx

from asp_app.db.schemas.coverage import CoverageUrlParameters, RunCoverageRequest
from asp_app.db.schemas.execution import ExecutionStatus, ExecutionStatusState, ExecutionStepName
from asp_app.db.models import ACSSStep, ACSSSession, StepStatus
from asp_app.utils.iid_hash_utils import HASHING_ENABLED, is_hashed_value, reverse_map_hashes_sql
from asp_app.config.acss_config import CoverageAPIConfig, get_coverage_api_config
from asp_app.services.redis_service import RedisService
from redis import Redis


# Workflow status mapping
WORKFLOW_STATUS = {
    "pending": "workflow is registered but not started yet",
    "fetching": "data querying to the EDS service is in progress",
    "verifying": "all retrieved data is being checked for errors or missing information",
    "generating": "construction of CGA requests in progress",
    "awaitingApproval": "indicates workflow is paused pending approval",
    "issuing": "transmission of CGA requests in progress",
    "processing": "waiting for CGA to complete its work but processing it’s notifications as they occur to provide update notifications to CWE clients",
    "cancelling": "workflow has been requested to abort at next available check point",
    "cancelled": "workflow was successfully cancelled at the stage it received the command at (finalization value)",
    "partial": "workflow completed with at least one task succeeding but one or more failed tasks (finalization value)",
    "failed": "all tasks in the workflow failed (finalization value)",
    "completed": "workflow completed successfully (finalization value)",
}


class RunCoverageService:
    """Simplified service for coverage API operations."""

    # ============ MAKE PAYLOAD ============

    @staticmethod
    async def make_payload(
        config: CoverageAPIConfig,
        session: ACSSSession,
        step: ACSSStep,
        job_id: str,
        url_params: CoverageUrlParameters,
        array_types: List[str],
        cells: List[str],
        boundary_coords: List[List[float]],
        output_location: str,
        output_name: str,
        redis_client: Redis,
        db: AsyncSession
    ) -> str:
        """
        Build coverage API payload from session setup_state and save to file.
        """
        session_id = session.id
        await RedisService.publish_log(redis_client, f"logs:{session_id}", "Creating coverage payload...")
        
        # Load template
        template_path = Path(config.payload_template_path)
        with open(template_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        
        # Reverse-map hashed cell IIDs — external coverage API needs original values
        if HASHING_ENABLED and cells:
            hashes = set(c for c in cells if c and is_hashed_value(c))
            if hashes:
                rmap = await reverse_map_hashes_sql(db, hashes)
                if rmap:
                    cells = [rmap.get(c, c) for c in cells]

        # Update payload
        payload["cells"] = cells
        payload["arrayTypes"] = array_types
        payload["extents"]["geometry"]["coordinates"] = boundary_coords
        
      
        
        payload["output"] = {
            "type": config.payload_output_type,
            "name": output_name,
            "location": output_location,
        
        }
        
        # Ensure payload storage directory exists
        payload_store = Path(config.payload_store)
        payload_store.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        payload_filename = f"CWE_{step.step_name.value}_{timestamp}.json"
        payload_path = payload_store / payload_filename
        
        # Save payload
        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump(payload, indent=4, fp=f)
        
        await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Payload saved: {payload_filename}")
        
        # Store coverage info in step_metadata
        step_metadata = step.step_metadata or {}
        step_metadata["coverage"] = {
            "url_params": url_params.model_dump(),
            "array_type": array_types[0],
            "cells": cells,
            "boundary_coords": boundary_coords,
            "payload_path": str(payload_path),
            "token": None,
            "poll_count": 0,
            "status": "payload_created",
            "error_message": None
        }
        step.step_metadata = step_metadata
        flag_modified(step, "step_metadata")
        await db.commit()
    
        
        return str(payload_path)

    # ============ CALL COVERAGE API ============

    @staticmethod
    async def call_coverage(
        db: AsyncSession,
        step: ACSSStep,
        session: ACSSSession,
        project_name: str,
        redis_client: Redis,
        url_params: CoverageUrlParameters,
        config: CoverageAPIConfig
    ) -> str:
        """
        Call the coverage API with the payload.
        """
        session_id = session.id
        
        await RedisService.publish_log(redis_client, f"logs:{session_id}", "Calling coverage API...")
        coverage_meta = step.step_metadata.get("coverage", {})
        # Build URL with parameters
        base_url = config.create_coverage_endpoint
        project = quote(project_name)
        technology = quote(url_params.technology)
        resolution = quote(url_params.resolution)
        mode = quote(url_params.mode)
        terminal = quote(url_params.terminal)
        auto_approve = str(url_params.auto_approve).lower()
        
        url = (
            f"{base_url}?project={project}&technology={technology}"
            f"&resolution={resolution}&mode={mode}&terminal={terminal}"
            f"&autoApprove={auto_approve}"
        )
        
        height = url_params.height
        carrier = url_params.carrier
        if height:
            url += f"&height={quote(height)}"
        if carrier:
            url += f"&carrier={quote(carrier)}"
        
        # Load payload
        payload_path = coverage_meta.get("payload_path")
        if not payload_path:
            raise HTTPException(status_code=400, detail="Payload path not found. Call make_payload first.")
        
        with open(payload_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json-patch+json",
            "Accept": "text/plain",
            "api-key": config.api_key
        }
        
        # Make API call
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        
        if response.status_code != 201:
            error_msg = f"Coverage API returned status {response.status_code}: {response.text}"
            coverage_meta["status"] = "failed"
            coverage_meta["error_message"] = error_msg
            step.step_metadata["coverage"] = coverage_meta
            flag_modified(step, "step_metadata")
            await db.commit()
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"API call failed: {error_msg}")
            raise HTTPException(status_code=response.status_code, detail=error_msg)
        
        # Extract token
        response_data = response.json()
        token = response_data.get("token")
        
        if not token:
            error_msg = "No token received from coverage API"
            coverage_meta["status"] = "failed"
            coverage_meta["error_message"] = error_msg
            step.step_metadata["coverage"] = coverage_meta
            flag_modified(step, "step_metadata")
            await db.commit()
            raise HTTPException(status_code=500, detail=error_msg)
        
        # Update step_metadata
        coverage_meta["token"] = token
        coverage_meta["status"] = "polling"
        step.step_metadata["coverage"] = coverage_meta
        flag_modified(step, "step_metadata")
        await db.commit()
        
        await RedisService.publish_log(redis_client, f"logs:{session_id}", f"API called successfully. Token: {token}")
        
        return token

    # ============ POLL COVERAGE ============

    @staticmethod
    async def poll_coverage(
        step: ACSSStep, 
        config: CoverageAPIConfig
    ) -> Tuple[int, str]:
        """
        Poll the coverage API for status (single poll).
        
        Args:
            step: ACSSStep with coverage metadata containing token
            config: CoverageAPIConfig
            
        Returns:
            Tuple of (run_code, status_message)
            - run_code: 0=in_progress, 1=completed/partial, 2=failed/cancelled
        """
        coverage_meta = step.step_metadata.get("coverage", {})
        token = coverage_meta.get("token")
        
        if not token:
            return 2, "No token available for polling"
        
        # Build polling URL
        base_url = config.status_polling_endpoint
        url = f"{base_url}/{token}"
        
        headers = {
            "accept": "application/json",
            "api-key": config.api_key
        }
        #We are using try catch here because , if we do not do it the main error handler will catch but the execution will not be stopped.
        # But one Polling Failure should not stop the execution.
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
            
            data = response.json()
            
            if data.get("item"):
                work_item = data["item"]
                status = work_item.get("status", "").lower()
                status_msg = WORKFLOW_STATUS.get(status, f"Status: {status}")
                
                if status in ["completed", "partial"]:
                    return 1, f"{status}: {status_msg}"
                elif status in ["cancelled", "failed"]:
                    return 2, f"{status}: {status_msg}"
                else:
                    return 0, f"{status}: {status_msg}"
            else:
                return 0, f"No work item found. Token: {token}"
                
        except httpx.RequestError as e:
            return 2, f"Request error: {str(e)}"
        except Exception as e:
            return 2, f"Unexpected error: {str(e)}"

    # ============ HELPER: UPDATE EXECUTION STATE ============

    @staticmethod
    async def _update_execution_state(
        db: AsyncSession,
        session: ACSSSession,
        execution_state_key: ExecutionStepName,
        status: ExecutionStatus,
        progress: int,
        job_id: str,
        redis_client: Redis,
        end_time: bool = False
    ):
        """Helper to update execution_status_state in session and publish to Redis."""
        execution_state = ExecutionStatusState(**session.execution_status_state)
        step_state = getattr(execution_state, execution_state_key.value)
        step_state.status = status
        step_state.progress = progress
        if status == ExecutionStatus.RUNNING and step_state.startTime is None:
            step_state.startTime = datetime.utcnow()
        if end_time:
            step_state.endTime = datetime.utcnow()
        session.execution_status_state = execution_state.model_dump(mode="json")
        flag_modified(session, "execution_status_state")
        await db.commit()
        await RedisService.publish_execution_state(redis_client, job_id, session.execution_status_state)

    # ============ MAIN ORCHESTRATOR ============

    @staticmethod
    async def run(
        session: ACSSSession,
        step: ACSSStep,
        db: AsyncSession,
        run_coverage_request: RunCoverageRequest,
        redis_client: Redis,
        execution_state_key: ExecutionStepName
    ) -> ACSSStep:
        """
        Main orchestrator - runs the complete coverage workflow for a step.
        
        Updates both step data (step.step_metadata, step.status) and 
        execution_status_state in session.
        """
        config = run_coverage_request.baseconfig
        project_name = run_coverage_request.project_name
        job_id = run_coverage_request.job_id
        url_params = run_coverage_request.url_params
        array_types = run_coverage_request.array_types
        cells = run_coverage_request.cells
        boundary_coords = run_coverage_request.boundary_coords
        output_location = run_coverage_request.output_location
        output_name = run_coverage_request.output_name
        session_id = session.id

        # Log start
        await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Starting coverage for step: {step.step_name.value}")
        
        # Update step status to IN_PROGRESS
        step.status = StepStatus.IN_PROGRESS
        flag_modified(step, "status")
        await db.commit()
        
        # Update execution_status_state to RUNNING
        await RunCoverageService._update_execution_state(
            db, session, execution_state_key, ExecutionStatus.RUNNING, 0, job_id, redis_client
        )
        
        try:
            # Step 1: Make payload
            payload_path = await RunCoverageService.make_payload(
                config, session, step, job_id, url_params, array_types, cells, 
                boundary_coords, output_location, output_name, redis_client, db
            )
            
            await RunCoverageService._update_execution_state(
                db, session, execution_state_key, ExecutionStatus.RUNNING, 10, job_id, redis_client
            )
            
            # # Step 2: Call coverage API
            token = await RunCoverageService.call_coverage(
                db, step, session, project_name, redis_client, url_params, config
            )
            
            # Update progress after API call
            await RunCoverageService._update_execution_state(
                db, session, execution_state_key, ExecutionStatus.RUNNING, 20, job_id, redis_client
            )
            
            # Step 3: Poll for completion
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Polling started (every {config.poll_interval}s)...")
            coverage_meta = step.step_metadata.get("coverage", {})
            
            poll_count = coverage_meta.get("poll_count", 0)
            max_polls = config.max_polls
            poll_interval = config.poll_interval
            
            while poll_count < max_polls:
                poll_count += 1
                
                run_code, status_msg = await RunCoverageService.poll_coverage(
                    step, config
                )
                
                # Update poll count in step metadata
                coverage_meta = step.step_metadata.get("coverage", {})
                coverage_meta["poll_count"] = poll_count
                step.step_metadata["coverage"] = coverage_meta
                flag_modified(step, "step_metadata")
                await db.commit()
                
                # Calculate progress (20% base + 80% polling progress)
                poll_progress = 20 + int((poll_count / max_polls) * 80)
                await RunCoverageService._update_execution_state(
                    db, session, execution_state_key, ExecutionStatus.RUNNING, min(poll_progress, 99), job_id, redis_client
                )
                
                await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Poll #{poll_count}: {status_msg}")
                
                if run_code == 1:
                    # Completed successfully
                    coverage_meta["status"] = "completed"
                    step.step_metadata["coverage"] = coverage_meta
                    step.status = StepStatus.COMPLETED
                    flag_modified(step, "step_metadata")
                    flag_modified(step, "status")
                    await db.commit()
                    
                    # Update execution_status_state to DONE
                    await RunCoverageService._update_execution_state(
                        db, session, execution_state_key, ExecutionStatus.DONE, 100, job_id, redis_client, end_time=True
                    )
                    
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Coverage completed after {poll_count} polls! Output location: {output_location}")
                    return step
                    
                elif run_code == 2:
                    # Failed
                    coverage_meta["status"] = "failed"
                    coverage_meta["error_message"] = status_msg
                    step.step_metadata["coverage"] = coverage_meta
                    step.status = StepStatus.FAILED
                    flag_modified(step, "step_metadata")
                    flag_modified(step, "status")
                    await db.commit()
                    
                    # Update execution_status_state to ERROR
                    await RunCoverageService._update_execution_state(
                        db, session, execution_state_key, ExecutionStatus.ERROR, poll_progress, job_id, redis_client, end_time=True
                    )
                    
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Coverage failed: {status_msg}")
                    raise HTTPException(status_code=400, detail=f"Coverage failed: {status_msg}")
                
                # Still in progress, wait before next poll
                await asyncio.sleep(poll_interval)
            
            # Max polls exceeded
            error_msg = f"Coverage did not complete within {max_polls} polls"
            coverage_meta = step.step_metadata.get("coverage", {})
            coverage_meta["status"] = "failed"
            coverage_meta["error_message"] = error_msg
            step.step_metadata["coverage"] = coverage_meta
            step.status = StepStatus.FAILED
            flag_modified(step, "step_metadata")
            flag_modified(step, "status")
            await db.commit()
            
            # Update execution_status_state to ERROR
            await RunCoverageService._update_execution_state(
                db, session, execution_state_key, ExecutionStatus.ERROR, 99, job_id, redis_client, end_time=True
            )
            
            await RedisService.publish_log(redis_client, f"logs:{session_id}", error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
            
        except Exception as e:
            # Get error message based on exception type
            if isinstance(e, HTTPException):
                error_msg = str(e.detail)
            else:
                error_msg = f"Error during coverage: {str(e)}"
            
            # Update step status
            step.status = StepStatus.FAILED
            flag_modified(step, "status")
            coverage_meta = step.step_metadata.get("coverage", {})
            coverage_meta["status"] = "failed"
            coverage_meta["error_message"] = error_msg
            step.step_metadata["coverage"] = coverage_meta
            flag_modified(step, "step_metadata")
            await db.commit()
            
            # Update execution_status_state to ERROR
            await RunCoverageService._update_execution_state(
                db, session, execution_state_key, ExecutionStatus.ERROR, 99, job_id, redis_client, end_time=True
            )
            
            await RedisService.publish_log(redis_client, f"logs:{session.id}", f"Error Running Coverage Error : {error_msg}")
            raise
