import os
import json
import asyncio
from typing import List, Literal
from zipfile import Path
from fastapi import HTTPException
import httpx
from uuid import UUID
from datetime import datetime
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from asp_app.services.candidate_services.validify_excel_service import ExcelColumnValidator
from asp_app.services.redis_service import RedisService
from asp_app.config.acss_config import get_candidate_config
from asp_app.config.tech_config_resolver import get_tech_config
from asp_app.db.models import ACSSSession, ACSSStep, ACSSCandidateCoverageRun
from sqlalchemy.orm.attributes import flag_modified
from asp_app.db.schemas.execution import ExecutionStepName, ExecutionStatus, ExecutionStatusState
from asp_app.services.candidate_services.location_payload_service import LocationService
from asp_app.services.candidate_services.mu_payload_service import MUService
from asp_app.services.candidate_services.cell_payload_service import CellService
from asp_app.db.models import StepStatus
import logging

logger = logging.getLogger(__name__)    


class CandidateService:
    """Service for managing candidate site operations."""
    
    # Class-level constants
    HEADERS = {
        "Content-Type": "application/json",
        "api-key": "teoco"
    }

    NODE_TYPE_MAPPING = {
            "location": "LocationObjectv214Type",
            "mu": "MUNodev214Type",
            "cell": "Cellv214Type"
        } 
    
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

    @staticmethod
    async def validate_gdl_columns(gdl_path: str, tech: str = "LTE") -> dict:
        config_path = get_tech_config(tech).columns_path
        return ExcelColumnValidator.validate_excel_columns(gdl_path, config_path)
    
    @staticmethod
    async def callEDSAPI(object_type: str, payload: dict, redis_client: Redis, session_id: UUID, verify_only: bool = False):
        params = {
            "autoCreateLogAnt": "true",
            "autoCreatePhsAnt": "true"
        }
         
        if verify_only:
            params["verifyOnly"] = "true"

        eds_create_url = get_candidate_config().eds_create_url
        if not eds_create_url:
            error_msg = "EDS_CREATE_URL not found in environment variables"
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"❌ ERROR: {error_msg}")
            raise ValueError(error_msg)
        
        url = f"{eds_create_url}/{object_type}"
        
        await RedisService.publish_log(redis_client, f"logs:{session_id}", f"📡 Calling EDS API for {object_type}...")
        await RedisService.publish_log(redis_client, f"logs:{session_id}", f"   URL: {url}")
        await RedisService.publish_log(redis_client, f"logs:{session_id}", f"   Payload items: {len(payload.get('appData', []))}")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=CandidateService.HEADERS,
                    params=params
                )
                
                if response.status_code >= 400:
                    error_msg = f"EDS API Error ({object_type}): Status {response.status_code}"
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", f"❌ {error_msg}")
                    response.raise_for_status()
                await RedisService.publish_log(redis_client, f"logs:{session_id}", f"✅ Successfully Called EDS API for {object_type} objects")
                return response.json()
                
        except httpx.HTTPError as e:
            error_msg = f"HTTP Error calling EDS API for {object_type}"
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"❌ {error_msg}")
            raise
        except Exception as e:
            error_msg = f"Unexpected error calling EDS API for {object_type}"
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"❌ {error_msg}")
            raise

    async def delete_eds(object_type: str, payload: dict):
        eds_delete_url = get_candidate_config().eds_delete_url
        if not eds_delete_url:
            error_msg = "EDS_DELETE_URL not found in environment variables"
            raise ValueError(error_msg)
        url = f"{eds_delete_url}/{object_type}"


        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
            "DELETE",
            url,
            json=payload,
            headers=CandidateService.HEADERS,
        )

        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    async def delete_by_type(
    node_type: Literal["location", "mu", "cell"],
    iids: List[str],
    bvid: str,
    tech: str = "LTE",
    ) -> dict:


        if node_type not in CandidateService.NODE_TYPE_MAPPING:
            raise ValueError(f"Invalid node_type: {node_type}. Must be one of: {list(CandidateService.NODE_TYPE_MAPPING.keys())}")
        
        if not iids:
            raise ValueError("iids list cannot be empty")
        
        # Get the EDS object type
        object_type = CandidateService.NODE_TYPE_MAPPING[node_type]
        
        # Build payload based on node_type
        app_data = []
        
        for iid in iids:
            if node_type == "location":
                app_data.append({
                    "$type": object_type,
                    "iid": iid,
                    "bvid": bvid
                })
            elif node_type == "mu":
                app_data.append({
                    "$type": object_type,
                    "technology": {
                        "fixedtechnology": tech
                    },
                    "iid": iid,
                    "bvid": bvid
                })
            elif node_type == "cell":
                app_data.append({
                    "$type": object_type,
                    "technology": {
                        "fixed": True,
                        "active": tech
                    },
                    "iid": iid,
                    "bvid": bvid
                })
        
        payload = {"appData": app_data}
        
        print(f"Deleting {len(iids)} {node_type}(s)...")

        # Call the delete API
        response = await CandidateService.delete_eds(object_type, payload)

        print(f"Successfully deleted {len(iids)} {node_type}(s)")
        return response


    @staticmethod
    async def _delete_from_payload_file(eds_object_type: str, file_path: str) -> int:
        """Send the saved JSON payload file to EDS as a DELETE body.

        Matches the manual delete-script flow the user proved works against
        EDS — DELETE /v1/EDS/Delete/{ObjectType} with the EXACT same payload
        we used to create the objects. Returns the number of items in
        ``appData`` so the caller can report a deleted count.

        Raises FileNotFoundError if the payload file does not exist (the
        caller falls back to IID-based delete in that case).
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Payload file not found: {file_path}")

        # JSON parse on a thread to avoid blocking the event loop on large files
        def _load_json():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        payload = await asyncio.to_thread(_load_json)

        count = len(payload.get("appData", []))
        if count == 0:
            return 0

        await CandidateService.delete_eds(eds_object_type, payload)
        return count

    @staticmethod
    async def cleanup_eds_sites_for_session(
        db: AsyncSession,
        session_id: UUID,
        project_name: str,
        redis_client: Redis,
    ) -> dict:
        """Testing helper — delete the last-created candidate sites from EDS.

        Strategy (mirrors the user's working delete script):

        1. **Primary** — file-based DELETE. For each tier we look up the
           saved JSON payload path in ``step_metadata`` (recorded by
           ``load_validate_and_create_candidates``) and POST that exact JSON
           as the DELETE body. EDS accepts this reliably because it is the
           same shape that succeeded as a CREATE.

        2. **Fallback** — IID-based DELETE. For sessions that pre-date the
           payload-path tracking (no ``*_payload_path`` keys) we rebuild a
           minimal ``{$type, iid, bvid}`` payload from the recorded IID list
           via ``CandidateService.delete_by_type``.

        Order: cell → MU → location (reverse of create order, EDS FK-safe).
        Each tier is best-effort — failure on one tier still attempts the
        next. Successfully deleted IIDs are cleared from step_metadata so
        the next Run creates fresh sites without 406-Partial collisions.

        All unexpected failures are caught and surfaced via the ``errors``
        dict so the HTTP layer always returns 200 with a structured body —
        never an opaque 500.
        """
        from asp_app.db.models import ACSSStep, StepName

        deleted = {"cell": 0, "mu": 0, "location": 0}
        errors: dict = {}

        try:
            # Order by created_at DESC, not id — ACSSStep.id is a random UUID4
            # so id ordering would return an arbitrary step row.
            step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.session_id == session_id,
                    ACSSStep.step_name == StepName.CREATING_CANDIDATES,
                ).order_by(ACSSStep.created_at.desc()).limit(1)
            )
            step = step_result.scalar_one_or_none()

            if step is None or not step.step_metadata:
                await RedisService.publish_log(
                    redis_client, f"logs:{session_id}",
                    "EDS cleanup: no candidate-creation step found — nothing to delete"
                )
                return {"deleted": deleted, "errors": errors}

            md = step.step_metadata
            # Reverse-create order so MU/Location aren't deleted while Cells reference them
            tiers = [
                # (logical name, EDS object type, payload file key, IID list key)
                ("cell",     "Cellv214Type",            "cell_payload_path",     "cell_iids"),
                ("mu",       "MUNodev214Type",          "mu_payload_path",       "mu_iids"),
                ("location", "LocationObjectv214Type",  "location_payload_path", "location_iids"),
            ]
            for node_type, eds_type, file_key, iids_key in tiers:
                file_path = md.get(file_key)
                iids = md.get(iids_key) or []
                if not file_path and not iids:
                    continue  # nothing to delete in this tier

                try:
                    count = 0
                    method = None
                    # Primary: file-based delete (replays the exact create payload)
                    if file_path and os.path.isfile(file_path):
                        count = await CandidateService._delete_from_payload_file(
                            eds_type, file_path
                        )
                        method = "file"
                    # Fallback: IID-based delete for pre-tracking sessions
                    elif iids:
                        await CandidateService.delete_by_type(
                            node_type=node_type, iids=iids, bvid=project_name,
                        )
                        count = len(iids)
                        method = "iid"
                    else:
                        continue

                    deleted[node_type] = count
                    md[iids_key] = []  # clear IIDs so re-create won't collide
                    await RedisService.publish_log(
                        redis_client, f"logs:{session_id}",
                        f"EDS cleanup: deleted {count} {node_type}(s) via {method}"
                        + (f" ({os.path.basename(file_path)})" if method == "file" else "")
                    )
                except Exception as e:
                    errors[node_type] = f"{type(e).__name__}: {e}"
                    await RedisService.publish_log(
                        redis_client, f"logs:{session_id}",
                        f"EDS cleanup: failed to delete {node_type}(s) — {e}"
                    )

            flag_modified(step, "step_metadata")
            await db.commit()
        except Exception as e:
            # Any unexpected failure (DB error, schema mismatch, etc.) becomes
            # a structured error in the response — never bubble to a 500.
            logger.exception("EDS cleanup encountered an unexpected error")
            try:
                await db.rollback()
            except Exception:
                pass
            errors["_internal"] = f"{type(e).__name__}: {e}"
            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"EDS cleanup: internal error — {e}"
            )

        return {"deleted": deleted, "errors": errors}


    @staticmethod
    async def load_validate_and_create_candidates(
        db: AsyncSession, 
        session_id: UUID, 
        redis_client: Redis, 
        job_id: str, 
        session: ACSSSession,
        project_name: str, 
        gdl_path: str,
        execution_state_key: ExecutionStepName,
        step: ACSSStep,
        tech: str = "LTE",
    ) -> ACSSStep:
        
        try:
            await CandidateService._update_execution_state(
                db=db,
                session=session,
                execution_state_key=execution_state_key,
                status=ExecutionStatus.RUNNING,
                progress=0,
                job_id=job_id,
                redis_client=redis_client
            )
            step.status = StepStatus.IN_PROGRESS
            flag_modified(step, "status")
            await db.commit()
            # Step 1: Validate columns
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "🔍 Validating GDL columns...")
            validation_result = await CandidateService.validate_gdl_columns(gdl_path, tech=tech)
            
            if not validation_result["valid"]:
                await RedisService.publish_log(redis_client, f"logs:{session_id}", f"❌ {validation_result['message']}")
                raise ValueError(validation_result["message"])
            
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "✅ GDL column validation passed")
            
            await CandidateService._update_execution_state(
                db=db,
                session=session,
                execution_state_key=execution_state_key,
                status=ExecutionStatus.RUNNING,
                progress=10,
                job_id=job_id,
                redis_client=redis_client
            )
            # Step 2: Build payloads
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "🔨 Building Location payload...")
            location_payload, payload_path =await LocationService.build_location_payload(gdl_path, project_name, tech=tech)
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"   Created {len(location_payload.get('appData', []))} location objects")
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"   Payload stored at: {payload_path}")
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "🔨 Building MU payload...")
            
            step.step_metadata["location_iids"] = [item.get('iid') for item in location_payload.get('appData', [])]
            # Record the saved JSON payload path so the standalone EDS-cleanup
            # button can replay the *exact* original create payload as a DELETE
            # body — matches the manual delete-script pattern that EDS accepts.
            step.step_metadata["location_payload_path"] = str(payload_path)
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"   Location iids: {step.step_metadata['location_iids']}")
            flag_modified(step, "step_metadata")
            await db.commit()
            await db.refresh(step)

            await CandidateService._update_execution_state(
                db=db,
                session=session,
                execution_state_key=execution_state_key,
                status=ExecutionStatus.RUNNING,
                progress=20,
                job_id=job_id,
                redis_client=redis_client
            )
            mu_payload, mu_payload_path = await MUService.build_mu_payload(gdl_path, project_name, tech=tech)
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"   Created {len(mu_payload.get('appData', []))} MU objects")
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"   Payload stored at: {mu_payload_path}")

            step.step_metadata["mu_iids"] = [item.get('iid') for item in mu_payload.get('appData', [])]
            step.step_metadata["mu_payload_path"] = str(mu_payload_path)
            # Compact map: site (location) iid -> list of mu iids (for later delete without storing full payload)
            site_with_mu_iids = {}
            for mu_obj in mu_payload.get("appData", []):
                site_iid = mu_obj.get("location", {}).get("iid")
                if site_iid is not None:
                    site_with_mu_iids.setdefault(site_iid, []).append(mu_obj.get("iid"))
            step.step_metadata["site_with_mu_iids"] = site_with_mu_iids
            flag_modified(step, "step_metadata")
            await db.commit()
            await db.refresh(step)
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "🔨 Building Cell payload...")
            await CandidateService._update_execution_state(
                db=db,
                session=session,
                execution_state_key=execution_state_key,
                status=ExecutionStatus.RUNNING,
                progress=30,
                job_id=job_id,
                redis_client=redis_client
            )
            cell_payload, cell_payload_path = await CellService.build_cell_payload(gdl_path, project_name, tech=tech)
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"   Created {len(cell_payload.get('appData', []))} cell objects")
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"   Payload stored at: {cell_payload_path}")
            cell_objects = cell_payload.get('appData', [])
            #getting object that will have site stucture like this:
            # {
            #     "site_id": "123",
            #     "cells": [
            #         {
            #             "cell_id": "456",
            #         }
            #     ]
            # }

            site_structure = {}
            for cell in cell_objects:
                site_id = cell.get('location', {}).get('iid')
                cell_id = cell.get('iid')
                site_structure.setdefault(site_id, []).append(cell_id)

            step.step_metadata["site_with_cells"] = site_structure
            step.step_metadata["cell_iids"] = [item.get('iid') for item in cell_payload.get('appData', [])]
            step.step_metadata["cell_payload_path"] = str(cell_payload_path)

            # Remove any existing candidate coverage run rows for this session (e.g. from a re-run)
            await db.execute(delete(ACSSCandidateCoverageRun).where(ACSSCandidateCoverageRun.session_id == session.id))

            for site_iid, cell_list in site_structure.items():
                row = ACSSCandidateCoverageRun(
                    session_id=session.id,
                    site_iid=site_iid,
                    cell_iids=cell_list,
                    cov_status=False,
                    cov_path=None,
                )
                db.add(row)

            flag_modified(step, "step_metadata")
            await db.commit()
            await CandidateService._update_execution_state(
                db=db,
                session=session,
                execution_state_key=execution_state_key,
                status=ExecutionStatus.RUNNING,
                progress=40,
                job_id=job_id,
                redis_client=redis_client
            )


     
            await CandidateService._update_execution_state(
                db=db,
                session=session,
                execution_state_key=execution_state_key,
                status=ExecutionStatus.RUNNING,
                progress=50,
                job_id=job_id,
                redis_client=redis_client
            )

            # Step 3: Call EDS API to create objects
            
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "📤 Creating candidates in EDS...")
            check_partial_error = False
            try:
                logger.info(f"Location payload: {location_payload}")
                result= await CandidateService.callEDSAPI(CandidateService.NODE_TYPE_MAPPING["location"], location_payload, redis_client, session_id)
                logger.info(f"Result: {result}")
                if result["code"]=="Partial":
                    check_partial_error = True
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", f"❌ Error: Some of the Candidates in the Provided GDL already present in the EDS")
                    raise HTTPException(status_code=406, detail="Some of the Candidates in the Provided GDL already present in the EDS")

            except Exception as e:
                if check_partial_error:
                    raise
                await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Cleaning up: deleting Location candidates from EDS...")
                try:
                    await CandidateService.delete_by_type(
                        node_type="location",
                        iids=step.step_metadata.get("location_iids", []),
                        bvid=project_name
                    )
                except Exception as e:
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", f"❌ Error deleting Location candidates from EDS")
                raise
            
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "✅ Location objects created s:uccessfully!")
            await CandidateService._update_execution_state(
                db=db,
                session=session,
                execution_state_key=execution_state_key,
                status=ExecutionStatus.RUNNING,
                progress=60,
                job_id=job_id,
                redis_client=redis_client
            )
            check_partial_error = False
            try:
                await CandidateService.callEDSAPI(CandidateService.NODE_TYPE_MAPPING["mu"], mu_payload, redis_client, session_id)
                if result["code"]=="Partial":
                    check_partial_error = True
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", f"❌ Error: Some of the MU in the Provided GDL already present in the EDS")
                    raise HTTPException(status_code=406, detail="Some of the MU in the Provided GDL already present in the EDS")
            except Exception as e:
                if check_partial_error:
                    raise
                await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Cleaning up: deleting MU and Location candidates from EDS...")
                try:
                    await CandidateService.delete_by_type(
                        node_type="mu",
                        iids=step.step_metadata.get("mu_iids", []),
                        bvid=project_name
                    )
                    await CandidateService.delete_by_type(
                        node_type="location",
                        iids=step.step_metadata.get("location_iids", []),
                        bvid=project_name
                    )
                except Exception as e:
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Error deleting MU and Location candidates from EDS")
                await RedisService.publish_log(redis_client, f"logs:{session_id}", f"MU and Location candidates deleted from EDS successfully!")
                raise

            await RedisService.publish_log(redis_client, f"logs:{session_id}", "✅ MU objects created successfully!")
            await CandidateService._update_execution_state(
                db=db,
                session=session,
                execution_state_key=execution_state_key,
                status=ExecutionStatus.RUNNING,
                progress=70,
                job_id=job_id,
                redis_client=redis_client
            )
            check_partial_error = False
            try:
                await CandidateService.callEDSAPI(CandidateService.NODE_TYPE_MAPPING["cell"], cell_payload, redis_client, session_id)
                if result["code"]=="Partial":
                    check_partial_error = True
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", f"❌ Error: Some of the Cells in the Provided GDL already present in the EDS")
                    raise HTTPException(status_code=406, detail="Some of the Cells in the Provided GDL already present in the EDS")
            except Exception as e:
                if check_partial_error:
                    raise
                await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Cleaning up: deleting Cell, MU and Location candidates from EDS...")
                try:
                    await CandidateService.delete_by_type(
                    node_type="cell",
                    iids=step.step_metadata.get("cell_iids", []),
                    bvid=project_name
                )
                    await CandidateService.delete_by_type(
                        node_type="mu",
                        iids=step.step_metadata.get("mu_iids", []),
                        bvid=project_name
                    )
                    await CandidateService.delete_by_type(
                    node_type="location",
                    iids=step.step_metadata.get("location_iids", []),
                    bvid=project_name
                    )

                except Exception as e:
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Error deleting Cell, MU and Location candidates from EDS")
                await RedisService.publish_log(redis_client, f"logs:{session_id}", f"✅ Cell, MU and Location candidates deleted from EDS successfully!")
                raise 

            await RedisService.publish_log(redis_client, f"logs:{session_id}", "✅ Cell objects created successfully!")
            await CandidateService._update_execution_state(
                db=db,
                session=session,
                execution_state_key=execution_state_key,
                status=ExecutionStatus.RUNNING,
                progress=80,
                job_id=job_id,
                redis_client=redis_client
            )
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "✅ All candidate objects created successfully!")
            
            # Step 4: Save compact site->(mu_iids, cell_iids) structure only (no full payloads to avoid huge metadata)
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "💾 Saving candidate indices into the step data...")
            # location_iids, site_with_cells, site_with_mu_iids, mu_iids, cell_iids already set above
            flag_modified(step, "step_metadata")
            await db.commit()
            await RedisService.publish_log(redis_client, f"logs:{session_id}", "✅ Candidates saved into the step data successfully!")
            step.status = StepStatus.COMPLETED
            flag_modified(step, "status")
            await CandidateService._update_execution_state(
                db=db,
                session=session,
                execution_state_key=execution_state_key,
                status=ExecutionStatus.DONE,
                progress=100,
                job_id=job_id,
                redis_client=redis_client,
                end_time=True
            )
            
            return step
        except Exception as e:
            # Roll back so the session is usable for updating step/execution state
            await db.rollback()
            # Get error message based on exception type
            if isinstance(e, HTTPException):
                error_msg = str(e.detail)
            else:
                error_msg = f"Error during validate candidates: {str(e)}"
            # Update execution_status_state to ERROR
            await CandidateService._update_execution_state(
                db=db,
                session=session,
                execution_state_key=execution_state_key,
                status=ExecutionStatus.ERROR,
                progress=99,
                job_id=job_id,
                redis_client=redis_client,
                end_time=True
            )
            # Update step status
            step.status = StepStatus.FAILED
            flag_modified(step, "status")
            creating_candidates_meta = step.step_metadata.get("creatingCandidates", {})
            creating_candidates_meta["status"] = "failed"
            creating_candidates_meta["error_message"] = error_msg
            step.step_metadata["creatingCandidates"] = creating_candidates_meta
            flag_modified(step, "step_metadata")
            await db.commit()
            
            
            
            raise
                
