import asyncio
import errno
import logging
import os
from pathlib import Path
from typing import List
from api.config import KML_ROOT
import aiofiles.os
import geopandas as gpd
import pandas as pd
from shapely.geometry import box
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)




class ProjectService:
    """Service for project-level queries (no DB required)."""

    @staticmethod
    async def get_outer_polygon_from_kml(project_name: str) -> List[List[float]]:
        """
        Read all KML files for *project_name*, merge geometries, and return
        the bounding-box polygon as ``[[lon, lat], ...]``.

        Raises:
            FileNotFoundError: folder or KML files missing
            ValueError: no valid polygons in any KML file
        """
        kml_root = Path(KML_ROOT)
        folder = kml_root / project_name.lower()

        if not await aiofiles.os.path.isdir(folder):
            raise FileNotFoundError(
                errno.ENOENT,
                os.strerror(errno.ENOENT),
                f"Folder not found: {project_name}",
            )

        kml_files = await asyncio.to_thread(lambda: list(folder.rglob("*.kml")))

        if not kml_files:
            raise FileNotFoundError(
                errno.ENOENT,
                os.strerror(errno.ENOENT),
                f"No KML files found in {project_name}",
            )

        logger.info(f"Found {len(kml_files)} KML file(s) for project {project_name}")

        async def _read_kml_file(kml_file: Path):
            try:
                gdf = await asyncio.to_thread(gpd.read_file, kml_file, driver="KML")
                gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
                return gdf if not gdf.empty else None
            except Exception as e:
                logger.warning(f"Error reading {kml_file.name}: {e}")
                return None

        gdfs = await asyncio.gather(*[_read_kml_file(f) for f in kml_files])
        gdfs = [g for g in gdfs if g is not None]

        if not gdfs:
            raise ValueError("No valid polygons found in any KML files")

        combined_gdf = pd.concat(gdfs, ignore_index=True)
        unified_geom = combined_gdf.unary_union

        minx, miny, maxx, maxy = unified_geom.bounds
        result = box(minx, miny, maxx, maxy)

        return [[xy[0], xy[1]] for xy in list(result.exterior.coords)]
    

