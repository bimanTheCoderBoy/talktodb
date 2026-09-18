"""Service to generate comparison report artifacts (PNG + stats JSON) per candidate.

Writes output to a local folder rooted at:
    ACSS_RESULT_DIR / <session_id> / <goal_type> / <candidate_slug> /

The baseline and best arrays are passed in directly (already loaded by the
calculator) so there is **no** duplicate raster read from UNC.

All heavy I/O and matplotlib rendering is done via ``asyncio.to_thread``
so the async event loop is never blocked.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import numpy as np

import matplotlib
matplotlib.use("Agg")  # headless backend — must be set before importing pyplot
import matplotlib.pyplot as plt  # noqa: E402

from asp_app.config.acss_config import get_acss_config
from asp_app.services.comparison.kpi_utils import GOAL1_EXPLANATIONS, GOAL2_EXPLANATIONS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify_candidate_name(name: str) -> str:
    """Sanitize a candidate_name (may contain ``|``, spaces, etc.) into a
    filesystem-safe slug usable on both Windows and Linux.

    Example: ``"Site_A|Site_B"``  ->  ``"Site_A__Site_B"``
    """
    slug = name.replace("|", "__")
    # Remove anything that is not alphanumeric, dash, underscore, or dot
    slug = re.sub(r"[^\w\-.]", "_", slug)
    # Collapse multiple underscores
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "unknown"


def _get_explanations(goal_type_value: str) -> Dict[str, str]:
    """Return the human-readable explanations dict for the given goal type."""
    if goal_type_value == "increase_rsrp":
        return dict(GOAL1_EXPLANATIONS)
    elif goal_type_value == "rsrp_threshold":
        return dict(GOAL2_EXPLANATIONS)
    return {}


# ---------------------------------------------------------------------------
# Matplotlib rendering (synchronous — called in thread pool)
# ---------------------------------------------------------------------------

def _render_compare_png(
    baseline: np.ndarray,
    best: np.ndarray,
    diff: np.ndarray,
    output_path: str,
    candidate_name: str,
) -> None:
    """Save a 3-panel comparison PNG (Baseline | Best | Difference)."""
    fig, axs = plt.subplots(1, 3, figsize=(14, 5))

    im0 = axs[0].imshow(baseline, cmap="viridis", vmin=-130, vmax=-60)
    axs[0].set_title("Baseline", fontsize=10)

    im1 = axs[1].imshow(best, cmap="viridis", vmin=-130, vmax=-60)
    axs[1].set_title("Best (with candidates)", fontsize=10)

    im2 = axs[2].imshow(diff, cmap="RdYlGn", vmin=-10, vmax=10)
    axs[2].set_title("Difference (dB)", fontsize=10)

    for ax in axs:
        ax.axis("off")

    # Color bars
    fig.colorbar(im0, ax=axs[0], fraction=0.046, pad=0.04, label="dBm")
    fig.colorbar(im1, ax=axs[1], fraction=0.046, pad=0.04, label="dBm")
    fig.colorbar(im2, ax=axs[2], fraction=0.046, pad=0.04, label="dB")

    fig.suptitle(f"Candidate: {candidate_name}", fontsize=11, y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    logger.info("_render_compare_png: saved %s", output_path)


def _write_stats_json(payload: Dict[str, Any], output_path: str) -> None:
    """Write a JSON file containing the result_details KPIs + explanations."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, default=str)
    logger.info("_write_stats_json: saved %s", output_path)


def _write_manifest(manifest: Dict[str, Any], output_path: str) -> None:
    """Write (or overwrite) the report manifest JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4, default=str)
    logger.info("_write_manifest: saved %s", output_path)


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------

class ComparisonReportService:
    """Generates comparison report artifacts for a single candidate evaluation."""

    @staticmethod
    async def generate_candidate_report(
        session_id: UUID,
        goal_type_value: str,
        candidate_name: str,
        baseline_array: np.ndarray,
        best_array: np.ndarray,
        result_details: Dict[str, Any],
    ) -> Dict[str, str]:
        """Generate a comparison report (PNG + stats JSON) for one candidate.

        Parameters
        ----------
        session_id : UUID
        goal_type_value : str  – e.g. ``"increase_rsrp"`` or ``"rsrp_threshold"``
        candidate_name : str  – raw name with ``|`` separators
        baseline_array : np.ndarray  – baseline raster (already loaded by calculator)
        best_array : np.ndarray  – best-of raster (already loaded by calculator)
        result_details : dict  – KPIs already computed by the calculator

        Returns
        -------
        dict with keys ``"report_dir"``, ``"compare_png"``, ``"stats_json"``
        holding the **full paths** to the generated artifacts.
        Returns empty dict on failure (logged, not raised).
        """
        try:
            config = get_acss_config()
            result_root = config.acss_result_dir

            # Build output directory:
            # acss_result_dir / session_id / goal_type / candidate_slug
            candidate_slug = slugify_candidate_name(candidate_name)
            report_dir = os.path.join(result_root, str(session_id), goal_type_value, candidate_slug)

            # Create directory on disk (blocking I/O in thread pool)
            await asyncio.to_thread(os.makedirs, report_dir, exist_ok=True)

            # Compute diff (float32 for plotting)
            baseline_f32 = baseline_array.astype(np.float32)
            best_f32 = best_array.astype(np.float32)
            diff = best_f32 - baseline_f32

            # --- Generate PNG ---
            compare_png_path = os.path.join(report_dir, "compare.png")
            await asyncio.to_thread(
                _render_compare_png,
                baseline_f32, best_f32, diff,
                compare_png_path, candidate_name,
            )

            # --- Write stats JSON (with explanations) ---
            stats_json_path = os.path.join(report_dir, "stats.json")
            enriched = {
                "candidate_name": candidate_name,
                "session_id": str(session_id),
                "goal_type": goal_type_value,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "kpis": result_details,
                "explanations": _get_explanations(goal_type_value),
            }
            await asyncio.to_thread(_write_stats_json, enriched, stats_json_path)

            return {
                "report_dir": report_dir,
                "compare_png": compare_png_path,
                "stats_json": stats_json_path,
            }

        except Exception as exc:
            logger.exception(
                "ComparisonReportService.generate_candidate_report failed for %s: %s",
                candidate_name, exc,
            )
            return {}

    @staticmethod
    async def write_manifest(
        session_id: UUID,
        goal_type_value: str,
        entries: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Write a top-level ``manifest.json`` listing all candidate reports.

        Parameters
        ----------
        entries : list[dict] – one dict per candidate with at least
            ``candidate_name`` and ``report_dir``.

        Returns
        -------
        str – path to manifest, or None on failure.
        """
        try:
            config = get_acss_config()
            result_root = config.acss_result_dir
            # acss_result_dir / session_id / goal_type
            manifest_dir = os.path.join(result_root, str(session_id), goal_type_value)

            await asyncio.to_thread(os.makedirs, manifest_dir, exist_ok=True)

            manifest_path = os.path.join(manifest_dir, "manifest.json")
            manifest = {
                "session_id": str(session_id),
                "goal_type": goal_type_value,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_candidates": len(entries),
                "candidates": entries,
            }
            await asyncio.to_thread(_write_manifest, manifest, manifest_path)
            return manifest_path
        except Exception as exc:
            logger.exception("ComparisonReportService.write_manifest failed: %s", exc)
            return None
