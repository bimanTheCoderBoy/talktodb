import asyncio
import json
from uuid import UUID
from fastapi import HTTPException
from redis import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

import pandas as pd

from asp_app.db.models import ACSSSession, ACSSStep, SessionStatus, StepName, StepStatus
from asp_app.db.schemas.execution import ExecutionStepName, ExecutionStatus
from asp_app.config.array_type_mapper import ArrayTypeMapper
from asp_app.config.tech_config_resolver import get_tech_config
from asp_app.services.candidate_services.candidate_service import CandidateService
from asp_app.services.redis_service import RedisService
from asp_app.services.run_coverage_service import RunCoverageService
from asp_app.services.setup_service import _extract_field


class UpdateActualCandidatesService:
    """Deletes non-selected candidates (cells, MUs, locations) using CREATING_CANDIDATES step_metadata: location_iids, site_with_cells, site_with_mu_iids."""

    @staticmethod
    async def _build_saved_candidates(
        gdl_path: str,
        keep_site_iids: set,
        tech: str,
        location_mapping: dict,
        cell_mapping: dict,
    ) -> list:
        """Read the GDL Excel and build site objects (same format as baselineCells)
        for the kept candidate sites.

        Column names are read from ``site_preview`` / ``cell_preview`` sections
        of the location and cell EDS mappings.
        """
        site_prev = location_mapping["site_preview"]
        cell_prev = cell_mapping["cell_preview"]
        site_id_col = site_prev["site_iid"]["excel"]

        df = await asyncio.to_thread(pd.read_excel, gdl_path)

        df = df[df[site_id_col].astype(str).str.strip().isin(keep_site_iids)]

        sites: dict = {}
        for _, row in df.iterrows():
            site_iid = _extract_field(row, site_prev["site_iid"])
            if not site_iid:
                continue

            if site_iid not in sites:
                sites[site_iid] = {
                    "site_iid": site_iid,
                    "latitude": _extract_field(row, site_prev["latitude"]),
                    "longitude": _extract_field(row, site_prev["longitude"]),
                    "technology": [tech],
                    "cells": [],
                }

            cell_iid = _extract_field(row, cell_prev["cell_iid"])
            if cell_iid is None:
                continue

            cell_obj = {
                "cell_iid": cell_iid,
                "azimuth": _extract_field(row, cell_prev["azimuth"]) or 0,
                "band": _extract_field(row, cell_prev["band"]),
                "pci": _extract_field(row, cell_prev["pci"]),
                "technology": tech,
                "selected": True,
            }
            sites[site_iid]["cells"].append(cell_obj)

        return list(sites.values())

    @staticmethod
    async def run(
        db: AsyncSession,
        session: ACSSSession,
        step: ACSSStep,
        session_id: UUID,
        job_id: str,
        redis_client: Redis,
        project_name: str,
    ) -> None:
        step.status = StepStatus.IN_PROGRESS
        flag_modified(step, "status")
        await db.commit()

        # Resolve technology from polygon arrayType
        polygon = (session.setup_state or {}).get("polygon") or {}
        array_type = polygon.get("arrayType", "LTE_Best_RSRP")
        tech = ArrayTypeMapper.to_technology(array_type)

        await RunCoverageService._update_execution_state(
            db, session, ExecutionStepName.UPDATE_ACTUAL_CANDIDATES,
            ExecutionStatus.RUNNING, 0, job_id, redis_client
        )
        try:
            # 1) Get selected candidate (sites to keep) from FINAL_EVALUATION step
            fe_step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.step_name == StepName.FINAL_EVALUATION,
                    ACSSStep.session_id == session_id,
                )
            )
            fe_step = fe_step_result.scalar_one_or_none()
            if not fe_step or not fe_step.step_metadata:
                raise HTTPException(status_code=400, detail="Final evaluation step metadata not found")

            selection = fe_step.step_metadata.get("selection", {})
            if selection.get("status") != "confirmed":
                raise HTTPException(status_code=400, detail="No confirmed candidate selection found")

            # Support multi-select: read list first, fall back to single string for backward compat
            selected_candidate_names = selection.get("selected_candidate_names")
            if not selected_candidate_names:
                single = selection.get("selected_candidate_name")
                if not single:
                    raise HTTPException(status_code=400, detail="Selected candidate name is empty")
                selected_candidate_names = [single]

            # Merge site IIDs from all selected candidates
            keep_site_iids = set()
            for name in selected_candidate_names:
                for s in name.split("|"):
                    s = s.strip()
                    if s:
                        keep_site_iids.add(s)

            if not keep_site_iids:
                raise HTTPException(status_code=400, detail="No site IIDs found in selected candidates")

            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"Keeping sites: {keep_site_iids}"
            )

            # 2) Get compact candidate indices from CREATING_CANDIDATES step (no full payloads)
            cc_step_result = await db.execute(
                select(ACSSStep).where(
                    ACSSStep.step_name == StepName.CREATING_CANDIDATES,
                    ACSSStep.session_id == session_id,
                    ACSSStep.status == StepStatus.COMPLETED,
                )
            )
            cc_step = cc_step_result.scalar_one_or_none()
            if not cc_step or not cc_step.step_metadata:
                raise HTTPException(status_code=400, detail="Creating candidates step metadata not found")

            all_location_iids = cc_step.step_metadata.get("location_iids", [])
            site_with_cells = cc_step.step_metadata.get("site_with_cells", {})
            site_with_mu_iids = cc_step.step_metadata.get("site_with_mu_iids", {})

            # 3) Compute what to delete
            delete_site_iids = [s for s in all_location_iids if s not in keep_site_iids]

            if not delete_site_iids:
                await RedisService.publish_log(
                    redis_client, f"logs:{session_id}",
                    "No candidates to delete — all sites are kept."
                )
            else:
                delete_cell_iids = []
                for site_iid in delete_site_iids:
                    delete_cell_iids.extend(site_with_cells.get(site_iid, []))

                delete_mu_iids = []
                for site_iid in delete_site_iids:
                    delete_mu_iids.extend(site_with_mu_iids.get(site_iid, []))

                await RedisService.publish_log(
                    redis_client, f"logs:{session_id}",
                    f"Deleting {len(delete_site_iids)} sites, {len(delete_mu_iids)} MUs, {len(delete_cell_iids)} cells"
                )

                await RunCoverageService._update_execution_state(
                    db, session, ExecutionStepName.UPDATE_ACTUAL_CANDIDATES,
                    ExecutionStatus.RUNNING, 20, job_id, redis_client
                )

                if delete_cell_iids:
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", "Deleting cell candidates from EDS...")
                    await CandidateService.delete_by_type(
                        node_type="cell", iids=delete_cell_iids, bvid=project_name, tech=tech
                    )
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", "Cell candidates deleted successfully")

                await RunCoverageService._update_execution_state(
                    db, session, ExecutionStepName.UPDATE_ACTUAL_CANDIDATES,
                    ExecutionStatus.RUNNING, 50, job_id, redis_client
                )

                if delete_mu_iids:
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", "Deleting MU candidates from EDS...")
                    await CandidateService.delete_by_type(
                        node_type="mu", iids=delete_mu_iids, bvid=project_name, tech=tech
                    )
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", "MU candidates deleted successfully")

                await RunCoverageService._update_execution_state(
                    db, session, ExecutionStepName.UPDATE_ACTUAL_CANDIDATES,
                    ExecutionStatus.RUNNING, 75, job_id, redis_client
                )

                if delete_site_iids:
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", "Deleting location candidates from EDS...")
                    await CandidateService.delete_by_type(
                        node_type="location", iids=delete_site_iids, bvid=project_name, tech=tech
                    )
                    await RedisService.publish_log(redis_client, f"logs:{session_id}", "Location candidates deleted successfully")

            # 4) Build saved_candidates site objects from GDL Excel for kept sites
            saved_candidates = []
            gdl_path = (session.setup_state or {}).get("loadCandidateGdl", {}).get("filePath")
            if gdl_path:
                await RedisService.publish_log(
                    redis_client, f"logs:{session_id}",
                    "Building saved candidate site objects from GDL..."
                )
                try:
                    tech_cfg = get_tech_config(tech)
                    with open(tech_cfg.location_eds_mapping_path, "r", encoding="utf-8") as f:
                        location_mapping = json.load(f)
                    with open(tech_cfg.cell_eds_mapping_path, "r", encoding="utf-8") as f:
                        cell_mapping = json.load(f)
                    saved_candidates = await UpdateActualCandidatesService._build_saved_candidates(
                        gdl_path, keep_site_iids, tech, location_mapping, cell_mapping
                    )
                    total_cells = sum(len(s.get("cells", [])) for s in saved_candidates)
                    await RedisService.publish_log(
                        redis_client, f"logs:{session_id}",
                        f"Built {len(saved_candidates)} saved candidate sites ({tech}) with {total_cells} cells"
                    )
                except Exception as e:
                    await RedisService.publish_log(
                        redis_client, f"logs:{session_id}",
                        f"Warning: Could not build saved candidates from GDL: {e}"
                    )
            else:
                await RedisService.publish_log(
                    redis_client, f"logs:{session_id}",
                    "Warning: GDL file path not found in setup_state; skipping saved_candidates"
                )

            # 5) Mark step and session as completed
            step.status = StepStatus.COMPLETED
            step.step_metadata = {
                "kept_sites": list(keep_site_iids),
                "deleted_sites": delete_site_iids,
                "selected_candidate_names": selected_candidate_names,
                "saved_candidates": saved_candidates,
            }
            flag_modified(step, "status")
            flag_modified(step, "step_metadata")

            # Also persist saved_candidates into session.setup_state so the frontend
            # can access them on session reload (alongside baselineCells).
            setup_state = dict(session.setup_state or {})
            setup_state["savedCandidates"] = saved_candidates
            session.setup_state = setup_state
            flag_modified(session, "setup_state")
            await db.commit()

            await RunCoverageService._update_execution_state(
                db, session, ExecutionStepName.UPDATE_ACTUAL_CANDIDATES,
                ExecutionStatus.DONE, 100, job_id, redis_client, end_time=True
            )

            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                "Update actual candidates complete."
            )

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
                db, session, ExecutionStepName.UPDATE_ACTUAL_CANDIDATES,
                ExecutionStatus.ERROR, 99, job_id, redis_client, end_time=True
            )
            await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Update actual candidates error: {error_msg}")
            raise HTTPException(status_code=400, detail=f"Update actual candidates failed: {error_msg}") from e
