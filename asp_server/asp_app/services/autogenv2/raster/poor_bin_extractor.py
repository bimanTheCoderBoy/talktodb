"""
Poor-bin extraction from a baseline RSRP BIL raster, clipped to polygon.

Input:
  bil_folder:      absolute path to directory with .bil + .hdr pair.
  polygon_coords:  [[lon, lat], ...] (EPSG:4326 / GeoJSON order).
  threshold_dbm:   pixels strictly below this AND finite are "poor".

Output:
  (lat, lon) or (lat, lon, rsrp_dbm) tuples — lat/lon swapped so
  sklearn DBSCAN(metric='haversine') gets the convention it expects.
"""
import os
from typing import List, Tuple

import numpy as np
import rasterio
from rasterio.mask import mask as rasterio_mask
from rasterio.warp import transform_geom, transform as warp_transform
from shapely.geometry import Polygon as ShapelyPolygon, mapping

WGS84 = "EPSG:4326"


def _resolve_bil(bil_folder: str) -> str:
    """Find the first .bil file with a matching .hdr in the folder."""
    if not os.path.isdir(bil_folder):
        raise FileNotFoundError(f"BIL folder does not exist: {bil_folder}")
    bil_files = [f for f in os.listdir(bil_folder) if f.lower().endswith('.bil')]
    for bil in bil_files:
        hdr = os.path.splitext(bil)[0] + '.hdr'
        if os.path.exists(os.path.join(bil_folder, hdr)):
            return os.path.join(bil_folder, bil)
    raise FileNotFoundError(f"No .bil file with matching .hdr found in folder: {bil_folder}")


def _read_nodata_from_hdr(bil_path: str) -> float:
    """Best-effort NODATA parser from ESRI .hdr sidecar."""
    hdr_path = os.path.splitext(bil_path)[0] + '.hdr'
    try:
        with open(hdr_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0].upper() in ('NODATA', 'NODATA_VALUE'):
                    return float(parts[1])
    except Exception:
        pass
    return -9999.0


def extract_poor_bins(
    bil_folder: str,
    polygon_coords: List[List[float]],
    threshold_dbm: float,
) -> List[Tuple[float, float]]:
    """Clip BIL to polygon, flag pixels < threshold, return (lat, lon) list."""
    triples = extract_poor_bins_with_rsrp(bil_folder, polygon_coords, threshold_dbm)
    return [(lat, lon) for (lat, lon, _) in triples]


def extract_poor_bins_with_rsrp(
    bil_folder: str,
    polygon_coords: List[List[float]],
    threshold_dbm: float,
) -> List[Tuple[float, float, float]]:
    """Clip BIL to polygon, flag pixels < threshold, return (lat, lon, rsrp_dbm).

    Synchronous — callers should wrap in ``asyncio.to_thread``.
    """
    if not polygon_coords or len(polygon_coords) < 3:
        return []

    bil_path = _resolve_bil(bil_folder)
    nodata = _read_nodata_from_hdr(bil_path)
    geom = ShapelyPolygon(polygon_coords)
    geom_geojson = mapping(geom)

    with rasterio.open(bil_path) as src:
        src_crs = src.crs
        if src_crs is not None and src_crs.to_string() != WGS84:
            geom_in_raster_crs = transform_geom(WGS84, src_crs, geom_geojson)
        else:
            geom_in_raster_crs = geom_geojson

        out_image, out_transform = rasterio_mask(
            src, [geom_in_raster_crs], crop=True, nodata=np.nan, filled=True
        )
        arr = out_image[0].astype(np.float32)
        arr = np.where(arr == nodata, np.nan, arr)
        poor_mask = (arr < threshold_dbm) & np.isfinite(arr)
        rows, cols = np.where(poor_mask)
        if rows.size == 0:
            return []
        rsrp_vals = arr[rows, cols].tolist()
        xs, ys = rasterio.transform.xy(out_transform, rows.tolist(), cols.tolist())
        if src_crs is not None and src_crs.to_string() != WGS84:
            lons, lats = warp_transform(src_crs, WGS84, list(xs), list(ys))
        else:
            lons, lats = list(xs), list(ys)
        return [
            (float(lat), float(lon), float(rsrp))
            for lat, lon, rsrp in zip(lats, lons, rsrp_vals)
        ]
