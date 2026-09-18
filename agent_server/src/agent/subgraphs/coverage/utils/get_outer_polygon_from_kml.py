import geopandas as gpd
import pandas as pd
from pathlib import Path
from shapely.geometry import box
import errno
import os
import asyncio
import aiofiles.os

from agent.config.coverage_config import CoverageReportConfig


async def get_outer_polygon_from_kml(folder_path: str, method: str = "bounding_box") -> object:
    """
    Find all KML files in a folder (recursively), process them, and return
    a single polygon covering all geometries.
    
    Args:
        folder_path: Path to folder containing KML files
    
    Returns:
        Shapely Polygon covering all geometries
        
    Raises:
        FileNotFoundError: If folder doesn't exist or no KML files found
        ValueError: If GeoDataFrame is empty after processing
    """
    
    # Get KML folder root path from config
    config = CoverageReportConfig()
    kml_root = Path(config.kml_folder_root_path)
    folder = kml_root / folder_path
    
    # Validate folder exists (non-blocking)
    if not await aiofiles.os.path.isdir(folder):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), folder_path)
    
    # Find all KML files recursively (run blocking rglob in thread pool)
    kml_files = await asyncio.to_thread(lambda: list(folder.rglob("*.kml")))
    
    if not kml_files:
        raise FileNotFoundError(
            errno.ENOENT,
            os.strerror(errno.ENOENT),
            f"No KML files found in {folder_path}"
        )
    
    print(f"Found {len(kml_files)} KML file(s)")
    
    # Read and concatenate all GeoDataFrames (async wrapper for blocking gpd.read_file)
    async def _read_kml_file(kml_file):
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
    
    # Return coverage polygon based on method
    if method == "bounding_box":
        # Axis-aligned rectangle
        minx, miny, maxx, maxy = unified_geom.bounds
        result = box(minx, miny, maxx, maxy)
    #     print(f"Method: Bounding Box | Bounds: ({minx:.4f}, {miny:.4f}, {maxx:.4f}, {maxy:.4f})")
    
    # elif method == "concave_hull":
    #     # Concave hull (tighter than convex, allows indentations)
    #     result = unified_geom.concave_hull(ratio=0.0)
    #     print(f"Method: Concave Hull | Area: {result.area:.2f}")
    
    # else:  # convex_hull (default)
    #     # Convex hull (elastic band around all polygons)
    #     result = unified_geom.convex_hull
    #     print(f"Method: Convex Hull | Area: {result.area:.2f}")
    
    return  [  [xy[0], xy[1]] for xy in list(result.exterior.coords)]


