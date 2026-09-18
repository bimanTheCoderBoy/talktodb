import asyncio
import errno
import os
from pathlib import Path
from typing import List
import aiofiles.os
import geopandas as gpd
import pandas as pd
from shapely.geometry import box
from asp_app.config.acss_config import get_kml_config


class ProjectService:
    @staticmethod
    async def get_outer_polygon_from_kml(project_name: str) -> List[List[float]]:
   
    # Get KML folder root path from config
        config = get_kml_config()
        kml_root = Path(config.kml_folder_root_path)
        folder = kml_root / project_name.lower()
        
        # Validate folder exists (non-blocking)
        if not await aiofiles.os.path.isdir(folder):
            print(f"Folder: {folder}")
            raise FileNotFoundError(
                errno.ENOENT, 
                os.strerror(errno.ENOENT), 
                f"Folder not found: {project_name}"
            )
        
        # Find all KML files recursively (run blocking rglob in thread pool)
        kml_files = await asyncio.to_thread(lambda: list(folder.rglob("*.kml")))
        
        if not kml_files:
            raise FileNotFoundError(
                errno.ENOENT,
                os.strerror(errno.ENOENT),
                f"No KML files found in {project_name}"
            )
        
        # print(f"Found {len(kml_files)} KML file(s)")
        
        # Read and concatenate all GeoDataFrames (async wrapper for blocking gpd.read_file)
        async def _read_kml_file(kml_file: Path):
            try:
                print(f"  Processing: {kml_file.name}")
                # Run blocking gpd.read_file in thread pool
                gdf = await asyncio.to_thread(gpd.read_file, kml_file, driver="KML")
                
                # Filter to polygons only (exclude points, lines)
                gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
                
                if not gdf.empty:
                    print(f"    -> {len(gdf)} polygon(s)")
                    return gdf
                return None
            except Exception as e:
                print(f"    -> Error: {e}")
                return None
        
        # Read all KML files in parallel
        gdf_tasks = [_read_kml_file(kml_file) for kml_file in kml_files]
        gdfs = await asyncio.gather(*gdf_tasks)
        
        # Filter out None results
        gdfs = [gdf for gdf in gdfs if gdf is not None]
        
        if not gdfs:
            raise ValueError("No valid polygons found in any KML files")
        
        # Concatenate all GeoDataFrames
        combined_gdf = pd.concat(gdfs, ignore_index=True)
        print(f"\nTotal polygons: {len(combined_gdf)}")
        
        # Union all geometries into a single geometry
        unified_geom = combined_gdf.unary_union
        
       
        minx, miny, maxx, maxy = unified_geom.bounds
        result = box(minx, miny, maxx, maxy)
        # print(f"Method: Bounding Box | Bounds: ({minx:.4f}, {miny:.4f}, {maxx:.4f}, {maxy:.4f})")
        
        # Convert to list of [lon, lat] coordinate pairs
        return [[xy[0], xy[1]] for xy in list(result.exterior.coords)]



