"""Numba-optimized kernels for fast KPI computation."""

from .compute_kernels import (
    compute_goal1_kpis_kernel,
    compute_goal2_kpis_kernel,
)

__all__ = [
    "compute_goal1_kpis_kernel",
    "compute_goal2_kpis_kernel",
]
