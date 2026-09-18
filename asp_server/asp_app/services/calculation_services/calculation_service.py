"""Main calculation service: dispatches by goal type to the right calculator."""

from typing import Callable, Any, Dict, List, Tuple, Union

import numpy as np

from asp_app.db.schemas.setup import GoalType
from .increase_rsrp_calculator import IncreaseRsrpCalculator
from .rsrp_threshold_calculator import RsrpThresholdCalculator


class CalculationService:
    """Returns the appropriate calculation function for a given goal type."""

    _CALCULATORS = {
        GoalType.INCREASE_RSRP: IncreaseRsrpCalculator.run,
        GoalType.RSRP_THRESHOLD: RsrpThresholdCalculator.run,
    }

    @classmethod
    def get_calculation_function(cls, goal_type: GoalType) -> Callable[..., Any]:
        """Return the runnable (async) calculation function for the given goal type."""
        fn = cls._CALCULATORS.get(goal_type)
        if fn is None:
            raise ValueError(f"Unknown goal type: {goal_type}")
        return fn

    @classmethod
    async def run_calculation(
        cls,
        goal_type: GoalType,
        best_paths: List[str],
        baseline_path: str,
        **goal_params: Any,
    ) -> Union[float, int]:
        """
        Resolve the calculator for goal_type and run it.
        Returns goal_value only (backward-compatible).
        """
        goal_value, _details, _baseline, _best = await cls.run_calculation_with_details(
            goal_type=goal_type,
            best_paths=best_paths,
            baseline_path=baseline_path,
            **goal_params,
        )
        return goal_value

    @classmethod
    async def run_calculation_with_details(
        cls,
        goal_type: GoalType,
        best_paths: List[str],
        baseline_path: str,
        **goal_params: Any,
    ) -> Tuple[Union[float, int], Dict[str, Any], np.ndarray, np.ndarray]:
        """
        Resolve the calculator for goal_type and run it.
        Returns (goal_value, result_details, baseline_array, best_array).
        The arrays are the same ones the calculator already loaded from disk,
        so the caller can forward them to the report service without re-reading.
        """
        fn = cls.get_calculation_function(goal_type)
        return await fn(
            best_paths=best_paths,
            baseline_path=baseline_path,
            **goal_params,
        )
