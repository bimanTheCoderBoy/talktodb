import asyncio
import logging
from typing import List, Optional, Dict, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from shapely.geometry import Polygon, Point
from api.db.models import UserProjectConfig
from security.encryption.iid_hash_utils import hash_iid, HASHING_ENABLED
from sqlalchemy import select
logger = logging.getLogger(__name__)


class CellsService:
    """Service for querying sites and cells."""

    CELLS_QUERY_LTE = """
            SELECT
            loc.iid        AS site_iid,
            loc.latitude,
            loc.longitude,
            loc.state,
            loc.address1,
            loc.town,
            c.cell_iid     AS cell_iid,
            NULLIF(c.technology_active::text, '') AS technology,
            phy.azimuth,
            c.lte_carrierparameters_physicalcellid AS pci,
            c.lte_carrierparameters_iid            AS band
        FROM cell_lte c

        LEFT JOIN (
            SELECT DISTINCT ON (iid)
                iid, latitude, longitude, state, address1, town
            FROM location
            ORDER BY iid, imported_at DESC
        ) loc
            ON loc.iid = c.location_iid

        LEFT JOIN (
            SELECT DISTINCT ON (cell_iid)
                cell_iid, azimuth
            FROM cell_physical_antenna
            WHERE imported_at = (SELECT MAX(imported_at) FROM cell_physical_antenna)
            ORDER BY cell_iid, imported_at DESC
        ) phy
            ON phy.cell_iid = c.cell_iid

        WHERE c.imported_at = (
            SELECT MAX(imported_at) FROM cell_lte
        )

    """
    CELLS_QUERY_NR = """

        SELECT
            loc.iid        AS site_iid,
            loc.latitude,
            loc.longitude,
            loc.state,
            loc.address1,
            loc.town,
            c.cell_iid     AS cell_iid,
            NULLIF(c.technology_active::text, '') AS technology,
            phy.azimuth,
            c.nrt_carrierparameters_physicalcellid AS pci,
            c.nrt_carrierparameters_iid            AS band
        FROM cell_nr c

        LEFT JOIN (
            SELECT DISTINCT ON (iid)
                iid, latitude, longitude, state, address1, town
            FROM location
            ORDER BY iid, imported_at DESC
        ) loc
            ON loc.iid = c.location_iid

        LEFT JOIN (
            SELECT DISTINCT ON (cell_iid)
                cell_iid, azimuth
            FROM cell_physical_antenna
            WHERE imported_at = (SELECT MAX(imported_at) FROM cell_physical_antenna)
            ORDER BY cell_iid, imported_at DESC
        ) phy
            ON phy.cell_iid = c.cell_iid

        WHERE c.imported_at = (
            SELECT MAX(imported_at) FROM cell_nr
        )
    """
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def _build_sites_cells_response(
        rows: list,
        cords: Optional[List[List[float]]],
        user_cells: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build the final response payload from SQLAlchemy row mappings.

        NOTE: This runs in a thread via asyncio.to_thread to avoid blocking
        the event loop when processing large result sets (Shapely + grouping).
        """
        boundary_polygon: Optional[Polygon] = None
        if cords:
            boundary_polygon = Polygon(cords)

        sites: Dict[str, Dict] = {}

        for row in rows:
            # row is a SQLAlchemy RowMapping (dict-like)
            site_iid = row.get("site_iid") or "unknown_site"
            lat = row.get("latitude")
            lon = row.get("longitude")

            # When polygon filtering, skip sites outside the boundary
            if boundary_polygon is not None:
                if lat is None or lon is None:
                    continue
                point = Point(lon, lat)
                if not (boundary_polygon.contains(point) or boundary_polygon.touches(point)):
                    continue

            if site_iid not in sites:
                sites[site_iid] = {
                    "site_iid": site_iid,
                    "latitude": lat,
                    "longitude": lon,
                    "state": row.get("state"),
                    "address1": row.get("address1"),
                    "town": row.get("town"),
                    "technology": set(),
                    "cells": [],
                }

            tech = row.get("technology")
            if tech:
                sites[site_iid]["technology"].add(tech)

            cell_obj: Dict[str, Any] = {
                "cell_iid": row.get("cell_iid"),
                "azimuth": row.get("azimuth"),
                "band": row.get("band"),
            }
            if row.get("pci") is not None:
                cell_obj["pci"] = row.get("pci")
            if tech:
                cell_obj["technology"] = tech
            if user_cells:
                cell_obj["selected"] = row.get("cell_iid") in user_cells

            sites[site_iid]["cells"].append(cell_obj)

        output = []
        for s in sites.values():
            output.append(
                {
                    "site_iid": s["site_iid"],
                    "latitude": s["latitude"],
                    "longitude": s["longitude"],
                    "state": s.get("state"),
                    "address1": s.get("address1"),
                    "town": s.get("town"),
                    "technology": sorted(list(s["technology"])),
                    "cells": s["cells"],
                }
            )

        return {"sites": output, "count": len(output)}

    @staticmethod
    async def get_sites_cells(
        db: AsyncSession,
        user_db: AsyncSession,
        cords: Optional[List[List[float]]] = None,
        auth_scope: bool = False,
        x_project_name: str = None,
        email: str = None,
    ) -> Dict[str, Any]:
        """
        Fetch sites/cells from the project database.

        **Two modes:**
        - *With* ``cords``: only polygon filtering is applied (text filters
          are ignored).  Sites whose lat/lon fall inside the polygon are returned.
        - *Without* ``cords``: the original behaviour — optional text filters
          (state, address1, town) are applied as SQL ``ILIKE`` conditions.

        Returns ``{"sites": [...], "count": int}``.
        """
        try:
            lte_sql = CellsService.CELLS_QUERY_LTE
            nr_sql = CellsService.CELLS_QUERY_NR
            params: Dict[str, str] = {}

            # Load user's saved config (cell_iids) for this project.
            user_cell_iids: Optional[List[str]] = None
            if email and x_project_name:
                cfg_result = await user_db.execute(
                    select(UserProjectConfig).where(
                        UserProjectConfig.email == email,
                        UserProjectConfig.project_name == x_project_name,
                    )
                )
                cfg_row = cfg_result.scalar_one_or_none()
                user_cell_iids = cfg_row.cell_iids if cfg_row else None
                
            # Hash user_cell_iids so they match hashed DB values
            hashed_user_cell_iids = None
            if user_cell_iids:
                hashed_user_cell_iids = [hash_iid(iid) for iid in user_cell_iids]

            # If auth_scope is enabled, restrict the SQL query to user's saved cell_iids.
            # (Otherwise we still pass user_cell_iids to the response builder to set `selected` flags.)
            if auth_scope:
                if hashed_user_cell_iids and len(hashed_user_cell_iids) > 0:
                    lte_sql += " AND c.cell_iid = ANY(:user_cell_iids)"
                    nr_sql += " AND c.cell_iid = ANY(:user_cell_iids)"
                    params["user_cell_iids"] = hashed_user_cell_iids
                else:
                    raise HTTPException(status_code=404, detail="No user project config found")

            sql = f"{lte_sql} UNION {nr_sql}"
            # ---- execute ----
            result = await db.execute(text(sql), params)
            rows = result.mappings().all()
            
            # Reverse-map hashed IIDs for frontend display
            if HASHING_ENABLED:
                hashes = set()
                for row in rows:
                    if row.get("site_iid"):
                        hashes.add(row["site_iid"])
                    if row.get("cell_iid"):
                        hashes.add(row["cell_iid"])
                if hashes:
                    map_result = await db.execute(
                        text("SELECT hash, original FROM iid_mapping WHERE hash = ANY(:hashes)"),
                        {"hashes": list(hashes)},
                    )
                    rmap = {r.hash: r.original for r in map_result}
                    if rmap:
                        rows = [
                            {**dict(row), "site_iid": rmap.get(row["site_iid"], row["site_iid"]),
                             "cell_iid": rmap.get(row["cell_iid"], row["cell_iid"])}
                            for row in rows
                        ]
                        # Also reverse-map hashed_user_cell_iids for `selected` flag comparison
                        if hashed_user_cell_iids:
                            hashed_user_cell_iids = [rmap.get(h, h) for h in hashed_user_cell_iids]

            # Shapely + grouping can be CPU-heavy; run in a thread to avoid blocking the event loop.
            return await asyncio.to_thread(CellsService._build_sites_cells_response, rows, cords, hashed_user_cell_iids)

        except HTTPException:
            raise
        except Exception as e:
            # Keep full traceback; the root cause is often inside a dependency
            # (e.g., DB driver / path resolution / runtime instrumentation).
            logger.exception("Error fetching sites and cells")
            raise HTTPException(
                status_code=500,
                detail=f"Could not fetch sites and cells from database: {str(e)}",
            )
