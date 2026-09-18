"""Numba JIT-compiled kernels for high-performance KPI computation.

These functions are compiled to machine code for fast pixel-level operations.
They operate on numpy arrays and return raw numeric results, which are then
converted to the KPI dictionaries by the caller (preserving the original
API contract).

Note: Numba is optional. If not installed, functions work as regular Python
(slower but functional). Install numba for 50-100x performance improvement.
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)

# Try to import numba; provide fallback if not available
try:
    from numba import njit, config
    NUMBA_AVAILABLE = True
    config.DISABLE_JIT = False
    logger.info("✓ Numba JIT compilation ENABLED - KPI computation will be 50-100x faster")
except ImportError:
    NUMBA_AVAILABLE = False
    logger.warning("⚠ Numba NOT installed - KPI computation will use pure Python (slower). Install numba for speedup.")
    # Provide a no-op decorator if numba not available
    def njit(*args, **kwargs):
        """No-op decorator when numba not installed."""
        def decorator(func):
            return func
        # Handle both @njit and @njit() syntax
        if len(args) > 0 and callable(args[0]):
            return args[0]
        return decorator


# =============================================================================
# Goal Type 1: Increase RSRP
# =============================================================================

@njit
def _compute_goal1_metrics(
    baseline: np.ndarray,
    best: np.ndarray,
    x_value: float,
    valid_min: float,
    valid_max: float,
) -> tuple:
    """
    JIT-compiled kernel for GoalType 1 KPI computation.
    
    Returns:
        (n_best_valid, n_overlap, n_new, n_improved, pct_improved,
         avg_baseline, avg_best, avg_abs_gain, avg_pct_gain, goal_satisfied)
    """
    # Convert to float64 for precision
    baseline_f64 = baseline.astype(np.float64)
    best_f64 = best.astype(np.float64)
    
    height, width = best_f64.shape
    n_best_valid = 0
    n_overlap = 0
    n_improved = 0
    
    # Arrays for aggregation
    sum_baseline = 0.0
    sum_best = 0.0
    sum_abs_gain = 0.0
    sum_pct_gain = 0.0
    
    # First pass: collect best-valid and overlap-valid pixels
    best_valid_pixels = np.zeros((height, width), dtype=np.bool_)
    overlap_valid_pixels = np.zeros((height, width), dtype=np.bool_)
    
    for i in range(height):
        for j in range(width):
            b_val = baseline_f64[i, j]
            c_val = best_f64[i, j]
            
            # Check best validity
            b_finite = not np.isnan(b_val) and not np.isinf(b_val)
            c_finite = not np.isnan(c_val) and not np.isinf(c_val)
            c_valid = c_finite and (c_val >= valid_min) and (c_val <= valid_max)
            
            if c_valid:
                best_valid_pixels[i, j] = True
                n_best_valid += 1
                
                # Check overlap validity
                b_valid = b_finite and (b_val >= valid_min) and (b_val <= valid_max)
                if b_valid:
                    overlap_valid_pixels[i, j] = True
                    n_overlap += 1
                    
                    # Accumulate overlap-valid stats
                    sum_baseline += b_val
                    sum_best += c_val
                    sum_abs_gain += (c_val - b_val)
                    
                    # Per-pixel % gain
                    abs_b = abs(b_val)
                    if abs_b > 0.0:
                        pct_gain = ((c_val - b_val) / abs_b) * 100.0
                    else:
                        pct_gain = 0.0
                    sum_pct_gain += pct_gain
                    
                    # Count improvements
                    if c_val > b_val:
                        n_improved += 1
    
    n_new = n_best_valid - n_overlap
    
    # Compute averages
    if n_overlap > 0:
        avg_baseline = sum_baseline / n_overlap
        avg_best = sum_best / n_overlap
        avg_abs_gain = sum_abs_gain / n_overlap
        avg_pct_gain = sum_pct_gain / n_overlap
        pct_improved = (n_improved / n_overlap) * 100.0
    else:
        avg_baseline = 0.0
        avg_best = 0.0
        avg_abs_gain = 0.0
        avg_pct_gain = 0.0
        pct_improved = 0.0
    
    # Check goal satisfaction
    goal_satisfied = avg_pct_gain >= x_value
    
    return (
        n_best_valid, n_overlap, n_new, n_improved, pct_improved,
        avg_baseline, avg_best, avg_abs_gain, avg_pct_gain, goal_satisfied
    )


def compute_goal1_kpis_kernel(
    baseline: np.ndarray,
    best: np.ndarray,
    x_value: float = 0.0,
    valid_min: float = -150.0,
    valid_max: float = -30.0,
) -> tuple:
    """
    High-performance wrapper for Goal Type 1 KPI computation.
    
    Args:
        baseline: Baseline RSRP raster
        best: Best (max) RSRP raster from candidates
        x_value: Target percentage gain
        valid_min: Minimum valid RSRP value
        valid_max: Maximum valid RSRP value
    
    Returns:
        (n_best_valid, n_overlap, n_new, n_improved, pct_improved,
         avg_baseline, avg_best, avg_abs_gain, avg_pct_gain, goal_satisfied)
    """
    if NUMBA_AVAILABLE:
        logger.debug(f"[Goal Type 1] Using Numba JIT compilation (array shape: {best.shape})")
    else:
        logger.debug(f"[Goal Type 1] Using pure Python fallback (array shape: {best.shape})")
    
    return _compute_goal1_metrics(baseline, best, x_value, valid_min, valid_max)


# =============================================================================
# Goal Type 2: RSRP Threshold
# =============================================================================

@njit
def _compute_goal2_metrics(
    baseline: np.ndarray,
    best: np.ndarray,
    threshold_value: float,
    valid_min: float,
    valid_max: float,
) -> tuple:
    """
    JIT-compiled kernel for GoalType 2 KPI computation.
    
    Returns:
        (n_best_valid, n_meets_threshold_best, n_below_threshold,
         n_meets_threshold_baseline, n_meets_threshold_overlap, avg_pct_gain, 
         all_meet_threshold)
    """
    baseline_f64 = baseline.astype(np.float64)
    best_f64 = best.astype(np.float64)
    
    height, width = best_f64.shape
    n_best_valid = 0
    n_meets_threshold_best = 0
    n_below_threshold = 0
    n_meets_threshold_baseline = 0
    n_meets_threshold_overlap = 0
    n_overlap = 0
    
    sum_pct_gain = 0.0
    
    for i in range(height):
        for j in range(width):
            b_val = baseline_f64[i, j]
            c_val = best_f64[i, j]
            
            # Check best validity
            b_finite = not np.isnan(b_val) and not np.isinf(b_val)
            c_finite = not np.isnan(c_val) and not np.isinf(c_val)
            c_valid = c_finite and (c_val >= valid_min) and (c_val <= valid_max)
            
            if c_valid:
                n_best_valid += 1
                
                # Threshold check on best
                if c_val >= threshold_value:
                    n_meets_threshold_best += 1
                else:
                    n_below_threshold += 1
                
                # Check overlap validity for supporting metrics
                b_valid = b_finite and (b_val >= valid_min) and (b_val <= valid_max)
                if b_valid:
                    n_overlap += 1
                    
                    # Baseline threshold check
                    if b_val >= threshold_value:
                        n_meets_threshold_baseline += 1
                    
                    # Best threshold check on overlap
                    if c_val >= threshold_value:
                        n_meets_threshold_overlap += 1
                    
                    # Per-pixel % gain for supporting metric
                    abs_b = abs(b_val)
                    if abs_b > 0.0:
                        pct_gain = ((c_val - b_val) / abs_b) * 100.0
                    else:
                        pct_gain = 0.0
                    sum_pct_gain += pct_gain
    
    # Compute averages
    if n_overlap > 0:
        avg_pct_gain = sum_pct_gain / n_overlap
    else:
        avg_pct_gain = 0.0
    
    # Check if all best-valid pixels meet threshold
    all_meet_threshold = (n_best_valid > 0) and (n_meets_threshold_best == n_best_valid)
    
    # Compute % meets threshold on best-valid pixels
    if n_best_valid > 0:
        pct_meets_threshold = (n_meets_threshold_best / n_best_valid) * 100.0
    else:
        pct_meets_threshold = 0.0
    
    return (
        n_best_valid, n_meets_threshold_best, n_below_threshold,
        n_meets_threshold_baseline, n_meets_threshold_overlap, avg_pct_gain,
        all_meet_threshold, pct_meets_threshold
    )


def compute_goal2_kpis_kernel(
    baseline: np.ndarray,
    best: np.ndarray,
    threshold_value: float = 0.0,
    valid_min: float = -150.0,
    valid_max: float = -30.0,
) -> tuple:
    """
    High-performance wrapper for Goal Type 2 KPI computation.
    
    Args:
        baseline: Baseline RSRP raster
        best: Best (max) RSRP raster from candidates
        threshold_value: RSRP threshold target
        valid_min: Minimum valid RSRP value
        valid_max: Maximum valid RSRP value
    
    Returns:
        (n_best_valid, n_meets_threshold_best, n_below_threshold,
         n_meets_threshold_baseline, n_meets_threshold_overlap, avg_pct_gain,
         all_meet_threshold, pct_meets_threshold)
    """
    if NUMBA_AVAILABLE:
        logger.debug(f"[Goal Type 2] Using Numba JIT compilation (array shape: {best.shape})")
    else:
        logger.debug(f"[Goal Type 2] Using pure Python fallback (array shape: {best.shape})")
    
    return _compute_goal2_metrics(baseline, best, threshold_value, valid_min, valid_max)
