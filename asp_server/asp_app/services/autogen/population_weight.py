"""
Population-density-aware weighting for the ASP / ACSS auto-gen pipeline.

Optionally loads a per-project population raster (typically a WorldPop
"persons-per-pixel" GeoTIFF, but any rasterio-readable single-band float
is accepted) and exposes a sampler so the auto-gen pipeline can weight
each poor pixel by the people it actually serves. When no raster exists
for the project this module returns ``None`` at every entry point and
the caller falls through to uniform weighting — fully optional, no
breaking change.

Storage convention (lowercase project names match KML_files/ + oss-csv/):
    <ACSSConfig.population_rasters_dir>/<project_name>.lower()/<file>

The first openable file inside the per-project folder wins (.tif / .tiff
/ .bil with .hdr). Hidden files are skipped.

Why CRS-aware sampling?
    The Jersey reference raster is already EPSG:4326 (WGS84) — same as
    the polygon coords, so reprojection is a no-op there. Other rasters
    (GHSL is Mollweide / Web-Mercator, LandScan is Plate Carrée etc.)
    will need transform; we always reproject the *query points* to the
    raster's CRS rather than reprojecting the raster, which is cheaper
    and avoids resampling artefacts.
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

# Per-process cache: key = absolute raster path, value = loaded raster bundle.
# Cleared by the calculation-step cache reset; not load-bearing for population
# rasters (they're read once per session by definition) but cheap insurance.
_cache: Dict[str, Dict] = {}


def _project_dir(project_name: str) -> str:
    """Absolute path to the per-project population_rasters folder."""
    cfg = get_acss_config()
    return os.path.normpath(
        os.path.join(cfg.population_rasters_dir, project_name.lower())
    )


def find_population_raster(project_name: str) -> Optional[str]:
    """Return the absolute path of the first openable raster in the
    project's folder, or ``None`` if the directory is missing/empty.

    Looks for ``.tif`` / ``.tiff`` / ``.bil`` (with matching ``.hdr``)
    files. Hidden entries (``.gitkeep`` etc.) are skipped.
    """
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
    """Open the raster, read the full single-band array into memory, and
    return a bundle dict for the sampler. Cached per absolute path so a
    second call inside the same process is free.

    The whole raster is loaded — for typical country-scale WorldPop files
    (~100m, ≤ 100 MB float32) this is fine and avoids per-sample I/O.
    """
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
    """For each ``(lat, lon)`` poor pixel return its population weight
    (typically persons-per-pixel) from the raster, or ``0.0`` for points
    outside the raster bounds / on a nodata cell.

    Reprojects query coords from WGS84 to the raster's CRS first when the
    raster is not already in WGS84 (cheap on small point sets; the loader
    transforms once per session).
    """
    if not poor_pixels:
        return []

    arr = bundle["array"]
    transform = bundle["transform"]
    crs = bundle["crs"]
    nodata = bundle["nodata"]
    rows, cols = bundle["shape"]

    # poor_pixels is [(lat, lon), ...] in WGS84 (rest of the auto-gen
    # pipeline uses WGS84 throughout). rasterio.transform.rowcol expects
    # (xs, ys) where x = lon, y = lat in the raster's CRS.
    lons = [float(p[1]) for p in poor_pixels]
    lats = [float(p[0]) for p in poor_pixels]

    if crs is not None and crs.to_string() != WGS84:
        # Project the query points into the raster's CRS once.
        xs, ys = warp_transform(WGS84, crs, lons, lats)
    else:
        xs, ys = lons, lats

    # rasterio.transform.rowcol returns lists of ints when xs/ys are lists.
    rc_rows, rc_cols = rowcol(transform, xs, ys, op=int)
    # Guard scalar return when len(poor_pixels) == 1
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
    """Drop all loaded rasters from memory. Idempotent."""
    n = len(_cache)
    _cache.clear()
    if n:
        logger.info("population_weight: cache cleared (%d rasters)", n)


def get_population_status(project_name: str) -> Dict:
    """Lightweight probe used by the frontend to decide whether to show
    the "Prioritise by population density" checkbox as enabled or
    disabled-with-hint. Reads enough of the raster to report total
    population but does NOT cache (this is a UI probe, not a run-time
    pipeline call).
    """
    path = find_population_raster(project_name)
    if not path:
        return {"available": False}

    try:
        with rasterio.open(path) as src:
            arr = src.read(1)
            nodata = src.nodata if src.nodata is not None else -99999.0
            valid = arr[(arr != nodata) & np.isfinite(arr) & (arr > 0)]
            total = float(valid.sum()) if valid.size else 0.0
        return {
            "available": True,
            "filename": os.path.basename(path),
            "total_population": round(total, 1),
        }
    except Exception as e:
        logger.warning("get_population_status: failed to probe %s: %s", path, e)
        return {"available": False, "error": str(e)}
