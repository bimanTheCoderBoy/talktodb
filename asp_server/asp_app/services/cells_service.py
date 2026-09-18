import json
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from uuid import UUID
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from asp_app.services.redis_service import RedisService
from sqlalchemy import text
from fastapi import HTTPException
from shapely.geometry import Polygon, Point
from asp_app.utils.iid_hash_utils import HASHING_ENABLED, is_hashed_value, reverse_map_hashes_sql

logger = logging.getLogger(__name__)


class CellsService:
    """Service for handling cell-related operations."""
    # Raw SQL query to fetch all cells with location and antenna data
    CELLS_QUERY = """
        SELECT
            loc.iid AS site_iid,
            loc.latitude,
            loc.longitude,
            c.cell_iid,
            NULLIF(c.technology_active::text, '') AS technology,
            phy.azimuth,
            phy.antennadevice_iid AS antenna_device,
            phy.masterpattern1_iid AS master_pattern,
            phy.height AS antenna_height,
            phy.tilt AS mechanical_tilt,
            c.lte_carrierparameters_physicalcellid AS pci,
            c.lte_carrierparameters_iid AS band,
            c.lte_carrierparameters_maxtxpower AS max_tx_power
        FROM cell_lte c
        LEFT JOIN (
            SELECT DISTINCT ON (iid) *
            FROM location
            WHERE imported_at = (SELECT MAX(imported_at) FROM location)
        ) loc ON loc.iid = c.location_iid
        LEFT JOIN cell_physical_antenna phy
            ON phy.cell_iid = c.cell_iid
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
            AND phy.imported_at = (SELECT MAX(imported_at) FROM cell_physical_antenna)

        UNION ALL

        SELECT
            loc.iid AS site_iid,
            loc.latitude,
            loc.longitude,
            c.cell_iid,
            NULLIF(c.technology_active::text, '') AS technology,
            phy.azimuth,
            phy.antennadevice_iid AS antenna_device,
            phy.masterpattern1_iid AS master_pattern,
            phy.height AS antenna_height,
            phy.tilt AS mechanical_tilt,
            c.nrt_carrierparameters_physicalcellid AS pci,
            c.nrt_carrierparameters_iid AS band,
            c.nrt_carrierparameters_maxtxpower AS max_tx_power
        FROM cell_nr c
        LEFT JOIN (
            SELECT DISTINCT ON (iid) *
            FROM location
            WHERE imported_at = (SELECT MAX(imported_at) FROM location)
        ) loc ON loc.iid = c.location_iid
        LEFT JOIN cell_physical_antenna phy
            ON phy.cell_iid = c.cell_iid
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
            AND phy.imported_at = (SELECT MAX(imported_at) FROM cell_physical_antenna)
    """

    @staticmethod
    def _create_polygon_from_coords(boundary_coords: List[List[float]]) -> Polygon:
        """
        Create a Shapely Polygon from boundary coordinates.
        
        Args:
            boundary_coords: List of [lon, lat] coordinates
            
        Returns:
            Shapely Polygon object
        """
        # boundary_coords is [[lon, lat], [lon, lat], ...]
        return Polygon(boundary_coords)

    @staticmethod
    def _is_point_in_polygon(lon: float, lat: float, polygon: Polygon) -> bool:
        """
        Check if a point is within the polygon.
        
        Args:
            lon: Longitude
            lat: Latitude
            polygon: Shapely Polygon object
            
        Returns:
            True if point is within polygon, False otherwise
        """
        point = Point(lon, lat)
        return polygon.contains(point) or polygon.touches(point)

    @staticmethod
    async def get_cells_in_bounds(
        db: AsyncSession,
        boundary_coords: List[List[float]],
        redis_client: Redis,
        acss_session_id: UUID
    ) -> Dict[str, Any]:
        """
        Get all cells within the specified boundary polygon.
        
        Args:
            db: Database session (connected to project database)
            boundary_coords: List of [lon, lat] coordinates defining the boundary polygon
            
        Returns:
            Dictionary containing sites with their cells that fall within the boundary
        """
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"logs:{acss_session_id}")
        try:
            # Create polygon from boundary coordinates
            boundary_polygon = CellsService._create_polygon_from_coords(boundary_coords)
            
            # Execute raw SQL query
            result = await db.execute(text(CellsService.CELLS_QUERY))
            rows = result.mappings().all()

            # Reverse-map hashed IIDs for display
            rmap = {}
            if HASHING_ENABLED and rows:
                hashes = set()
                for r in rows:
                    for col in ("site_iid", "cell_iid"):
                        val = r.get(col)
                        if val and isinstance(val, str) and is_hashed_value(val):
                            hashes.add(val)
                if hashes:
                    rmap = await reverse_map_hashes_sql(db, hashes)

            # Group cells by site and filter by polygon
            sites: Dict[str, Dict] = {}

            for row in rows:
                site_iid = rmap.get(row.get("site_iid"), row.get("site_iid")) or "unknown_site"
                latitude = row.get("latitude")
                longitude = row.get("longitude")
                
                # Skip if no coordinates
                if latitude is None or longitude is None:
                    continue
                
                # Check if site location is within boundary polygon
                if not CellsService._is_point_in_polygon(longitude, latitude, boundary_polygon):
                    continue
                
                # Add site if not exists
                if site_iid not in sites:
                    sites[site_iid] = {
                        "site_iid": site_iid,
                        "latitude": latitude,
                        "longitude": longitude,
                        "technology": set(),
                        "cells": []
                    }
                
                # Add technology
                tech = row.get("technology")
                if tech:
                    sites[site_iid]["technology"].add(tech)
                
                # Construct cell object
                band_value = row.get("band")
                raw_cell = row.get("cell_iid")
                cell_obj = {
                    "cell_iid": rmap.get(raw_cell, raw_cell) if raw_cell else raw_cell,
                    "azimuth": row.get("azimuth"),
                    "band": str(band_value) if band_value is not None else None,
                    "pci": row.get("pci"),
                    "technology": tech,
                    "selected": True,
                    "antenna_device": row.get("antenna_device"),
                    "master_pattern": row.get("master_pattern"),
                    "antenna_height": row.get("antenna_height"),
                    "mechanical_tilt": row.get("mechanical_tilt"),
                    "max_tx_power": row.get("max_tx_power"),
                }
                
                sites[site_iid]["cells"].append(cell_obj)
            
            # Convert to list format and sort technologies
            sites_list = []
            total_cells = 0
            
            for site_data in sites.values():
                site_output = {
                    "site_iid": site_data["site_iid"],
                    "latitude": site_data["latitude"],
                    "longitude": site_data["longitude"],
                    "technology": sorted(list(site_data["technology"])),
                    "cells": site_data["cells"]
                }
                sites_list.append(site_output)
                total_cells += len(site_data["cells"])
            
            await RedisService.publish_log(redis_client, f"logs:{acss_session_id}", f"Cells in bounds fetched successfully returning {json.dumps(sites_list)} sites and {total_cells} cells")
            return {
                "sites": sites_list,
                "total_sites": len(sites_list),
                "total_cells": total_cells
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch cells in bounds: {str(e)}"
            )

    BASELINE_CELLS_LTE_QUERY = """
        SELECT
            loc.iid        AS site_iid,
            loc.latitude,
            loc.longitude,
            c.cell_iid,
            NULLIF(c.technology_active::text, '') AS technology,
            phy.azimuth,
            phy.antennadevice_iid  AS antenna_device,
            phy.masterpattern1_iid AS master_pattern,
            phy.height             AS antenna_height,
            phy.tilt               AS mechanical_tilt,
            c.lte_carrierparameters_physicalcellid AS pci,
            c.lte_carrierparameters_iid            AS band,
            c.lte_carrierparameters_maxtxpower     AS max_tx_power,
            c.lte_sumimotxelems   AS mimo_tx,
            c.lte_sumimorxelems   AS mimo_rx,
            c.lte_carrierparameters_autocalculatemethod AS auto_calc_method,
            la.primarymodel_modeltype_iid               AS primary_model,
            la.primarymodel_radiuskm                    AS primary_model_radius,
            mu.plmn_iid                                 AS plmn,
            c.lte_tac                                   AS tac,
            c.lte_carrierparameters_referencesignalppre AS ref_signal_ppre
        FROM cell_lte c
        JOIN (
            SELECT DISTINCT ON (iid) *
            FROM location
            WHERE imported_at = (SELECT MAX(imported_at) FROM location)
        ) loc ON loc.iid = c.location_iid
        LEFT JOIN cell_physical_antenna phy
            ON  phy.cell_iid = c.cell_iid
            AND phy.imported_at = (SELECT MAX(imported_at) FROM cell_physical_antenna)
        LEFT JOIN cell_logical_antenna la
            ON  la.cell_iid = c.cell_iid
            AND la.imported_at = (SELECT MAX(imported_at) FROM cell_logical_antenna)
        LEFT JOIN mu_lte mu
            ON  mu.iid = c.parent_iid
            AND mu.imported_at = (SELECT MAX(imported_at) FROM mu_lte)
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
          AND c.lte_carrierparameters_iid = :band
          AND ST_Within(
                loc.geom::geometry,
                ST_GeomFromText(:boundary_wkt, 4326)
              )
    """

    BASELINE_CELLS_NR_QUERY = """
        SELECT
            loc.iid        AS site_iid,
            loc.latitude,
            loc.longitude,
            c.cell_iid,
            NULLIF(c.technology_active::text, '') AS technology,
            phy.azimuth,
            phy.antennadevice_iid  AS antenna_device,
            phy.masterpattern1_iid AS master_pattern,
            phy.height             AS antenna_height,
            phy.tilt               AS mechanical_tilt,
            c.nrt_carrierparameters_physicalcellid AS pci,
            c.nrt_carrierparameters_iid            AS band,
            c.nrt_carrierparameters_maxtxpower     AS max_tx_power,
            c.nrt_sumimotxelems   AS mimo_tx,
            c.nrt_sumimorxelems   AS mimo_rx,
            c.nrt_carrierparameters_autocalculatemethod AS auto_calc_method,
            la.beamset_iid                                            AS beamset_iid,
            la.beamswitching_patternfrequency                         AS beam_frequency,
            la.beamswitching_sbactrlpatterns_ro_patterns_gain          AS beam_gain,
            la.beamswitching_sbactrlpatterns_ro_patterns_electricaltilt AS beam_etilt,
            la.beamswitching_sbactrlpatterns_ro_patterns_antennapatternangle AS beam_angle,
            la.primarymodel_modeltype_iid               AS primary_model,
            la.primarymodel_radiuskm                    AS primary_model_radius,
            mu.plmn_iid                                 AS plmn,
            c.nrt_tac                                   AS tac
        FROM cell_nr c
        JOIN (
            SELECT DISTINCT ON (iid) *
            FROM location
            WHERE imported_at = (SELECT MAX(imported_at) FROM location)
        ) loc ON loc.iid = c.location_iid
        LEFT JOIN cell_physical_antenna phy
            ON  phy.cell_iid = c.cell_iid
            AND phy.imported_at = (SELECT MAX(imported_at) FROM cell_physical_antenna)
        LEFT JOIN cell_logical_antenna la
            ON  la.cell_iid = c.cell_iid
            AND la.imported_at = (SELECT MAX(imported_at) FROM cell_logical_antenna)
        LEFT JOIN mu_nr mu
            ON  mu.iid = c.parent_iid
            AND mu.imported_at = (SELECT MAX(imported_at) FROM mu_nr)
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
          AND c.nrt_carrierparameters_iid = :band
          AND ST_Within(
                loc.geom::geometry,
                ST_GeomFromText(:boundary_wkt, 4326)
              )
    """

    @staticmethod
    def _coords_to_wkt(boundary_coords: List[List[float]]) -> str:
        """Convert [[lon, lat], ...] to a WKT POLYGON string."""
        coords = list(boundary_coords)
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        ring = ", ".join(f"{lon} {lat}" for lon, lat in coords)
        return f"POLYGON(({ring}))"

    @staticmethod
    async def get_baseline_cells_for_band(
        db: AsyncSession,
        boundary_coords: List[List[float]],
        band: str,
        technology: str,
    ) -> List[Dict[str, Any]]:
        """Fetch enriched baseline cells inside a boundary, filtered by band.

        All filtering (band + spatial) is done in SQL using the location.geom
        column. Returns a list of site dicts with full antenna data, ready for
        the autogenv2 pipeline.

        ``technology`` should be ``"NR"`` or ``"LTE"`` — used to pick the
        correct cell table.
        """
        boundary_wkt = CellsService._coords_to_wkt(boundary_coords)
        params = {"band": band, "boundary_wkt": boundary_wkt}

        query = (
            CellsService.BASELINE_CELLS_NR_QUERY
            if technology.upper() == "NR"
            else CellsService.BASELINE_CELLS_LTE_QUERY
        )

        result = await db.execute(text(query), params)
        rows = result.mappings().all()

        sites: Dict[str, Dict] = {}
        for row in rows:
            site_iid = row["site_iid"] or "unknown_site"
            if site_iid not in sites:
                sites[site_iid] = {
                    "site_iid": site_iid,
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "technology": set(),
                    "cells": [],
                }

            tech = row.get("technology")
            if tech:
                sites[site_iid]["technology"].add(tech)

            cell_obj = {
                "cell_iid": row["cell_iid"],
                "azimuth": row.get("azimuth"),
                "band": str(row["band"]) if row.get("band") is not None else None,
                "pci": row.get("pci"),
                "technology": tech,
                "selected": True,
                "antenna_device": row.get("antenna_device"),
                "master_pattern": row.get("master_pattern"),
                "antenna_height": row.get("antenna_height"),
                "mechanical_tilt": row.get("mechanical_tilt"),
                "max_tx_power": row.get("max_tx_power"),
                "mimo_tx": row.get("mimo_tx"),
                "mimo_rx": row.get("mimo_rx"),
                "auto_calc_method": row.get("auto_calc_method"),
                "primary_model": row.get("primary_model"),
                "primary_model_radius": row.get("primary_model_radius"),
                "plmn": row.get("plmn"),
                "tac": row.get("tac"),
            }
            if technology.upper() == "LTE":
                cell_obj["ref_signal_ppre"] = row.get("ref_signal_ppre")
            if technology.upper() == "NR":
                cell_obj["beamset_iid"] = row.get("beamset_iid")
                cell_obj["beam_frequency"] = row.get("beam_frequency")
                cell_obj["beam_gain"] = row.get("beam_gain")
                cell_obj["beam_etilt"] = row.get("beam_etilt")
                cell_obj["beam_angle"] = row.get("beam_angle")

            sites[site_iid]["cells"].append(cell_obj)

        sites_list = [
            {
                "site_iid": s["site_iid"],
                "latitude": s["latitude"],
                "longitude": s["longitude"],
                "technology": sorted(list(s["technology"])),
                "cells": s["cells"],
            }
            for s in sites.values()
        ]

        total_cells = sum(len(s["cells"]) for s in sites_list)
        logger.info(
            "get_baseline_cells_for_band(band=%s): %d sites, %d cells",
            band, len(sites_list), total_cells,
        )
        return sites_list

    # ── Lightweight PCI + RSI radius query (10km, tech-aware) ─────────

    NEARBY_PCI_RSI_LTE = """
        SELECT
            c.lte_carrierparameters_physicalcellid AS pci,
            c.lte_firstassignedrsi                 AS rsi,
            c.lte_carrierparameters_iid             AS band
        FROM cell_lte c
        JOIN (
            SELECT DISTINCT ON (iid) iid, geom
            FROM location
            WHERE imported_at = (SELECT MAX(imported_at) FROM location)
        ) loc ON loc.iid = c.location_iid
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
          AND ST_DWithin(
                loc.geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_m
              )
    """

    NEARBY_PCI_RSI_NR = """
        SELECT
            c.nrt_carrierparameters_physicalcellid       AS pci,
            c.nrt_carrierparameters_firstassignedrsi     AS rsi,
            c.nrt_carrierparameters_iid                  AS band
        FROM cell_nr c
        JOIN (
            SELECT DISTINCT ON (iid) iid, geom
            FROM location
            WHERE imported_at = (SELECT MAX(imported_at) FROM location)
        ) loc ON loc.iid = c.location_iid
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
          AND ST_DWithin(
                loc.geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_m
              )
    """

    @staticmethod
    async def get_nearby_pci_rsi(
        db: AsyncSession,
        lat: float,
        lon: float,
        radius_km: float,
        technology: str,
        selected_band: str = "",
    ) -> Tuple[Set[int], Set[int]]:
        """Fetch all used PCIs (cross-band) and used RSIs (same-band only).

        Uses ``ST_DWithin`` on the ``geom`` column for a true radius scan
        that is independent of the polygon boundary.

        PCI must be unique across all bands of the same technology.
        RSI only needs to be unique within the same band/carrier.

        Returns ``(used_pcis, used_rsis)``.
        """
        query = (
            CellsService.NEARBY_PCI_RSI_NR
            if technology.upper() == "NR"
            else CellsService.NEARBY_PCI_RSI_LTE
        )
        params = {"lat": lat, "lon": lon, "radius_m": radius_km * 1000}

        result = await db.execute(text(query), params)
        rows = result.all()

        used_pcis: Set[int] = set()
        used_rsis: Set[int] = set()
        for pci, rsi, row_band in rows:
            if pci is not None:
                try:
                    used_pcis.add(int(pci))
                except (TypeError, ValueError):
                    pass
            if rsi is not None and str(row_band or "") == selected_band:
                try:
                    used_rsis.add(int(rsi))
                except (TypeError, ValueError):
                    pass

        logger.info(
            "get_nearby_pci_rsi(%s, %.5f, %.5f, %.0fkm, band=%s): %d rows → "
            "%d unique PCIs, %d used RSIs (same-band)",
            technology, lat, lon, radius_km, selected_band, len(rows),
            len(used_pcis), len(used_rsis),
        )
        return used_pcis, used_rsis

    # ── Pattern lookup by closest eTilt (no radius limit) ─────────────

    PATTERN_BY_ETILT_LTE = """
        SELECT
            la.passive_antennapatterntype_iid AS logical_pattern,
            la.passive_electricaldowntilt_ro  AS electrical_tilt
        FROM cell_lte c
        JOIN (
            SELECT DISTINCT ON (iid) iid
            FROM location
            WHERE imported_at = (SELECT MAX(imported_at) FROM location)
        ) loc ON loc.iid = c.location_iid
        JOIN cell_physical_antenna phy
            ON  phy.cell_iid = c.cell_iid
            AND phy.imported_at = (SELECT MAX(imported_at) FROM cell_physical_antenna)
        JOIN cell_logical_antenna la
            ON  la.cell_iid = c.cell_iid
            AND la.imported_at = (SELECT MAX(imported_at) FROM cell_logical_antenna)
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
          AND c.lte_carrierparameters_iid = :band
          AND phy.antennadevice_iid = :antenna_device
          AND la.passive_antennapatterntype_iid IS NOT NULL
          AND la.passive_electricaldowntilt_ro IS NOT NULL
        ORDER BY ABS(la.passive_electricaldowntilt_ro - :target_etilt) ASC
        LIMIT 1
    """

    PATTERN_BY_ETILT_NR = """
        SELECT
            la.passive_antennapatterntype_iid AS logical_pattern,
            la.passive_electricaldowntilt_ro  AS electrical_tilt
        FROM cell_nr c
        JOIN (
            SELECT DISTINCT ON (iid) iid
            FROM location
            WHERE imported_at = (SELECT MAX(imported_at) FROM location)
        ) loc ON loc.iid = c.location_iid
        JOIN cell_physical_antenna phy
            ON  phy.cell_iid = c.cell_iid
            AND phy.imported_at = (SELECT MAX(imported_at) FROM cell_physical_antenna)
        JOIN cell_logical_antenna la
            ON  la.cell_iid = c.cell_iid
            AND la.imported_at = (SELECT MAX(imported_at) FROM cell_logical_antenna)
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
          AND c.nrt_carrierparameters_iid = :band
          AND phy.antennadevice_iid = :antenna_device
          AND la.passive_antennapatterntype_iid IS NOT NULL
          AND la.passive_electricaldowntilt_ro IS NOT NULL
        ORDER BY ABS(la.passive_electricaldowntilt_ro - :target_etilt) ASC
        LIMIT 1
    """

    @staticmethod
    async def get_pattern_by_etilt(
        db: AsyncSession,
        band: str,
        target_etilt: float,
        antenna_device: str,
        technology: str,
    ) -> Tuple[Optional[str], Optional[float]]:
        """Find the antenna pattern whose eTilt is closest to *target_etilt*
        on cells with the **same antenna device**.

        Searches the entire project (no radius/polygon limit) for cells on
        *band* with *antenna_device*, sorted by closest eTilt.

        Returns ``(logical_pattern, matched_etilt)`` or ``(None, None)``.
        """
        if not antenna_device:
            logger.info(
                "get_pattern_by_etilt(%s, band=%s, etilt=%.1f): "
                "no antenna_device → skip",
                technology, band, target_etilt,
            )
            return None, None

        query = (
            CellsService.PATTERN_BY_ETILT_NR
            if technology.upper() == "NR"
            else CellsService.PATTERN_BY_ETILT_LTE
        )
        result = await db.execute(
            text(query),
            {"band": band, "target_etilt": target_etilt,
             "antenna_device": antenna_device},
        )
        row = result.first()
        if row is None:
            logger.info(
                "get_pattern_by_etilt(%s, band=%s, device=%s, etilt=%.1f): "
                "no match",
                technology, band, antenna_device, target_etilt,
            )
            return None, None

        pattern, matched_etilt = row
        logger.info(
            "get_pattern_by_etilt(%s, band=%s, device=%s, etilt=%.1f): "
            "pattern=%s (matched_etilt=%.1f°)",
            technology, band, antenna_device, target_etilt,
            pattern, matched_etilt,
        )
        return pattern, float(matched_etilt)
