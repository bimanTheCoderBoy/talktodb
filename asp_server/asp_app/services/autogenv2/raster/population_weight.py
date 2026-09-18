"""
Population-density weighting for the auto-gen pipeline.

Loads a per-project population raster (WorldPop GeoTIFF or similar) and
samples each poor pixel to weight candidate placement by the people it
serves.  When no raster exists the caller falls through to uniform
weighting — fully optional.

Storage convention:
    <ACSSConfig.population_rasters_dir>/<project_name>.lower()/<file>
"""
import logging
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import rasterio
from rasterio.transform import rowcol
from rasterio.warp import transform as warp_transform

from asp_app.config.acss_config import get_acss_config

logger = logging.getLogger(__name__)

WGS84 = "EPSG:4326"

_cache: Dict[str, Dict] = {}


def _project_dir(project_name: str) -> str:
    cfg = get_acss_config()
    return os.path.normpath(
        os.path.join(cfg.population_rasters_dir, project_name.lower())
    )


def find_population_raster(project_name: str) -> Optional[str]:
    """Return the path of the first openable raster, or None."""
    base = _project_dir(project_name)
    if not os.path.isdir(base):
        return None
    for name in sorted(os.listdir(base)):
        if name.startswith("."):
            continue
        full = os.path.join(base, name)
        if not os.path.isfile(full):
            continue
        lower = name.lower()
        if lower.endswith(".tif") or lower.endswith(".tiff"):
            return full
        if lower.endswith(".bil"):
            hdr = os.path.splitext(full)[0] + ".hdr"
            if os.path.isfile(hdr):
                return full
    return None


def load_population_raster(path: str) -> Dict:
    """Read full single-band array into memory. Cached per path."""
    cached = _cache.get(path)
    if cached is not None:
        return cached
    with rasterio.open(path) as src:
        bundle = {
            "path": path,
            "array": src.read(1),
            "transform": src.transform,
            "crs": src.crs,
            "nodata": src.nodata if src.nodata is not None else -99999.0,
            "shape": src.shape,
            "bounds": src.bounds,
        }
    _cache[path] = bundle
    logger.info(
        "population_weight: loaded %s shape=%s crs=%s nodata=%s",
        os.path.basename(path), bundle["shape"], bundle["crs"], bundle["nodata"],
    )
    return bundle


def sample_weights_at_pixels(
    bundle: Dict,
    poor_pixels: List[Tuple[float, float]],
) -> List[float]:
    """For each (lat, lon) poor pixel return its population weight."""
    if not poor_pixels:
        return []

    arr = bundle["array"]
    transform = bundle["transform"]
    crs = bundle["crs"]
    nodata = bundle["nodata"]
    rows, cols = bundle["shape"]

    lons = [float(p[1]) for p in poor_pixels]
    lats = [float(p[0]) for p in poor_pixels]

    if crs is not None and crs.to_string() != WGS84:
        xs, ys = warp_transform(WGS84, crs, lons, lats)
    else:
        xs, ys = lons, lats

    rc_rows, rc_cols = rowcol(transform, xs, ys, op=int)
    if isinstance(rc_rows, int):
        rc_rows = [rc_rows]
        rc_cols = [rc_cols]

    weights: List[float] = []
    for r, c in zip(rc_rows, rc_cols):
        if r < 0 or r >= rows or c < 0 or c >= cols:
            weights.append(0.0)
            continue
        v = float(arr[r, c])
        if not np.isfinite(v) or v == nodata or v <= 0.0:
            weights.append(0.0)
            continue
        weights.append(v)
    return weights


def clear_cache() -> None:
    """Drop all loaded rasters from memory."""
    _cache.clear()
