"""Calculator for Increase RSRP goal (GoalType 1).

Delegates all KPI computation to ``compute_goal1_kpis`` so that the
calculator, report service, and frontend all share the same metric
definitions and pixel-domain rules.

Goal value = **Avg % Gain** computed on OverlapValidPixels.

Returns a 4-tuple so the caller can forward the already-loaded arrays
to the report service without re-reading from disk.
"""

import logging
from typing import List, Any, Tuple, Dict

import numpy as np

from .base_calculation_service import RasterBestValueService
from asp_app.services.comparison.kpi_utils import compute_goal1_kpis

logger = logging.getLogger(__name__)


class IncreaseRsrpCalculator:
    """Calculator for 'Increase RSRP by x %' goal."""

    @staticmethod
    async def run(
        best_paths: List[str],
        baseline_path: str,
        x_value: float = 0,
        k_value: int = 1,
        **kwargs: Any,
    ) -> Tuple[float, Dict[str, Any], np.ndarray, np.ndarray]:
        """Compute Avg % Gain on overlap-valid pixels.

        Returns ``(goal_value, result_details, baseline_array, best_array)``.
        """
        empty_details: Dict[str, Any] = {
            "Total Pixels (Best-valid)": 0,
            "Total Pixels (Overlap-valid)": 0,
            "New Valid Pixels": 0,
            "Improved Pixels": 0,
            "Improved Pixels (%)": None,
            "Average Baseline RSRP (dBm)": None,
            "Average Best RSRP (dBm)": None,
            "Avg Absolute Gain (dB)": None,
            "Avg % Gain": None,
            "X Value (%)": round(float(x_value), 4) if x_value else 0.0,
            "Goal Satisfied": False,
        }
        empty_arr = np.array([], dtype=np.float32)

        if not best_paths:
            logger.warning("IncreaseRsrpCalculator: no best_paths, returning 0.0")
            return 0.0, empty_details, empty_arr, empty_arr

        svc = RasterBestValueService()
        # Best of (baseline, candidates) — result is never worse than baseline
        all_paths = [baseline_path] + best_paths
        best_array = await svc.get_best_data("max", all_paths)
        baseline_array = await svc.read_single_array(baseline_path)

        logger.info(
            "IncreaseRsrpCalculator: best_array shape=%s, baseline_array shape=%s",
            best_array.shape, baseline_array.shape,
        )

        # Delegate KPI computation to the shared helper
        kpis, goal_value = compute_goal1_kpis(
            baseline_array, best_array,
            x_value=float(x_value),
        )

        logger.info(
            "IncreaseRsrpCalculator: goal_value=%.4f, goal_satisfied=%s",
            goal_value, kpis.get("Goal Satisfied"),
        )

        return goal_value, kpis, baseline_array, best_array
