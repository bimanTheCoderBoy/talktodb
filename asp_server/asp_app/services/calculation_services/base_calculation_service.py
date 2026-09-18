import os
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
import numpy as np
import rasterio

logger = logging.getLogger(__name__)


def _read_nodata_from_hdr(bil_path: str) -> Optional[float]:
    """
    Read NODATA from Esri BIL .hdr (same base name as .bil). Example line: NODATA         -9999
    Returns the value as float, or None if not found.
    """
    base, _ = os.path.splitext(bil_path)
    hdr_path = base + ".hdr"
    if not os.path.isfile(hdr_path):
        return None
    try:
        with open(hdr_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.upper().startswith("NODATA"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return float(parts[1])
        return None
    except (OSError, ValueError):
        return None


def _to_unc_path(path: str) -> str:
    """
    Convert path to UNC format for Windows, or keep Linux paths as-is.
    - Windows UNC paths (\\host\path): keep as-is
    - Linux absolute paths (/path): keep as-is (for Docker/production)
    - Windows relative paths: convert to UNC format (for dev)
    """
    if not path or not path.strip():
        return path
    normalized = path.strip().replace("\\", "/").strip("/")
    if not normalized:
        return path
    parts = [p for p in normalized.split("/") if p]
    if not parts:
        return path
    if os.name == "nt":
        return "\\\\" + "\\".join(parts)
    return "/" + "/".join(parts)


# ================================
# Service Class
# ================================

class RasterBestValueService:
    # ---------------------------------------------------------------
    # In-process raster cache (per worker process).
    #
    # Stage-4 (Calculation) iterates C(N, K) combinations and each one
    # used to re-read the same K+1 BILs from a UNC share at ~12s/file.
    # That made N=10 / K=2 take ~37 minutes — almost 100% I/O wasted on
    # repeats. The cache lets each unique BIL be read exactly once per
    # session.
    #
    # Lifecycle: callers (CandidateEvaluationService) call clear_cache()
    # at the start AND end of the calculation step so it never leaks
    # across sessions. Within a single calculation step every cache hit
    # is consistent because the underlying BIL files are immutable for
    # the duration of the step (coverage simulation has finished and
    # nothing rewrites them until the next session's "Run Coverage for
    # Candidates" step).
    #
    # Memory: float16 raster of typical shape (20, 36) ≈ 1.4 KB. Even
    # 1000 cached BILs ≈ 1.4 MB — negligible.
    #
    # Concurrency: Celery workers run with --concurrency=2 in prefork
    # mode → each task gets its own subprocess and its own class dict.
    # If we ever switch to thread-based concurrency this cache would
    # need a per-call dict instead.
    # ---------------------------------------------------------------
    _array_cache: Dict[str, np.ndarray] = {}
    _meta_cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def clear_cache(cls) -> None:
        """Drop all cached arrays and metadata. Idempotent."""
        n_arr = len(cls._array_cache)
        n_meta = len(cls._meta_cache)
        cls._array_cache.clear()
        cls._meta_cache.clear()
        if n_arr or n_meta:
            logger.info("RasterBestValueService: cache cleared (%d arrays, %d metas)", n_arr, n_meta)

    async def prewarm_cache(self, folder_paths: List[str]) -> None:
        """Pre-load every unique BIL into the cache concurrently.

        Best-effort: any per-path failure (missing folder, bad header,
        unreadable BIL) is logged but does not raise. The downstream
        per-combination loop will still fail that one combination
        gracefully via its existing try/except — same behaviour as
        today, just without the wasted re-reads on every other combo.

        Concurrency is bounded by an asyncio semaphore (default 4) so
        we don't overwhelm the SMB server with simultaneous opens.
        """
        if not folder_paths:
            return

        # Resolve folder → .bil paths up front. If the resolver itself
        # fails (e.g. one folder is missing), fall back to per-combination
        # reads — they will hit the same error individually and skip
        # those combinations cleanly.
        try:
            bil_paths = await self._resolve_paths(folder_paths)
        except Exception as e:
            logger.warning(
                "prewarm_cache: path resolution failed (%s); falling back to per-combination reads",
                e,
            )
            return

        sem = asyncio.Semaphore(4)

        async def read_one(p: str) -> None:
            async with sem:
                try:
                    t0 = time.perf_counter()
                    # Single call — _read_array now populates _meta_cache as
                    # a side-effect from the same rasterio.open(). Avoids
                    # the second SMB handshake we were paying before.
                    arr = await self._read_array(p)
                    meta = self._meta_cache.get(p, {})
                    elapsed = time.perf_counter() - t0
                    # Bytes covers float16 only — actual UNC traffic may be
                    # larger if the source raster is wider dtype, but this
                    # gives a useful order-of-magnitude for cache sizing.
                    size_mb = (arr.nbytes / (1024 * 1024)) if arr is not None else 0.0
                    logger.info(
                        "prewarm_cache: BIL '%s' read in %.2fs (shape=%s, %.2f MB, n_valid=%d)",
                        os.path.basename(p), elapsed,
                        meta.get("shape"),
                        size_mb,
                        int(np.isfinite(arr).sum()) if arr is not None else 0,
                    )
                except Exception as e:
                    logger.warning("prewarm_cache: failed to read %s: %s", p, e)

        t_total = time.perf_counter()
        await asyncio.gather(*(read_one(p) for p in bil_paths))
        cached = sum(1 for p in bil_paths if p in self._array_cache)
        # Total cache footprint — useful when BILs are larger than the
        # tiny (20, 36) sample the original comment was based on. If this
        # ever climbs into hundreds of MB we should add an LRU eviction
        # policy or move to local-SSD staging.
        total_bytes = sum(
            arr.nbytes for arr in self._array_cache.values() if arr is not None
        )
        total_mb = total_bytes / (1024 * 1024)
        logger.info(
            "prewarm_cache: cached %d/%d BILs in %.2fs (sem=4, %.2f MB total in cache)",
            cached, len(bil_paths), time.perf_counter() - t_total, total_mb,
        )
        if total_mb > 512:
            logger.warning(
                "prewarm_cache: cache footprint %.0f MB exceeds 512 MB — "
                "consider lowering N or moving BILs to local SSD",
                total_mb,
            )

    async def get_best_data(
        self,
        type: str,
        paths: List[str]
    ) -> np.ndarray:
        """
        type: 'min' or 'max'
        paths: list of folder paths (directories). Each folder is searched for the first .bil with matching .hdr.
        Single path returns that raster as-is. Paths are converted to UNC if not already.
        """
        self._validate_type(type)
        if not paths:
            raise ValueError("At least one path required")
        if len(paths) == 1:
            return await self.read_single_array(paths[0])

        bil_paths = await self._resolve_paths(paths)
        logger.info("get_best_data: resolved %d BIL path(s): %s", len(bil_paths), bil_paths)

        t0 = time.perf_counter()
        # Open first raster as reference
        ref_meta = await self._read_meta(bil_paths[0])
        logger.info("get_best_data: ref shape=%s, bounds=%s", ref_meta["shape"], ref_meta["bounds"])

        # Load rasters — time is disk/network I/O (UNC path), not array size; shape (20,36) still ~10–15s per file
        arrays = []
        total_io_time = 0.0
        for idx, p in enumerate(bil_paths):
            t_bil = time.perf_counter()
            meta = await self._read_meta(p)
            self._validate_meta(ref_meta, meta, p)
            arr = await self._read_array(p)
            bil_elapsed = time.perf_counter() - t_bil
            total_io_time += bil_elapsed
            bil_name = os.path.basename(p)
            logger.info("get_best_data: BIL [%d/%d] '%s' read in %.2fs (shape=%s, n_valid=%d)",
                        idx + 1, len(bil_paths), bil_name, bil_elapsed,
                        arr.shape, int(np.isfinite(arr).sum()))
            arrays.append(arr)

        logger.info("get_best_data: total I/O time for %d BILs = %.2fs", len(bil_paths), total_io_time)

        # Compute best values (float32 reduce, cast to float16)
        t_compute = time.perf_counter()
        result = self._compute(arrays, type)
        compute_elapsed = time.perf_counter() - t_compute
        logger.info("get_best_data: compute (%s) took %.4fs", type, compute_elapsed)

        elapsed = time.perf_counter() - t0
        logger.info("get_best_data: result shape=%s, dtype=%s, min=%s, max=%s, n_valid=%s (total %.2fs = I/O %.2fs + compute %.4fs)",
                    result.shape, result.dtype,
                    float(np.nanmin(result)) if result.size else None,
                    float(np.nanmax(result)) if result.size else None,
                    int(np.isfinite(result).sum()),
                    elapsed, total_io_time, compute_elapsed)
        return result

    async def read_single_array(self, base_path: str) -> np.ndarray:
        """
        Read a single BIL raster from a folder. The folder is searched for the first .bil with matching .hdr.
        base_path: folder path (converted to UNC if not already). Used for baseline raster in goal calculations.
        """
        bil_paths = await self._resolve_paths([base_path])
        logger.info("read_single_array: baseline_path=%s, bil_found=%s", base_path, bil_paths[0] if bil_paths else None)
        t0 = time.perf_counter()
        arr = await self._read_array(bil_paths[0])
        elapsed = time.perf_counter() - t0
        logger.info("read_single_array: array shape=%s, dtype=%s, min=%s, max=%s, n_valid=%s (read %.2fs)",
                    arr.shape, arr.dtype,
                    float(np.nanmin(arr)) if arr.size else None,
                    float(np.nanmax(arr)) if arr.size else None,
                    int(np.isfinite(arr).sum()), elapsed)
        return arr


    # ================================
    # Validation
    # ================================

    def _validate_type(self, type):
        if type not in ("min", "max"):
            raise ValueError("type must be 'min' or 'max'")

    async def _resolve_paths(self, paths: List[str]) -> List[str]:
        """Resolve folder paths to .bil file paths (first .bil + .hdr per folder). Runs in thread pool to avoid blocking."""
        return await asyncio.to_thread(self._resolve_paths_sync, paths)

    def _resolve_paths_sync(self, paths: List[str]) -> List[str]:
        if len(paths) < 1:
            raise ValueError("At least one path required")

        bils = []
        for p in paths:
            folder = _to_unc_path(p)
            if not os.path.isdir(folder):
                raise FileNotFoundError(f"Path is not a directory or does not exist: {folder}")

            # Search folder for first .bil and require matching .hdr
            bil_path = None
            for name in sorted(os.listdir(folder)):
                if name.lower().endswith(".bil"):
                    base = os.path.splitext(name)[0]
                    cand_bil = os.path.join(folder, name)
                    cand_hdr = os.path.join(folder, base + ".hdr")
                    if os.path.isfile(cand_bil) and os.path.isfile(cand_hdr):
                        bil_path = cand_bil
                        break
            if bil_path is None:
                logger.warning("_resolve_paths_sync: no .bil+.hdr in folder: %s", folder)
                raise FileNotFoundError(f"No .bil file with matching .hdr found in folder: {folder}")
            logger.debug("_resolve_paths_sync: folder=%s -> bil=%s", folder, bil_path)
            bils.append(bil_path)
        return bils


    # ================================
    # Raster IO (async)
    # ================================

    async def _read_meta(self, path):
        # Cache-aware. Cache lifecycle is managed by callers via
        # clear_cache() / prewarm_cache(); see class docstring.
        cached = self._meta_cache.get(path)
        if cached is not None:
            return cached
        meta = await asyncio.to_thread(self._read_meta_sync, path)
        self._meta_cache[path] = meta
        return meta

    def _read_meta_sync(self, path):
        with rasterio.open(path) as src:
            return {
                "shape": src.shape,
                "bounds": src.bounds,
                "transform": src.transform,
                "crs": src.crs
            }

    async def _read_array(self, path):
        # Cache-aware. ~25-50s SMB read on miss; ~0ms on hit. With cache
        # filled by prewarm_cache(), all per-combination calls hit the
        # cache and the calculation step is bound by compute, not I/O.
        cached = self._array_cache.get(path)
        if cached is not None:
            return cached
        # Open once and populate BOTH caches — saves a redundant SMB
        # handshake when callers later ask for meta on the same path
        # (and the prewarm path uses this single call to fill both).
        arr, meta = await asyncio.to_thread(self._read_array_and_meta_sync, path)
        self._array_cache[path] = arr
        self._meta_cache[path] = meta
        return arr

    def _read_array_and_meta_sync(self, path):
        """One rasterio.open() returns both array and metadata. Used by
        the cache-aware path to coalesce two SMB handshakes into one
        (each handshake on this UNC share is ~25s, so this halves the
        prewarm wall time)."""
        nodata = _read_nodata_from_hdr(path)
        with rasterio.open(path) as src:
            meta = {
                "shape": src.shape,
                "bounds": src.bounds,
                "transform": src.transform,
                "crs": src.crs,
            }
            arr = src.read(1).astype(np.float16)
            if nodata is not None:
                arr = np.where(arr == nodata, np.nan, arr)
            elif getattr(src, "nodata", None) is not None:
                arr = np.where(arr == src.nodata, np.nan, arr)
            return arr, meta

    def _read_array_sync(self, path):
        # NODATA from .hdr (e.g. NODATA -9999); no RSRP bounds — only mask exact nodata value
        nodata = _read_nodata_from_hdr(path)
        with rasterio.open(path) as src:
            arr = src.read(1).astype(np.float16)  # Keep float16 for storage efficiency
            if nodata is not None:
                arr = np.where(arr == nodata, np.nan, arr)
            elif getattr(src, "nodata", None) is not None:
                arr = np.where(arr == src.nodata, np.nan, arr)
            return arr


    # ================================
    # Metadata Comparison
    # ================================

    def _validate_meta(self, ref, cur, path):
        if ref["shape"] != cur["shape"]:
            raise ValueError(f"Shape mismatch: {path}")

        if ref["bounds"] != cur["bounds"]:
            raise ValueError(f"Bounds mismatch: {path}")

        if ref["transform"] != cur["transform"]:
            raise ValueError(f"Transform mismatch: {path}")

        if ref["crs"] != cur["crs"]:
            raise ValueError(f"CRS mismatch: {path}")


    # ================================
    # Compute
    # ================================

    def _compute(self, arrays, type):
        # Use float32 and NaN-ignoring min/max so "best" = best of valid values only (no NaN propagation).
        # Otherwise max(baseline, cand) with one NaN gives NaN → avg_best over wrong subset → negative improvement.
        arrays_f32 = [a.astype(np.float32) for a in arrays]
        stack = np.stack(arrays_f32, axis=-1)
        if type == "min":
            result = np.nanmin(stack, axis=-1)
        else:
            result = np.nanmax(stack, axis=-1)
        # Where all rasters had NaN, result is NaN; keep it so downstream can ignore
        return result.astype(np.float16)  # Return float16 for storage efficiency
