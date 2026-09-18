import asyncio
import json
import os
import shutil
from uuid import UUID
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from fastapi import HTTPException, UploadFile

from asp_app.db.models import ACSSSession
from asp_app.db.schemas.setup import (
    PutPolygonRequest,
    DefineGoalRequest,
    SetupStatus,
    GoalType,
)
from redis import Redis

from asp_app.config.acss_config import get_acss_config
from asp_app.config.array_type_mapper import ArrayTypeMapper
from asp_app.config.tech_config_resolver import get_tech_config
from asp_app.services.candidate_services.validify_excel_service import ExcelColumnValidator
from asp_app.services.redis_service import RedisService

GDL_STORAGE_DIR = get_acss_config().gdl_storage_dir


def _extract_field(row, field_spec):
    """Read a value from a DataFrame row using a mapping field spec.

    ``field_spec`` is a dict like ``{"excel": "Cell: LTE: PCI ID", "transform": "int", "default": 0}``.
    """
    val = row.get(field_spec["excel"])
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return field_spec.get("default")
    xform = field_spec.get("transform", "str")
    if xform == "float":
        return float(val)
    if xform == "int":
        return int(val)
    return str(val).strip()

class SetupService:
    """Service for handling setup state operations."""

    @staticmethod
    async def _get_session(db: AsyncSession, session_id: UUID) -> ACSSSession:
        """Helper method to get session by ID."""
        result = await db.execute(
            select(ACSSSession).where(ACSSSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session with ID {session_id} not found"
            )
        return session

    @staticmethod
    def _get_setup_state(session: ACSSSession) -> dict:
        """Get or initialize setup state from session."""
        if session.setup_state is None:
            return {
                "loadProject": {"status": "done"},  
                "polygon": {
                    "status": "pending",
                    "coords": None,
                    "boundaryRadius": None,
                    "boundaryCoords": None,
                    "vertices": 0,
                    "timestamp": None,
                    "baselineCells": None,
                    "arrayType": None,
                    "selectedBand": None,
                },
                "loadCandidateGdl": {
                    "status": "pending",
                    "fileName": None,
                    "filePath": None,
                    "autoGenConfig": None,
                },
                "defineGoal": {
                    "status": "pending",
                    "goalType": "increase_rsrp",
                    "parameters": {},
                },
            }
        return session.setup_state

    @staticmethod
    async def put_polygon(
        db: AsyncSession,
        acss_session_id: UUID,
        polygon_data: PutPolygonRequest,
        redis_client: Redis
    ) -> ACSSSession:
        """
        Update polygon coordinates in setup state
        """
        try:
            session = await SetupService._get_session(db, acss_session_id)
            setup_state = SetupService._get_setup_state(session)
            
            # Update polygon state
            setup_state["polygon"] = {
                "status": "done",
                "coords": polygon_data.polygon_coords,
                "boundaryRadius": polygon_data.boundary_radius,
                "boundaryCoords": polygon_data.boundary_coords,
                "vertices": len(polygon_data.polygon_coords),
                "timestamp": datetime.utcnow().isoformat(),
                "baselineCells": polygon_data.baseline_cells,
                "arrayType": polygon_data.array_type,
                "technology": polygon_data.technology,
                "selectedBand": polygon_data.selected_band,
            }
            
            # Update session and flag as modified (required for SQLAlchemy JSONB detection)
            session.setup_state = setup_state
            flag_modified(session, "setup_state")
            await db.commit()
            await db.refresh(session)
            
            await RedisService.publish_log(redis_client, f"logs:{acss_session_id}", f"Polygon updated successfully returning updated session")
            return session
            
        except HTTPException:
            raise
        except Exception as e:
            await RedisService.publish_log(redis_client, f"logs:{acss_session_id}", f"Failed to update polygon: {str(e)}")
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update polygon: {str(e)}"
            )

    @staticmethod
    async def upload_gdl(
        db: AsyncSession,
        acss_session_id: UUID,
        file: UploadFile,
        redis_client: Redis
    ) -> ACSSSession:
        """
        Upload GDL file and update setup state.
        """
        try:
            session = await SetupService._get_session(db, acss_session_id)
            setup_state = SetupService._get_setup_state(session)
            
            # Validate file extension
            if file.filename:
                file_ext = os.path.splitext(file.filename)[1].lower()
                if file_ext not in ['.csv', '.xlsx', '.xls']:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid file type. Only CSV, XLSX, and XLS files are allowed."
                    )
            
            # Ensure storage directory exists
            os.makedirs(GDL_STORAGE_DIR, exist_ok=True)
            
            # Generate unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"{acss_session_id}_{timestamp}_{file.filename}"
            file_path = os.path.join(GDL_STORAGE_DIR, safe_filename)
            
            # Save file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            await RedisService.publish_log(redis_client, f"logs:{acss_session_id}", f"GDL file saved to disk successfully")

            # Update setup state with file info
            setup_state["loadCandidateGdl"] = {
                "status": "done",
                "fileName": file.filename,
                "filePath": file_path,
            }
            session.setup_state = setup_state
            flag_modified(session, "setup_state")
            await db.commit()
            await db.refresh(session)

            # Validate columns and build all candidate site objects
            session = await SetupService.build_all_candidates_and_save_to_setup_state(
                db, session, file_path, redis_client,
            )

            await RedisService.publish_log(redis_client, f"logs:{acss_session_id}", f"GDL file uploaded and candidates built successfully")
            return session
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            await RedisService.publish_log(redis_client, f"logs:{acss_session_id}", f"Failed to upload GDL file: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload GDL file: {str(e)}"
            )

    @staticmethod
    async def define_goal(
        db: AsyncSession,
        acss_session_id: UUID,
        goal_data: DefineGoalRequest,
        redis_client: Redis,
    ) -> ACSSSession:
        """
        Define goal in setup state.
        """
        try:
            session = await SetupService._get_session(db, acss_session_id)
            setup_state = SetupService._get_setup_state(session)
            print(setup_state["defineGoal"])
            # Update goal state (generic parameters object)
            setup_state["defineGoal"] = {
                "status": "done",
                "goalType": goal_data.goal_type.value,
                "parameters": goal_data.parameters,
            }
            # Update session and flag as modified (required for SQLAlchemy JSONB detection)
            session.setup_state = setup_state
            flag_modified(session, "setup_state")
            await db.commit()
            await db.refresh(session)
            print(setup_state["defineGoal"])
            await RedisService.publish_log(redis_client, f"logs:{acss_session_id}", f"Goal defined successfully returning updated session")   
            return session
            
        except HTTPException:
            raise
        except Exception as e:
            await RedisService.publish_log(redis_client, f"logs:{acss_session_id}", f"Failed to define goal: {str(e)}")
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to define goal: {str(e)}"
            )

    @staticmethod
    async def get_setup_state(
        db: AsyncSession,
        session_id: UUID
    ) -> dict:
        """
        Get setup state for a session.
        
        Args:
            db: Database session
            session_id: UUID of the ACSS session
            
        Returns:
            Setup state dictionary
        """
        session = await SetupService._get_session(db, session_id)
        return SetupService._get_setup_state(session)

    # ============ BUILD ALL CANDIDATES FROM GDL ============

    @staticmethod
    def _build_site_objects_from_df(
        df: pd.DataFrame,
        tech: str,
        location_mapping: dict,
        cell_mapping: dict,
    ) -> list:
        """Build site objects (same format as baselineCells) from a GDL DataFrame.

        Column names are read from the ``site_preview`` section of the
        *location_mapping* and ``cell_preview`` section of the *cell_mapping*.

        Returns:
            [
                {
                    "site_iid": "…",
                    "latitude": 49.248,
                    "longitude": -2.231,
                    "technology": ["LTE"],
                    "cells": [
                        {"cell_iid": "…", "azimuth": 120, "band": "700",
                         "pci": 280, "technology": "LTE", "selected": True}
                    ]
                }, …
            ]
        """
        site_prev = location_mapping["site_preview"]
        cell_prev = cell_mapping["cell_preview"]

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
    def _resolve_technology(session: ACSSSession) -> str:
        """Derive the radio technology (``"LTE"`` or ``"NR"``) from the
        polygon's ``arrayType`` stored in setup_state. Falls back to ``"LTE"``."""
        polygon = (session.setup_state or {}).get("polygon") or {}
        array_type = polygon.get("arrayType", "LTE_Best_RSRP")
        return ArrayTypeMapper.to_technology(array_type)

    @staticmethod
    async def build_all_candidates_and_save_to_setup_state(
        db: AsyncSession,
        session: ACSSSession,
        gdl_path: str,
        redis_client: Redis,
    ) -> ACSSSession:
        """Validate GDL columns, build site objects for ALL candidates, and
        persist them into ``session.setup_state["allCandidates"]``.

        This is called right after a successful GDL upload so the frontend can
        immediately preview candidate sites on the map.

        Raises HTTPException(400) when required columns are missing.
        """
        session_id = session.id
        tech = SetupService._resolve_technology(session)
        tech_cfg = get_tech_config(tech)

        # 1) Validate columns using technology-specific required columns
        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            f"Validating GDL columns for {tech}..."
        )
        validation = ExcelColumnValidator.validate_excel_columns(gdl_path, tech_cfg.columns_path)

        if not validation["valid"]:
            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"GDL validation failed: {validation['message']}"
            )
            raise HTTPException(status_code=400, detail=validation["message"])

        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            f"GDL validation passed — {validation['total_excel_columns']} columns present"
        )

        # 2) Load EDS mappings (site_preview + cell_preview sections) and build site objects
        with open(tech_cfg.location_eds_mapping_path, "r", encoding="utf-8") as f:
            location_mapping = json.load(f)
        with open(tech_cfg.cell_eds_mapping_path, "r", encoding="utf-8") as f:
            cell_mapping = json.load(f)

        df = await asyncio.to_thread(pd.read_excel, gdl_path)
        all_candidates = SetupService._build_site_objects_from_df(df, tech, location_mapping, cell_mapping)
        total_cells = sum(len(s.get("cells", [])) for s in all_candidates)

        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            f"Built {len(all_candidates)} candidate sites ({tech}) with {total_cells} cells from GDL"
        )

        # 3) Persist into setup_state
        setup_state = dict(session.setup_state or {})
        setup_state["allCandidates"] = all_candidates
        session.setup_state = setup_state
        flag_modified(session, "setup_state")
        await db.commit()
        await db.refresh(session)

        return session

    # ============ GDL DOWNLOAD (SELECTED COLUMNS) ============

    # Columns shared across LTE and NR
    _COMMON_COLUMN_MAP = {
        "Property: ID":                                       "site_iid",
        "Cell: Identity":                                     "cell_iid",
        "Property: Location: Y Coordinate":                   "lat",
        "Property: Location: X Coordinate":                   "lon",
        "Property: Physical Antenna: Azimuth (deg)":          "azimuth",
        "Property: Logical Antenna: Electrical Tilt (deg)":   "electrical_tilt_deg",
        "Property: Physical Antenna: Height - Inventory (m)": "height_m",
    }

    # Columns that differ by technology
    _TECH_COLUMN_MAP = {
        "LTE": {
            "Cell: LTE: Max TX Power (dBm)":      "max_tx_dbm",
            "Cell: LTE: Ref Signal PPRE (dBm)":   "ppre_dbm",
            "Cell: LTE: PCI ID":                  "pci",
            "Cell: LTE: TAC":                     "tac",
            "Cell: LTE: First assigned RSI":      "rsi",
            "Cell: LTE: Assigned Carrier":        "band",
        },
        "NR": {
            "Cell: NR: Max TX Power (dBm)":       "max_tx_dbm",
            "Cell: NR: Ref Signal PPRE (dBm)":    "ppre_dbm",
            "Cell: NR: PCI ID":                   "pci",
            "Cell: NR: TAC":                      "tac",
            "Cell: NR: First assigned RSI":       "rsi",
            "Cell: NR: Assigned Carrier":         "band",
        },
    }

    @staticmethod
    async def get_gdl_for_download(
        db: AsyncSession,
        session_id: UUID,
    ) -> Dict:
        """Read the stored GDL file and return selected columns as JSON rows.

        Returns ``{"columns": [...], "rows": [[...], ...]}`` with only the
        columns the frontend needs for the GDL CSV download.
        """
        session = await SetupService._get_session(db, session_id)
        setup_state = session.setup_state or {}

        file_path = (setup_state.get("loadCandidateGdl") or {}).get("filePath")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="GDL file not found")

        tech = SetupService._resolve_technology(session)

        # Build the full column mapping for this technology
        col_map = {**SetupService._COMMON_COLUMN_MAP, **SetupService._TECH_COLUMN_MAP.get(tech, {})}

        # Read file
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            df = await asyncio.to_thread(pd.read_csv, file_path)
        else:
            df = await asyncio.to_thread(pd.read_excel, file_path)

        # Keep only columns that exist in the file
        present = {src: dst for src, dst in col_map.items() if src in df.columns}
        if not present:
            raise HTTPException(
                status_code=400,
                detail="GDL file does not contain any of the expected columns",
            )

        df_out = df[list(present.keys())].rename(columns=present)
        df_out = df_out.fillna("")

        # Enrich with population_weighted and covers_population from allCandidates
        all_candidates = setup_state.get("allCandidates") or []
        pw_lookup = {
            str(s["site_iid"]).strip(): s.get("population_weighted", False)
            for s in all_candidates
        }
        pop_weight_lookup = {
            str(s["site_iid"]).strip(): s.get("covers_population", "")
            for s in all_candidates
        }
        if "site_iid" in df_out.columns:
            df_out["population_weighted"] = df_out["site_iid"].map(
                lambda sid: str(pw_lookup.get(str(sid).strip(), False)).upper()
            )
            df_out["population_weight"] = df_out["site_iid"].map(
                lambda sid: pop_weight_lookup.get(str(sid).strip(), "")
            )
        else:
            df_out["population_weighted"] = "FALSE"
            df_out["population_weight"] = ""

        columns = list(df_out.columns)
        rows = df_out.values.tolist()

        return {"columns": columns, "rows": rows}
