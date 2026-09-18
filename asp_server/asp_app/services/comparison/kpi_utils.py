"""Shared KPI computation helpers for coverage comparison.

Provides GoalType-specific KPI dictionaries with operator-friendly labels.
All metrics use RSRP-valid pixels only ([-150, -30] dBm range).

Pixel populations
-----------------
- **BestValidPixels** : ``best`` is finite and within [-150, -30].
- **OverlapValidPixels** : *both* baseline and best are finite and within [-150, -30].
- **NewValidPixels** : BestValid minus Overlap (expansion area).
"""

import math
import logging
from typing import Dict, Any, Optional

import numpy as np

from asp_app.services.calculation_services.kernels import (
    compute_goal1_kpis_kernel,
    compute_goal2_kpis_kernel,
)

logger = logging.getLogger(__name__)

# RSRP validity bounds — pixels outside this range are treated as no-data.
VALID_MIN: float = -150.0
VALID_MAX: float = -30.0


# ---------------------------------------------------------------------------
# JSON-safe helper
# ---------------------------------------------------------------------------

def _safe_float(val: float, decimals: int = 4) -> Optional[float]:
    """Return *val* rounded to *decimals* if finite, else ``None``."""
    if isinstance(val, (int, float)) and math.isfinite(val):
        return round(float(val), decimals)
    return None


# ---------------------------------------------------------------------------
# Mask builders
# ---------------------------------------------------------------------------

def best_valid_mask(
    best: np.ndarray,
    valid_min: float = VALID_MIN,
    valid_max: float = VALID_MAX,
) -> np.ndarray:
    """Boolean mask where *best* is finite and within [valid_min, valid_max]."""
    c = best.astype(np.float64)
    return np.isfinite(c) & (c >= valid_min) & (c <= valid_max)


def overlap_valid_mask(
    baseline: np.ndarray,
    best: np.ndarray,
    valid_min: float = VALID_MIN,
    valid_max: float = VALID_MAX,
) -> np.ndarray:
    """Boolean mask where *both* baseline and best are finite and within range."""
    b = baseline.astype(np.float64)
    c = best.astype(np.float64)
    return (
        np.isfinite(b) & np.isfinite(c)
        & (b >= valid_min) & (b <= valid_max)
        & (c >= valid_min) & (c <= valid_max)
    )


# ---------------------------------------------------------------------------
# GoalType 1: increase_rsrp
# ---------------------------------------------------------------------------

# Human-readable explanations for the JSON report file.
GOAL1_EXPLANATIONS: Dict[str, str] = {
    "Total Pixels (Best-valid)": "Count of pixels where best RSRP is finite and within [-150, -30] dBm.",
    "Total Pixels (Overlap-valid)": "Count of pixels where both baseline and best RSRP are finite and within [-150, -30] dBm. Used for gain calculations.",
    "New Valid Pixels": "Pixels where best has valid RSRP but baseline does not (expansion area).",
    "Improved Pixels": "Number of overlap-valid pixels where best RSRP > baseline RSRP.",
    "Improved Pixels (%)": "Percentage of overlap-valid pixels where best > baseline.",
    "Average Baseline RSRP (dBm)": "Mean baseline RSRP over overlap-valid pixels.",
    "Average Best RSRP (dBm)": "Mean best RSRP over overlap-valid pixels.",
    "Avg Absolute Gain (dB)": "Mean of (best - baseline) over all overlap-valid pixels.",
    "Avg % Gain": "Mean of ((best - baseline) / |baseline|) * 100 over overlap-valid pixels. This is the goal ranking score.",
    "X Value (%)": "User-specified target percentage gain.",
    "Goal Satisfied": "True if Avg % Gain >= X Value.",
}


def compute_goal1_kpis(
    baseline: np.ndarray,
    best: np.ndarray,
    x_value: float = 0.0,
    valid_min: float = VALID_MIN,
    valid_max: float = VALID_MAX,
) -> Dict[str, Any]:
    """Compute KPIs for GoalType 1 (increase_rsrp).

    Returns an ordered dict with user-friendly labels.
    Also returns ``goal_value`` = Avg % Gain.
    Uses high-performance Numba JIT kernels for pixel-level computation.
    """
    # Convert float16 to float32 for Numba kernels (float16 has insufficient precision)
    baseline = baseline.astype(np.float32) if baseline.dtype == np.float16 else baseline
    best = best.astype(np.float32) if best.dtype == np.float16 else best
    
    # Call high-performance kernel (JIT-compiled or pure Python fallback)
    (
        n_best_valid, n_overlap, n_new, n_improved, pct_improved,
        avg_baseline, avg_best, avg_abs_gain, avg_pct_gain, goal_satisfied
    ) = compute_goal1_kpis_kernel(baseline, best, x_value, valid_min, valid_max)

    # Empty fallback
    if n_overlap == 0:
        logger.warning("compute_goal1_kpis: no overlap-valid pixels")
        return {
            "Total Pixels (Best-valid)": n_best_valid,
            "Total Pixels (Overlap-valid)": 0,
            "New Valid Pixels": n_new,
            "Improved Pixels": 0,
            "Improved Pixels (%)": None,
            "Average Baseline RSRP (dBm)": None,
            "Average Best RSRP (dBm)": None,
            "Avg Absolute Gain (dB)": None,
            "Avg % Gain": None,
            "X Value (%)": _safe_float(x_value),
            "Goal Satisfied": False,
        }, 0.0

    kpis: Dict[str, Any] = {
        "Total Pixels (Best-valid)": n_best_valid,
        "Total Pixels (Overlap-valid)": n_overlap,
        "New Valid Pixels": n_new,
        "Improved Pixels": n_improved,
        "Improved Pixels (%)": _safe_float(pct_improved),
        "Average Baseline RSRP (dBm)": _safe_float(avg_baseline),
        "Average Best RSRP (dBm)": _safe_float(avg_best),
        "Avg Absolute Gain (dB)": _safe_float(avg_abs_gain),
        "Avg % Gain": _safe_float(avg_pct_gain),
        "X Value (%)": _safe_float(float(x_value)),
        "Goal Satisfied": goal_satisfied,
    }

    goal_value = round(avg_pct_gain, 4)

    logger.info(
        "compute_goal1_kpis: overlap=%s, improved=%s (%.1f%%), avg_gain=%.2f dB, avg_pct=%.2f%%, goal_sat=%s",
        n_overlap, n_improved, pct_improved, avg_abs_gain, avg_pct_gain, goal_satisfied,
    )

    return kpis, goal_value


# ---------------------------------------------------------------------------
# GoalType 2: rsrp_threshold
# ---------------------------------------------------------------------------

GOAL2_EXPLANATIONS: Dict[str, str] = {
    "Threshold (dBm)": "User-specified RSRP threshold value.",
    "Total Pixels (Best-valid)": "Count of pixels where best RSRP is finite and within [-150, -30] dBm.",
    "Pixels Meeting Threshold (Best)": "Best-valid pixels where best RSRP >= threshold.",
    "% Meets Threshold (Best)": "Percentage of best-valid pixels meeting the threshold. This is the goal ranking score.",
    "Pixels Below Threshold (Best)": "Best-valid pixels where best RSRP < threshold.",
    "Pixels Meeting Threshold (Baseline)": "Overlap-valid pixels where baseline RSRP >= threshold (before adding candidates).",
    "Pixels Meeting Threshold (Best, Overlap)": "Overlap-valid pixels where best RSRP >= threshold (after adding candidates).",
    "Avg % Gain": "Mean of ((best - baseline) / |baseline|) * 100 over overlap-valid pixels (supporting metric).",
    "Meets Threshold (All)": "True if every best-valid pixel meets the threshold (100% compliance).",
}


def compute_goal2_kpis(
    baseline: np.ndarray,
    best: np.ndarray,
    threshold_value: float = 0.0,
    valid_min: float = VALID_MIN,
    valid_max: float = VALID_MAX,
) -> Dict[str, Any]:
    """Compute KPIs for GoalType 2 (rsrp_threshold).

    Returns an ordered dict with user-friendly labels.
    Also returns ``goal_value`` = % Meets Threshold (Best) on BestValidPixels.
    Uses high-performance Numba JIT kernels for pixel-level computation.
    """
    # Convert float16 to float32 for Numba kernels (float16 has insufficient precision)
    baseline = baseline.astype(np.float32) if baseline.dtype == np.float16 else baseline
    best = best.astype(np.float32) if best.dtype == np.float16 else best
    
    # Call high-performance kernel (JIT-compiled or pure Python fallback)
    (
        n_best_valid, n_meets_threshold_best, n_below_threshold,
        n_meets_threshold_baseline, n_meets_threshold_overlap, avg_pct_gain_val,
        meets_all, pct_meets
    ) = compute_goal2_kpis_kernel(baseline, best, threshold_value, valid_min, valid_max)

    if n_best_valid == 0:
        logger.warning("compute_goal2_kpis: no best-valid pixels")
        return {
            "Threshold (dBm)": _safe_float(threshold_value),
            "Total Pixels (Best-valid)": 0,
            "Pixels Meeting Threshold (Best)": 0,
            "% Meets Threshold (Best)": None,
            "Pixels Below Threshold (Best)": 0,
            "Pixels Meeting Threshold (Baseline)": 0,
            "Pixels Meeting Threshold (Best, Overlap)": 0,
            "Avg % Gain": None,
            "Meets Threshold (All)": False,
        }, 0.0

    # Format avg_pct_gain
    avg_pct_gain = None
    if math.isfinite(avg_pct_gain_val):
        avg_pct_gain = _safe_float(avg_pct_gain_val)

    kpis: Dict[str, Any] = {
        "Threshold (dBm)": _safe_float(threshold_value),
        "Total Pixels (Best-valid)": n_best_valid,
        "Pixels Meeting Threshold (Best)": n_meets_threshold_best,
        "% Meets Threshold (Best)": _safe_float(pct_meets),
        "Pixels Below Threshold (Best)": n_below_threshold,
        "Pixels Meeting Threshold (Baseline)": n_meets_threshold_baseline,
        "Pixels Meeting Threshold (Best, Overlap)": n_meets_threshold_overlap,
        "Avg % Gain": avg_pct_gain,
        "Meets Threshold (All)": meets_all,
    }

    goal_value = pct_meets

    logger.info(
        "compute_goal2_kpis: best_valid=%s, meets=%s (%.1f%%), below=%s, meets_all=%s",
        n_best_valid, n_meets_threshold_best, pct_meets, n_below_threshold, meets_all,
    )

    return kpis, goal_value
