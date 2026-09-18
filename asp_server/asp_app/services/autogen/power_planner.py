"""
Smart per-site Max TX Power and Ref Signal PPRE.

Today's auto-gen stamps every cell with the static template value
(``Cell: LTE: Max TX Power (dBm) = 30``, ``Ref Signal PPRE (dBm) = 15.2``).
That means every auto-generated site is **arbitrarily loud or quiet**
relative to the cells around it — pilot pollution risk on the high side,
under-coverage on the low side, and no responsiveness to the operator's
``increase_rsrp`` goal.

This module replaces that with three small steps:

  1. **Inherit from local infrastructure** — Max TX and PPRE are pulled
     from the nearby baseline cells (median across the catchment) so a
     synthesized site "fits in" with the neighbours instead of being
     arbitrarily loud or quiet.

  2. **Goal-aware bias** — when the user picked ``increase_rsrp`` with an
     aggressive ``x_value`` target, nudge Max TX up by 1-3 dB. Mirrors the
     same shape used by ``compute_smart_height``'s goal bias so the
     auto-gen feels coherent.

  3. **Hard clamp** to the legal LTE-macro range so a bad data row in the
     project DB cannot produce an illegal payload. PPRE additionally
     respects a pilot/data ratio guard to avoid pilot-pollution.

No propagation model. No DEM. No external dependencies. Reads only from
the existing baseline cell rows.
"""
from __future__ import annotations

import logging
from statistics import median
from typing import Dict, Iterable, Optional

logger = logging.getLogger(__name__)

# Hard clamps for legal LTE macro power. Out-of-range values are pulled
# back to the nearest legal bound rather than rejected — the auto-gen
# pipeline should not fail on dirty baseline data.
MAX_TX_MIN_DBM = 23.0
MAX_TX_MAX_DBM = 46.0

# PPRE / Max TX gap — typical CRS power planning sits in this window.
# Outside the window we clamp PPRE up or down so the pilot/data ratio
# stays sane and the cell does not pollute neighbours.
PPRE_GAP_MIN_DB = -20.0  # PPRE no further than 20 dB below Max TX
PPRE_GAP_MAX_DB = -10.0  # PPRE no closer than 10 dB to Max TX

# Default PPRE offset when no baseline data is available. Matches the
# current template (Max TX = 30, PPRE = 15.2) within rounding.
_DEFAULT_PPRE_OFFSET_DB = -15.0


_MAX_TX_KEYS = (
    "max_tx_power_dbm",
    "max_tx_dbm",
    "max_tx_power",
    "lte_max_tx_dbm",
)
_PPRE_KEYS = (
    "ref_signal_ppre_dbm",
    "ppre_dbm",
    "ref_signal_ppre",
    "lte_ref_signal_ppre_dbm",
)


def _pluck(cell: Dict, candidate_keys: Iterable[str]) -> Optional[float]:
    """First non-null float across candidate keys. None if nothing usable."""
    for k in candidate_keys:
        v = cell.get(k) if isinstance(cell, dict) else None
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def smart_max_tx_dbm(
    baseline_cells_nearby: Iterable[Dict],
    bias_db: float = 0.0,
    template_default: float = 30.0,
) -> float:
    """Median Max TX of the local cells + aggression bias, clamped to legal range.

    Args:
        baseline_cells_nearby: cell dicts produced by the cellsInPolygon
            handoff (any of the standard Max TX column aliases will be
            picked up — see ``_MAX_TX_KEYS``).
        bias_db: aggression-indexed dB offset on top of the local median.
            Selected by ``services.autogen.rf_brain.POWER_BIAS_DB``
            based on the operator's goal.
        template_default: fallback when no nearby cells carry power data.

    Returns: Max TX in dBm, clamped to legal LTE-macro range [23, 46].
    """
    powers = []
    for c in (baseline_cells_nearby or []):
        v = _pluck(c, _MAX_TX_KEYS)
        if v is not None:
            powers.append(v)
    base = float(median(powers)) if powers else float(template_default)
    return float(_clamp(base + float(bias_db), MAX_TX_MIN_DBM, MAX_TX_MAX_DBM))


def smart_ppre_dbm(
    max_tx_dbm: float,
    baseline_cells_nearby: Iterable[Dict],
    template_default: Optional[float] = None,
) -> float:
    """Median PPRE of the local cells, clamped to a sane pilot/data ratio.

    When no baseline cells carry PPRE values, we synthesise a value
    ``Max TX - 15 dB`` (matches the current template ratio of 30 → 15.2
    within rounding) — keeps pilot power proportional to data power so
    the cell behaves like everyone else in the area.
    """
    ppres = []
    for c in (baseline_cells_nearby or []):
        v = _pluck(c, _PPRE_KEYS)
        if v is not None:
            ppres.append(v)

    if ppres:
        base = float(median(ppres))
    elif template_default is not None:
        base = float(template_default)
    else:
        base = float(max_tx_dbm) + _DEFAULT_PPRE_OFFSET_DB

    # Enforce a sane pilot/data ratio so the synthesised cell does not
    # become a pilot polluter (PPRE too high) or a pilot ghost
    # (PPRE too low — cell would not be measurable as a neighbour).
    lo = max_tx_dbm + PPRE_GAP_MIN_DB
    hi = max_tx_dbm + PPRE_GAP_MAX_DB
    return round(float(_clamp(base, lo, hi)), 1)
