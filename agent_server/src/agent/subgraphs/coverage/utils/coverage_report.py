"""
Async utility functions for coverage report generation.
"""

import os
import json
import numpy as np  # type: ignore
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from datetime import datetime
from typing import List, Dict, Any, Optional
import aiofiles
import asyncio

from shapely import Polygon
from agent.config.coverage_config import CoverageReportConfig
from langgraph.config import get_stream_writer
from langgraph.types import StreamWriter

MAX_BIL_FILE_SIZE_MB = 10


def categorize_rsrp(data_subset, pixel_area, total_polygon_area):
    """
    Vectorized NumPy RSRP categorization — no Numba dependency needed.
    Uses bulk boolean operations instead of per-element Python loops.
    """
    covered_areas = np.array([
        np.count_nonzero(data_subset > -45),
        np.count_nonzero((data_subset > -60) & (data_subset <= -45)),
        np.count_nonzero((data_subset > -80) & (data_subset <= -60)),
        np.count_nonzero((data_subset > -90) & (data_subset <= -80)),
        np.count_nonzero((data_subset > -100) & (data_subset <= -90)),
        np.count_nonzero((data_subset > -115) & (data_subset <= -100)),
        np.count_nonzero((data_subset > -120) & (data_subset <= -115)),
    ], dtype=np.float64) * pixel_area
    return np.minimum(covered_areas, total_polygon_area)


async def load_config(config_file: str) -> Dict[str, Any]:
    """
    Load configuration from JSON file.
    
    Args:
        config_file: Path to the configuration JSON file
        
    Returns:
        Dictionary containing the configuration
    """
    async with aiofiles.open(config_file, 'r', encoding='utf-8') as f:
        content = await f.read()
        config = json.loads(content)
    return config


async def read_raster(raster_file: str) -> rasterio.DatasetReader:
    """
    Read the raster file and return dataset (async wrapper for blocking rasterio.open).
    
    Args:
        raster_file: Path to the raster file
        
    Returns:
        Rasterio dataset object
        
    Raises:
        ValueError: If the raster file cannot be read
    """
    try:
        # Run blocking rasterio.open in thread pool to avoid blocking event loop
        dataset = await asyncio.to_thread(rasterio.open, raster_file)
        return dataset
    except Exception as e:
        raise ValueError(f"Error reading raster file {raster_file}: {e}")


async def read_kml(kml_file: str) -> gpd.GeoDataFrame:
    """
    Read the KML file and return a GeoDataFrame (async wrapper for blocking gpd.read_file).
    
    Args:
        kml_file: Path to the KML file
        
    Returns:
        GeoDataFrame containing the polygon geometries
        
    Raises:
        ValueError: If the KML file cannot be read
    """
    try:
        # Run blocking gpd.read_file in thread pool to avoid blocking event loop
        gdf = await asyncio.to_thread(gpd.read_file, kml_file)
        return gdf
    except Exception as e:
        raise ValueError(f"Error reading KML file {kml_file}: {e}")


def calculate_areas_and_intersections(dataset: rasterio.DatasetReader, polygons_gdf: gpd.GeoDataFrame) -> List[Dict[str, Any]]:
    """
    Calculate areas and intersections for each polygon.
    
    Args:
        dataset: Rasterio dataset object
        polygons_gdf: GeoDataFrame containing polygon geometries
        
    Returns:
        List of dictionaries containing calculated results for each polygon and RSRP category
    """
    results = []
    pixel_area = dataset.res[0] * dataset.res[1] / 1_000_000  # Convert to SQKM

    for index, polygon in polygons_gdf.iterrows():
        if polygon.geometry.is_empty:
            print(f"Polygon {index + 1} is empty.")
            continue

        # Step 1: Mask the raster with the polygon's geometry to get the intersection
        geom = [polygon.geometry.__geo_interface__]
        try:
            out_image, out_transform = mask(dataset, geom, crop=True)
        except ValueError as e:
            print(f"Polygon {index + 1} does not overlap raster, skipping: {e}")
            continue

        # Step 2: Calculate total covered area inside the polygon
        out_image = out_image[0]  # Get the first band (RSRP values)
        out_image = out_image[out_image > dataset.nodata]  # Remove no-data values

        # Calculate total covered area in the polygon (in square kilometers)
        covered_area_total = np.count_nonzero(out_image) * pixel_area

        # Convert polygon area to SQKM
        total_area = polygon.geometry.area / 1_000_000  # Convert to SQKM

        # Round values to 4 decimal places
        total_area = round(total_area, 4)
        covered_area_total = round(covered_area_total, 4)

        if covered_area_total > 0:
            # Step 3: Categorize RSRP values and calculate covered area for each RSRP category
            categorized_areas = categorize_rsrp(out_image, pixel_area, total_area)

            # Step 4: Add the results for each RSRP category
            for i, area in enumerate(categorized_areas):
                category = ['> -45 dBm', '-60 to -45 dBm', '-80 to -60 dBm', 
                            '-90 to -80 dBm', '-100 to -90 dBm', '-115 to -100 dBm', 
                            '-120 to -115 dBm'][i]

                # Ensure the category covered area doesn't exceed the polygon's area
                area = min(area, total_area)

                # Round the covered area for each category to 4 decimal places
                area = round(area, 4)

                # Calculate the percentage of covered area
                covered_area_percentage = (area / total_area) * 100 if total_area > 0 else 0

                # Round the percentage to 4 decimal places
                covered_area_percentage = round(covered_area_percentage, 4)

                results.append({
                    'Polygon Name': f'Polygon{index + 1}',  # Using index as Polygon Name
                    'Polygon Area [SQKM]': total_area,
                    'RSRP Category': category,
                    'COVERED AREA [SQKM]': area if area > 0 else '',  # Blank if no area
                    'COVERED AREA [%]': covered_area_percentage if area > 0 else 0  # Blank if no area
                })
        else:
            print(f"No covered area found for Polygon Index {index + 1}.")

    return results


async def find_bil_files(root_dir: str) -> List[str]:
    """
    Find all .bil files in subdirectories (async wrapper for os.walk).
    
    Args:
        root_dir: Root directory to search for .bil files
        
    Returns:
        List of paths to .bil files
    """
    print(f"Searching for BIL files in {root_dir}...")
    def _find_files():
        bil_files = []
        for subdir, _, files in os.walk(root_dir):
            for file in files:
                if file.lower().endswith('.bil'):
                    bil_files.append(os.path.join(subdir, file))
                    print(f"Found BIL file: {os.path.join(subdir, file)}")
        return bil_files
    
    # Run blocking os.walk in thread pool to avoid blocking event loop
    return await asyncio.to_thread(_find_files)


async def find_kml_files(kml_dir: str) -> List[str]:
    """
    Find all .kml files in a directory (async wrapper for os.walk).
    
    Args:
        kml_dir: Directory to search for .kml files
        
    Returns:
        List of paths to .kml files
    """
    def _find_files():
        kml_files = []
        for subdir, _, files in os.walk(kml_dir):
            for file in files:
                if file.lower().endswith('.kml'):
                    kml_files.append(os.path.join(subdir, file))
                    print(f"Found KML file: {os.path.join(subdir, file)}")
        return kml_files
    
    # Run blocking os.walk in thread pool to avoid blocking event loop
    return await asyncio.to_thread(_find_files)


async def save_results_to_csv(results_df: pd.DataFrame, bil_file: str, kml_file: Optional[str] = None, report_folder: str = "Report_Folder") -> str:
    """
    Save the results to a CSV file (async wrapper for blocking pandas.to_csv).
    
    Args:
        results_df: DataFrame containing the results
        bil_file: Path to the BIL file used
        kml_file: Path to the KML file used, if None, then user defined polygon is used
        report_folder: Folder where the CSV will be saved (default: "Report_Folder")
        
    Returns:
        Path to the created CSV file
    """
    # Check if the Report_Folder exists, if not, create it (async)
    folder_exists = await asyncio.to_thread(os.path.exists, report_folder)
    if not folder_exists:
        await asyncio.to_thread(os.makedirs, report_folder, exist_ok=True)
        print(f"Created new directory: {report_folder}")

    # Generate a timestamp for uniqueness
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Define the output file name with path in the Report_Folder
    bil_basename = os.path.splitext(os.path.basename(bil_file))[0]

    #Trick to get Array Type from the BIL file path
    bil_parent_folder = os.path.basename(os.path.dirname(bil_file))
    if kml_file is None:
        kml_basename = "user_defined_polygon.kml"
    else:
        kml_basename = os.path.splitext(os.path.basename(kml_file))[0]
    output_csv = os.path.join(report_folder, f"{bil_parent_folder}_{bil_basename}_{kml_basename}_{timestamp}.csv")
    
    # Save the DataFrame to CSV (run blocking to_csv in thread pool)
    await asyncio.to_thread(results_df.to_csv, output_csv, index=False)
    print(f"Results saved to {output_csv}")
    
    return output_csv


def process_single_combination_sync(bil_file_path: str, kml_file_path: Optional[str] = None, report_folder: str = "Report_Folder", is_user_defined_polygon: bool = False, boundaries: List[List[float]] = None) -> Optional[Dict[str, Any]]:
    """
    Process a single BIL file with a single KML file (Synchronous version).
    
    Args:
        bil_file_path: Path to the BIL file
        kml_file_path: Path to the KML file, if None, then user defined polygon is used     
        report_folder: Folder where the CSV will be saved (default: "Report_Folder")
        is_user_defined_polygon: Whether the polygon is user defined
        boundaries: The boundaries of the polygon
    Returns:
        Dict with "file" (csv path) and optionally "skipped"/"reason", or None if failed
    """
    stream_writer: StreamWriter = get_stream_writer()
    try:
        file_size_mb = os.path.getsize(bil_file_path) / (1024 * 1024)
        if file_size_mb > MAX_BIL_FILE_SIZE_MB:
            msg = f"Skipped {os.path.basename(bil_file_path)}: file size {file_size_mb:.1f}MB exceeds {MAX_BIL_FILE_SIZE_MB}MB limit"
            print(msg)
            stream_writer({"step": "4.2", "status": "skipped", "message": msg})
            return {"skipped": True, "reason": msg}

        print(f"Processing {kml_file_path} with {bil_file_path}...")

        # If the polygon is user defined, use the boundaries to create a GeoDataFrame
        if is_user_defined_polygon and boundaries is not None:
            stream_writer({"step": "4.2", "status": "in_progress", "message": "Creating GeoDataFrame for user defined polygon..."})
            polygons_gdf = gpd.GeoDataFrame(geometry=[Polygon(boundaries)], crs="EPSG:4326")
        else:
            # If the polygon is not user defined, read the KML file
            # Read the KML file (sync)
            stream_writer({"step": "4.2", "status": "in_progress", "message": "Reading KML file for user defined polygon..."})
            polygons_gdf = gpd.read_file(kml_file_path)
        
        if polygons_gdf is None or polygons_gdf.empty:
            stream_writer({"step": "4.2", "status": "in_progress", "message": f"Skipping {kml_file_path} due to loading failure or empty data."})
            print(f"Skipping {kml_file_path} due to loading failure or empty data.")
            return None
        stream_writer({"step": "4.2", "status": "in_progress", "message": "Reading raster file..."})
        # Read the raster file (sync)
        dataset = rasterio.open(bil_file_path)
        stream_writer({"step": "4.2", "status": "in_progress", "message": "Reading raster file..."})
        try:
            print(f"Existing CRS for polygons: {polygons_gdf.crs}")
            stream_writer({"step": "4.2", "status": "in_progress", "message": "Setting original CRS to EPSG:4326 for polygons..."})
            if polygons_gdf.crs is None:
                polygons_gdf.set_crs(epsg=4326, inplace=True)  # Set original CRS if not set
                print("Set original CRS to EPSG:4326 for polygons.")
            stream_writer({"step": "4.2", "status": "in_progress", "message": "Reprojecting polygons to match raster CRS..."})
            raster_crs = dataset.crs
            if raster_crs != polygons_gdf.crs:
                polygons_gdf = polygons_gdf.to_crs(raster_crs)
                print("Polygons reprojected to match raster CRS.")
            stream_writer({"step": "4.2", "status": "in_progress", "message": "Calculating areas and intersections..."})
            # Calculate areas and intersections (CPU bound, already sync)
            results = calculate_areas_and_intersections(dataset, polygons_gdf)
            stream_writer({"step": "4.2", "status": "in_progress", "message": "Creating DataFrame from results..."})
            # Create a DataFrame from the results
            results_df = pd.DataFrame(results)
            stream_writer({"step": "4.2", "status": "in_progress", "message": "Saving results to CSV..."})
            # Save to CSV (sync)
            os.makedirs(report_folder, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            bil_basename = os.path.splitext(os.path.basename(bil_file_path))[0]
            bil_parent_folder = os.path.basename(os.path.dirname(bil_file_path))
            
            if kml_file_path is None:
                kml_basename = "user_defined_polygon.kml"
            else:
                kml_basename = os.path.splitext(os.path.basename(kml_file_path))[0]
            
            output_csv = os.path.join(report_folder, f"{bil_parent_folder}_{bil_basename}_{kml_basename}_{timestamp}.csv")
            results_df.to_csv(output_csv, index=False)
            print(f"Results saved to {output_csv}")
            stream_writer({"step": "4.2", "status": "in_progress", "message": f"Results saved to {output_csv}"})
            return {"file": output_csv}

        finally:
            # Clean up
            dataset.close()
            stream_writer({"step": "4.2", "status": "in_progress", "message": "Dataset closed."})
    except Exception as e:
        print(f"Error processing {bil_file_path} with {kml_file_path}: {e}")
        stream_writer({"step": "4.2", "status": "in_progress", "message": f"Error processing {bil_file_path} with {kml_file_path}: {e}"})
        return None


async def process_all_files(bil_folder: str, report_folder: str, boundaries: List[List[float]], max_concurrent: int = 4) -> Dict[str, Any]:
    """
    Process all .bil files against a polygon boundary (user-drawn or project config).
    
    Args:
        bil_folder: Folder containing .bil files
        report_folder: Folder where CSV reports will be saved
        boundaries: The polygon coordinates to use for the report
        max_concurrent: Maximum number of concurrent tasks (default: 4)
        
    Returns:
        Dict with "created_files" (list of csv paths) and "skipped_reasons" (list of skip messages)
    """
    stream_writer: StreamWriter = get_stream_writer()

    stream_writer({"step": "4.1", "status": "started", "message": "Searching for BIL files..."})
    bil_files = await find_bil_files(bil_folder)
    stream_writer({"step": "4.1", "status": "in_progress", "message": f"Found {len(bil_files)} BIL file(s). Using polygon boundary."})
    if not bil_files:
        stream_writer({"step": "4.1", "status": "in_progress", "message": "No .bil files found."})
        print("No .bil files found.")
        return {"created_files": [], "skipped_reasons": []}

    # Step 4.2: Prepare processing tasks
    stream_writer({"step": "4.2", "status": "in_progress", "message": "Preparing file processing tasks..."})
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run_in_thread(*args):
        async with semaphore:
            return await asyncio.to_thread(process_single_combination_sync, *args)

    tasks = []
    for bil_file_path in bil_files:
        tasks.append(run_in_thread(bil_file_path, None, report_folder, True, boundaries))

    stream_writer({"step": "4.2", "status": "in_progress", "message": f"Prepared {len(tasks)} processing task(s)"})

    # Step 4.3: Execute all tasks concurrently
    stream_writer({"step": "4.3", "status": "in_progress", "message": f"Processing {len(tasks)} file combination(s)..."})
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    created_files = []
    skipped_reasons = []
    failed_count = 0
    for r in results:
        if isinstance(r, Exception):
            failed_count += 1
            print(f"Task failed with error: {r}")
        elif isinstance(r, dict):
            if r.get("skipped"):
                skipped_reasons.append(r["reason"])
            elif r.get("file"):
                created_files.append(r["file"])
        elif r is None:
            failed_count += 1

    summary_parts = [f"{len(created_files)} succeeded"]
    if skipped_reasons:
        summary_parts.append(f"{len(skipped_reasons)} skipped (large file)")
    if failed_count > 0:
        summary_parts.append(f"{failed_count} failed")
    stream_writer({"step": "4.3", "status": "in_progress", "message": f"Processing complete: {', '.join(summary_parts)}"})

    # Step 4.4: Cleanup old reports
    stream_writer({"step": "4.4", "status": "started", "message": "Cleaning up old reports..."})
    
    try:
        report_config = CoverageReportConfig()
        max_reports = report_config.maximum_report_folder_length
        
        # Get all CSV files in the report folder (async)
        async def _get_file_info(filename):
            file_path = os.path.join(report_folder, filename)
            mtime = await asyncio.to_thread(os.path.getmtime, file_path)
            return (file_path, mtime)
        
        file_list = await asyncio.to_thread(os.listdir, report_folder)
        csv_files = [f for f in file_list if f.lower().endswith('.csv')]
        
        # Parallelize mtime retrieval
        report_files = await asyncio.gather(*[_get_file_info(f) for f in csv_files])
        
        # Sort by modification time (newest first)
        report_files.sort(key=lambda x: x[1], reverse=True)
        
        # Delete older files beyond the maximum limit (async)
        if len(report_files) > max_reports:
            files_to_delete = report_files[max_reports:]
            
            async def _delete_file(file_path):
                try:
                    await asyncio.to_thread(os.remove, file_path)
                    print(f"Deleted old report: {file_path}")
                except Exception as e:
                    print(f"Failed to delete {file_path}: {e}")

            await asyncio.gather(*[_delete_file(f[0]) for f in files_to_delete], return_exceptions=True)
            
            
            stream_writer({"step": "4.4", "status": "in_progress", "message": f"Cleaned up {len(files_to_delete)} old report(s). Keeping latest {max_reports}."})
            print(f"Cleaned up {len(files_to_delete)} old report(s). Keeping latest {max_reports}.")
        else:
            
            stream_writer({"step": "4.4", "status": "in_progress", "message": "No cleanup needed, within report limit."})
    except Exception as e:
        stream_writer({"step": "4.4", "status": "in_progress", "message": f"Error during report cleanup: {e}"})
        print(f"Error during report cleanup: {e}")
    
    return {"created_files": created_files, "skipped_reasons": skipped_reasons}



