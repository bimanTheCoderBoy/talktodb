"""Calculator for RSRP threshold goal (GoalType 2).

Delegates all KPI computation to ``compute_goal2_kpis`` so that the
calculator, report service, and frontend all share the same metric
definitions and pixel-domain rules.

Goal value = **% Meets Threshold (Best)** computed on BestValidPixels (0–100).

Returns a 4-tuple so the caller can forward the already-loaded arrays
to the report service without re-reading from disk.
"""

import logging
from typing import List, Any, Tuple, Dict

import numpy as np

from .base_calculation_service import RasterBestValueService
from asp_app.services.comparison.kpi_utils import compute_goal2_kpis

logger = logging.getLogger(__name__)


class RsrpThresholdCalculator:
    """Calculator for 'Make sure RSRP threshold will be x' goal."""

    @staticmethod
    async def run(
        best_paths: List[str],
        baseline_path: str,
        threshold_value: float = 0,
        **kwargs: Any,
    ) -> Tuple[float, Dict[str, Any], np.ndarray, np.ndarray]:
        """Compute % Meets Threshold on best-valid pixels.

        Returns ``(goal_value, result_details, baseline_array, best_array)``.
        """
        empty_details: Dict[str, Any] = {
            "Threshold (dBm)": round(float(threshold_value), 4) if np.isfinite(threshold_value) else None,
            "Total Pixels (Best-valid)": 0,
            "Pixels Meeting Threshold (Best)": 0,
            "% Meets Threshold (Best)": None,
            "Pixels Below Threshold (Best)": 0,
            "Pixels Meeting Threshold (Baseline)": 0,
            "Pixels Meeting Threshold (Best, Overlap)": 0,
            "Avg % Gain": None,
            "Meets Threshold (All)": False,
        }
        empty_arr = np.array([], dtype=np.float32)

        if not best_paths:
            logger.warning("RsrpThresholdCalculator: no best_paths, returning 0")
            return 0.0, empty_details, empty_arr, empty_arr
        if not np.isfinite(threshold_value):
            logger.warning("RsrpThresholdCalculator: threshold_value=%s is not finite, returning 0", threshold_value)
            return 0.0, empty_details, empty_arr, empty_arr

        svc = RasterBestValueService()
        # Best of (baseline, candidates) — consistent with GoalType 1
        all_paths = [baseline_path] + best_paths
        best_array = await svc.get_best_data("max", all_paths)
        baseline_array = await svc.read_single_array(baseline_path)

        logger.info(
            "RsrpThresholdCalculator: best_array shape=%s, threshold_value=%s",
            best_array.shape, threshold_value,
        )

        # Delegate KPI computation to the shared helper
        kpis, goal_value = compute_goal2_kpis(
            baseline_array, best_array,
            threshold_value=float(threshold_value),
        )

        logger.info(
            "RsrpThresholdCalculator: goal_value=%.4f, meets_all=%s",
            goal_value, kpis.get("Meets Threshold (All)"),
        )

        return goal_value, kpis, baseline_array, best_array
