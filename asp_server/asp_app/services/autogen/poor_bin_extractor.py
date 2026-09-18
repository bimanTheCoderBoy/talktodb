"""
Poor-bin extraction from a baseline RSRP BIL raster, clipped to polygon.

Input contract (callers in 02-05 and 02-07):
- bil_folder: str absolute path to a directory containing exactly one .bil + .hdr pair.
  Resolved using the same convention RasterBestValueService._resolve_paths_sync uses
  in services/calculation_services/base_calculation_service.py.
- polygon_coords: list[list[float]] in [[lon, lat], ...] order (matches
  setup_state["polygon"]["coords"] format per ACSSContext.jsx:39 and
  PolygonDrawControl.jsx:134).
- threshold_dbm: float, e.g. -110.0. Pixels strictly less than this AND finite
  are flagged as poor.

Output: list[tuple[float, float]] in (lat, lon) order — note the swap so
sklearn DBSCAN(metric='haversine') gets the convention it expects (radians of [lat, lon]).

Coordinate convention table:
  polygon_coords  → [[lon, lat], ...]   (EPSG:4326, GeoJSON/frontend convention)
  shapely.Polygon → (lon, lat) tuples   (shapely expects same order as polygon_coords)
  rasterio.mask   → clips in raster CRS (lon/lat WGS84)
  rasterio.transform.xy → returns (xs, ys) = (lons, lats) on WGS84 raster
  Output          → (lat, lon)          (sklearn haversine expects [lat, lon] radians)
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
    """Find the first .bil file with a matching .hdr in the folder.

    Mirrors the lookup logic in RasterBestValueService._resolve_paths_sync in
    services/calculation_services/base_calculation_service.py. Intentionally
    reimplemented here (not imported) to avoid pulling in numba/heavy
    initialization from that module.
    """
    if not os.path.isdir(bil_folder):
        raise FileNotFoundError(f"BIL folder does not exist: {bil_folder}")
    bil_files = [f for f in os.listdir(bil_folder) if f.lower().endswith('.bil')]
    for bil in bil_files:
        hdr = os.path.splitext(bil)[0] + '.hdr'
        if os.path.exists(os.path.join(bil_folder, hdr)):
            return os.path.join(bil_folder, bil)
    raise FileNotFoundError(f"No .bil file with matching .hdr found in folder: {bil_folder}")


def _read_nodata_from_hdr(bil_path: str) -> float:
    """Best-effort NODATA parser from ESRI .hdr sidecar.

    Mirrors the implementation in base_calculation_service._read_nodata_from_hdr
    but returns -9999.0 as default (vs None) so the caller can safely compare
    arr == nodata without a None-check.
    """
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
    """Clip BIL to polygon, flag pixels < threshold, return (lat, lon) list.

    Backwards-compatible wrapper around :func:`extract_poor_bins_with_rsrp`
    that discards the RSRP value. New callers that want gap-severity
    weighting should call the ``_with_rsrp`` variant directly.
    """
    triples = extract_poor_bins_with_rsrp(bil_folder, polygon_coords, threshold_dbm)
    return [(lat, lon) for (lat, lon, _) in triples]


def extract_poor_bins_with_rsrp(
    bil_folder: str,
    polygon_coords: List[List[float]],
    threshold_dbm: float,
) -> List[Tuple[float, float, float]]:
    """Clip BIL to polygon, flag pixels < threshold, return (lat, lon, rsrp_dbm).

    Carrying the per-pixel RSRP lets downstream auto-gen build a
    **gap-severity** weight (``threshold - rsrp``) for every poor pixel —
    deeper gaps drag azimuth/tilt toward them. Without RSRP every poor
    pixel weighed equally and the picker couldn't distinguish a
    -111 dBm "barely poor" pixel from a -125 dBm "deep hole".

    Callers should wrap this in ``asyncio.to_thread`` — this function is
    intentionally synchronous (rasterio I/O is blocking).

    Args:
        bil_folder: Absolute path to directory with .bil + .hdr file pair.
        polygon_coords: [[lon, lat], ...] polygon coordinates (GeoJSON order).
        threshold_dbm: RSRP threshold in dBm. Pixels strictly below this are poor.

    Returns:
        List of (lat, lon, rsrp_dbm) tuples for pixels below threshold
        inside the polygon. Empty list if no poor pixels found.
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
        # Sample RSRP values at the poor-pixel indices (parallel to rows/cols).
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
