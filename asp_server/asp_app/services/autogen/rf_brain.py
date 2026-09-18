"""
Unified RF planning "brain" for auto-gen.

Today's auto-gen exposes four independent smart-params: height, tilt,
azimuths, power. Each has its own goal-aware bias and its own picture of
"what the operator wants". This module ties them all together via a
single concept — **aggression** — derived from the operator's goal:

  ─ ``rsrp_threshold`` or no goal       → CONSERVATIVE (level 0)
  ─ ``increase_rsrp`` with x_value > 0  → MODERATE     (level 1)
  ─ ``increase_rsrp`` with x_value ≥ 5  → AGGRESSIVE   (level 2)
  ─ ``increase_rsrp`` with x_value ≥ 10 → VERY_AGGR.   (level 3)

The aggression level cascades through every parameter so the decisions
reinforce each other instead of contradicting:

                 Conservative  Moderate  Aggressive  Very Agg.
  Height bias     +5 m         +7 m      +10 m       +13 m
  Tilt percentile P85          P88       P90         P92
  Power bias      +0 dB        +2 dB     +4 dB       +6 dB

  With baseline / template default of 40 dBm:
                 40 dBm        42 dBm    44 dBm      46 dBm
                                                     ^ legal LTE-macro cap

  Azimuths: always multiples of 5° (enforced by the histogram binning
            in ``azimuth_detector.compute_smart_azimuths_per_site``).

Higher aggression = taller site, broader tilt (push energy toward the
horizon), louder power. The intuition is "the operator is trying harder
to fix this gap", so every knob points in the same direction.

Why a brain instead of independent functions
--------------------------------------------
Four independent heuristics can produce **internally inconsistent** plans
— e.g. ``increase_rsrp x=5`` could give moderate-bias height with a
conservative-bias power if the thresholds drift. Routing every decision
through one aggression level guarantees they stay in sync. Operators
debugging a candidate site read **one** number (the aggression level)
and instantly know which knob is at which setting.
"""
from __future__ import annotations

import logging
from enum import IntEnum
from typing import Dict, Iterable, List, Optional, Tuple

from asp_app.services.autogen import power_planner, tilt_mapping
from asp_app.services.autogen.azimuth_detector import compute_smart_azimuths_per_site
from asp_app.services.autogen.placement_service import compute_smart_tilt
from asp_app.services.autogen.synthetic_gdl_writer import compute_smart_height

logger = logging.getLogger(__name__)


class Aggression(IntEnum):
    """How hard the site should be trying to fix the gap."""
    CONSERVATIVE = 0       # rsrp_threshold or no goal — match neighbourhood
    MODERATE = 1           # increase_rsrp with small x_value
    AGGRESSIVE = 2         # increase_rsrp x_value >= 5
    VERY_AGGRESSIVE = 3    # increase_rsrp x_value >= 10


# Aggression-indexed coefficients. Index by ``int(aggression)``.
# Adding new levels = append values to each tuple — single point of edit.
HEIGHT_BIAS_M = (5.0, 7.0, 10.0, 13.0)
TILT_TARGET_PERCENTILE = (85.0, 88.0, 90.0, 92.0)
# Power bias steps in dB. Combined with the new 40 dBm baseline template,
# VERY_AGGRESSIVE lands exactly at the 46 dBm legal LTE-macro per-port
# cap — i.e. "we are doing everything legally allowed for this goal".
POWER_BIAS_DB = (0.0, 2.0, 4.0, 6.0)


# Thresholds for the goal-derived aggression mapping. Centralised here
# so all four parameters cross the same bumps at the same x_value, and
# the table edit is one place if RF planning ever changes its mind.
_X_VAL_VERY_AGGRESSIVE = 10.0
_X_VAL_AGGRESSIVE = 5.0


def derive_aggression(
    goal_type: Optional[str],
    goal_params: Optional[Dict],
) -> Aggression:
    """Map the operator's goal selection to an aggression level."""
    if goal_type != "increase_rsrp":
        return Aggression.CONSERVATIVE
    try:
        x = float((goal_params or {}).get("x_value", 0) or 0)
    except (TypeError, ValueError):
        x = 0.0
    if x >= _X_VAL_VERY_AGGRESSIVE:
        return Aggression.VERY_AGGRESSIVE
    if x >= _X_VAL_AGGRESSIVE:
        return Aggression.AGGRESSIVE
    if x > 0:
        return Aggression.MODERATE
    return Aggression.CONSERVATIVE


class SiteRFParams:
    """Final smart-param decisions for a single auto-generated site.

    Plain object (not dataclass) to keep import surface minimal for the
    Celery worker. All fields are scalars/lists with explicit types so
    serialising to setup_state is trivial.

    PPRE note: the brain deliberately does **not** compute a per-site PPRE
    — pumping pilot power does not move the RSRP goal the operator cares
    about (RSRP gain comes from Max TX, geometry, or new sites). PPRE is
    left at the template default (e.g. 15.2 dBm for the AIR3237 catalog).
    """

    __slots__ = (
        "height_m", "tilt_deg", "tilt_resolved_uid",
        "azimuths_deg", "max_tx_dbm",
        "aggression", "target_percentile", "height_bias_m", "power_bias_db",
    )

    def __init__(
        self,
        height_m: float,
        tilt_deg: float,
        tilt_resolved_uid: Optional[str],
        azimuths_deg: List[float],
        max_tx_dbm: float,
        aggression: Aggression,
        target_percentile: float,
        height_bias_m: float,
        power_bias_db: float,
    ):
        self.height_m = float(height_m)
        self.tilt_deg = float(tilt_deg)
        self.tilt_resolved_uid = tilt_resolved_uid
        self.azimuths_deg = [float(a) for a in azimuths_deg]
        self.max_tx_dbm = float(max_tx_dbm)
        self.aggression = aggression
        self.target_percentile = float(target_percentile)
        self.height_bias_m = float(height_bias_m)
        self.power_bias_db = float(power_bias_db)


def decide_site_params(
    *,
    site_lat: float,
    site_lon: float,
    poor_bins_nearby: List,
    poor_weights_nearby: Optional[List[float]],
    baseline_sites: Iterable[Dict],
    goal_type: Optional[str],
    goal_params: Optional[Dict],
    template_defaults: Dict,
    band_code: str,
    available_tilts: List[float],
    tilt_range: Dict[str, float],
    template_default_tilt: float,
    electrical_tilt_override: Optional[float] = None,
    n_sectors: int = 3,
    min_sep_deg: int = 65,
) -> SiteRFParams:
    """Single coherent decision for height, tilt, azimuths, Max TX, PPRE.

    Every parameter is derived from the same ``Aggression`` level, so the
    plan is internally consistent: a site that's taller is also tilted to
    aim farther, transmits at higher power, and the operator sees one
    aggression number explaining all four choices.

    Args:
        site_lat / site_lon: candidate centroid (WGS84).
        poor_bins_nearby: (lat, lon) tuples within the catchment radius.
        poor_weights_nearby: composite (severity × population) weights
            parallel to ``poor_bins_nearby``. None → uniform.
        baseline_sites: nearby existing sites/cells; their heights drive
            ``smart_height``, their power columns drive ``smart_max_tx``.
        goal_type / goal_params: from ``setup_state.defineGoal``.
        template_defaults: GDL defaults from the antenna-template JSON;
            supplies fallback height / Max TX / PPRE when baseline is empty.
        band_code: two-digit band identifier (``"07"``, ``"18"`` …) for
            tilt-mapping resolution.
        available_tilts: discrete tilt values the band carries per the
            operator-uploaded mapping. Empty → continuous-clamp fallback.
        tilt_range / template_default_tilt: ``placement_service.compute_smart_tilt``
            arguments for the continuous-clamp fallback.
        electrical_tilt_override: when not None, bypass the geometry path
            entirely (still snapped to the mapping). Used by the manual
            AutoGenPanel "Electrical Tilt" input.
    """
    aggression = derive_aggression(goal_type, goal_params)
    level = int(aggression)

    height_bias_m = HEIGHT_BIAS_M[level]
    target_percentile = TILT_TARGET_PERCENTILE[level]
    power_bias_db = POWER_BIAS_DB[level]

    # 1. Height — median of nearby baseline + aggression bias, clamped.
    template_h = float(template_defaults.get("Property: Physical Antenna: Height - Inventory (m)", 15.0))
    height_m = compute_smart_height(
        baseline_sites=list(baseline_sites),
        bias_m=height_bias_m,
        template_default=template_h,
    )

    # 2. Azimuths — bearing histogram binned to 5° increments (operator
    #    requirement: every emitted azimuth is a multiple of 5°),
    #    weighted by composite gap-severity × population score.
    azimuths_deg = compute_smart_azimuths_per_site(
        site_lat, site_lon, poor_bins_nearby,
        n_sectors=n_sectors, min_sep_deg=min_sep_deg,
        weights_nearby=poor_weights_nearby,
    )

    # 3. Tilt — user override wins; else atan(h / d_target) where target
    #    distance is the aggression-indexed weighted percentile of the
    #    composite-score-weighted distance distribution.
    mapping_active = bool(available_tilts)
    if electrical_tilt_override is not None:
        tilt_deg = float(electrical_tilt_override)
        if mapping_active:
            tilt_deg = float(tilt_mapping.snap_tilt(band_code, tilt_deg) or tilt_deg)
    else:
        tilt_deg = compute_smart_tilt(
            site_lat, site_lon, poor_bins_nearby,
            height_m=height_m,
            tilt_min=tilt_range["min"], tilt_max=tilt_range["max"],
            default=template_default_tilt,
            weights_nearby=poor_weights_nearby,
            available_tilts=available_tilts if mapping_active else None,
            target_percentile=target_percentile,
        )

    tilt_resolved_uid = (
        tilt_mapping.resolve_uid(band_code, tilt_deg) if mapping_active else None
    )

    # 4. Power — median of baseline + aggression bias, clamped legal range.
    # PPRE deliberately omitted; see SiteRFParams docstring. The cell
    # writer falls back to ``template_defaults["Cell: LTE: Ref Signal
    # PPRE (dBm)"]`` for every cell.
    template_max_tx = float(template_defaults.get("Cell: LTE: Max TX Power (dBm)", 30.0))
    max_tx_dbm = power_planner.smart_max_tx_dbm(
        baseline_cells_nearby=baseline_sites,
        bias_db=power_bias_db,
        template_default=template_max_tx,
    )

    return SiteRFParams(
        height_m=height_m,
        tilt_deg=tilt_deg,
        tilt_resolved_uid=tilt_resolved_uid,
        azimuths_deg=azimuths_deg,
        max_tx_dbm=max_tx_dbm,
        aggression=aggression,
        target_percentile=target_percentile,
        height_bias_m=height_bias_m,
        power_bias_db=power_bias_db,
    )


def describe_aggression(aggression: Aggression) -> str:
    """Human-readable summary for Redis logs / UI hints."""
    level = int(aggression)
    return (
        f"aggression={aggression.name.lower()} "
        f"(height+{HEIGHT_BIAS_M[level]:.0f}m, tilt-target=P{int(TILT_TARGET_PERCENTILE[level])}, "
        f"power+{POWER_BIAS_DB[level]:.0f}dB)"
    )
