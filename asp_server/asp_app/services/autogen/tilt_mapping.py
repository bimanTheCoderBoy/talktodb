"""
Operator-uploaded ``tilt → beam-pattern`` mapping.

Why this exists
---------------
Each antenna device exported from ASSET carries a fixed set of
beam-pattern UNIQUE-IDs — one per (band, electrical tilt) combination.
For ERICSSON_AIR3237_B78K_P the UID scheme is, for example,
``ERICSSON_AIR3237_B78K_P\\07_70`` = band 07 (787 MHz), 7° tilt.

The geometry-derived smart tilt produced by
``placement_service.compute_smart_tilt`` is *continuous* (e.g. 6.4°).
EDS rejects payloads where the antenna device's intrinsic ELEC_TILT
does not equal the GDL row's ``Logical Antenna: Electrical Tilt (deg)``.
So auto-gen has to snap the continuous value to one the device actually
supports — and rewrite the antenna device / master pattern / pattern
fields to point at the matching beam-pattern UID.

The mapping the engineer uploads is the source of truth for this snap.
We deliberately do **not** parse vendor antenna XMLs at runtime — those
files vary in schema between vendors and exports, and the customer's
operations team already curates the legal (band, tilt, pattern) set.
A 3-column CSV is the smallest shared contract.

File format
-----------
CSV with a header row, comma-separated::

    band_code,tilt_deg,beam_pattern_name
    07,2.0,ERICSSON_AIR3237_B78K_P\\07_20
    07,2.5,ERICSSON_AIR3237_B78K_P\\07_25
    07,7.0,ERICSSON_AIR3237_B78K_P\\07_70
    07,10.0,ERICSSON_AIR3237_B78K_P\\07_100
    18,3.0,ERICSSON_AIR3237_B78K_P\\18_30

* ``band_code`` is a string (preserves any leading zero — ``07`` ≠ ``7``).
* ``tilt_deg`` is float; rows are keyed by this value inside a band.
* Duplicate (band, tilt) rows: last one wins, with a warning logged.

Path is :func:`config.acss_config.get_tilt_mapping_path`; override the
location with the ``TILT_MAPPING_CSV_PATH`` env var.

Module API
----------
* :func:`load_tilt_mapping` — returns
  ``{band_code: {tilt_deg: beam_pattern_name}}``. Cached.
* :func:`get_available_tilts(band)` — sorted list of tilts the band supports.
* :func:`resolve_uid(band, tilt)` — exact UID for a known (band, tilt);
  ``None`` when absent.
* :func:`snap_tilt(band, desired)` — closest available tilt; ``None`` if
  the band has no entries.
* :func:`resolve_snapped(band, desired)` —
  ``(uid, snapped_tilt)`` tuple, or ``None`` if the band is empty.
* :func:`reload_tilt_mapping` — busts the cache (called by the upload
  endpoint after the file is overwritten).
"""
from __future__ import annotations

import csv
import logging
import os
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from asp_app.config.acss_config import get_tilt_mapping_path

logger = logging.getLogger(__name__)


REQUIRED_COLUMNS = ("band_code", "tilt_deg", "beam_pattern_name")
# Optional fourth column. Present in the seed CSV so callers can apply a
# half-VBW correction to geometry-derived tilts (the main lobe peak hits
# the target, not the beam edge). Missing values fall back to ``None``
# and the caller skips the correction.
VBW_COLUMN = "vertical_bw_deg"


class _Entry:
    """One mapping row: the beam-pattern UID plus optional vertical-beamwidth."""

    __slots__ = ("uid", "vbw")

    def __init__(self, uid: str, vbw: Optional[float] = None):
        self.uid = uid
        self.vbw = vbw


def _parse_csv(path: str) -> Dict[str, Dict[float, _Entry]]:
    """Parse the CSV into ``{band_code: {tilt_deg: _Entry}}``."""
    result: Dict[str, Dict[float, _Entry]] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"Tilt mapping CSV {path} has no header row")
        headers = [h.strip() for h in reader.fieldnames]
        missing = [c for c in REQUIRED_COLUMNS if c not in headers]
        if missing:
            raise ValueError(
                f"Tilt mapping CSV {path} missing required column(s): {missing}. "
                f"Expected header: {','.join(REQUIRED_COLUMNS)}"
            )
        has_vbw = VBW_COLUMN in headers
        for row_num, row in enumerate(reader, start=2):  # data starts at line 2
            band = (row.get("band_code") or "").strip()
            tilt_raw = (row.get("tilt_deg") or "").strip()
            uid = (row.get("beam_pattern_name") or "").strip()
            vbw_raw = (row.get(VBW_COLUMN) or "").strip() if has_vbw else ""
            if not band or not tilt_raw or not uid:
                if any((band, tilt_raw, uid)):
                    logger.warning(
                        "Tilt mapping %s line %d: incomplete row "
                        "(band=%r tilt=%r uid=%r) — skipped",
                        path, row_num, band, tilt_raw, uid,
                    )
                continue
            try:
                tilt = float(tilt_raw)
            except ValueError:
                logger.warning(
                    "Tilt mapping %s line %d: tilt_deg=%r is not a number — skipped",
                    path, row_num, tilt_raw,
                )
                continue
            vbw: Optional[float] = None
            if vbw_raw:
                try:
                    vbw = float(vbw_raw)
                except ValueError:
                    logger.warning(
                        "Tilt mapping %s line %d: vertical_bw_deg=%r is not a number — ignored",
                        path, row_num, vbw_raw,
                    )
            band_map = result.setdefault(band, {})
            if tilt in band_map and band_map[tilt].uid != uid:
                logger.warning(
                    "Tilt mapping %s line %d: duplicate (band=%s, tilt=%s°) — "
                    "%r overrides %r",
                    path, row_num, band, tilt, uid, band_map[tilt].uid,
                )
            band_map[tilt] = _Entry(uid, vbw)
    return result


@lru_cache(maxsize=1)
def load_tilt_mapping() -> Dict[str, Dict[float, _Entry]]:
    """Return the cached ``{band_code: {tilt_deg: _Entry}}`` index.

    Returns an empty dict when the CSV is absent — caller falls back to
    continuous-clamped tilt (no beam-pattern rewriting). This is the
    "no mapping uploaded yet" state on a fresh install.
    """
    path = get_tilt_mapping_path()
    if not os.path.exists(path):
        logger.info("Tilt mapping CSV not present at %s — auto-gen will use continuous tilt clamp", path)
        return {}
    try:
        index = _parse_csv(path)
    except (OSError, ValueError) as e:
        logger.error("Failed to load tilt mapping %s: %s", path, e)
        return {}

    if not index:
        logger.warning("Tilt mapping %s parsed but produced 0 rows", path)
        return index

    bands = sorted(index.keys())
    total = sum(len(v) for v in index.values())
    logger.info(
        "Loaded tilt mapping from %s: %d bands (%s), %d (band,tilt) entries",
        path, len(bands), ",".join(bands), total,
    )
    return index


def reload_tilt_mapping() -> Dict[str, Dict[float, _Entry]]:
    """Force-rebuild the cached mapping. Called by the upload endpoint
    after the file is replaced or deleted."""
    load_tilt_mapping.cache_clear()
    return load_tilt_mapping()


def get_known_bands() -> List[str]:
    """All band codes present in the current mapping, sorted."""
    return sorted(load_tilt_mapping().keys())


def get_available_tilts(band_code: str) -> List[float]:
    """Sorted electrical tilts the named band supports per the uploaded mapping.

    Returns ``[]`` when the band is absent — caller falls back to the
    continuous tilt-range clamp.
    """
    band_map = load_tilt_mapping().get(band_code, {})
    return sorted(band_map.keys())


def resolve_uid(band_code: str, tilt_deg: float) -> Optional[str]:
    """Exact UID for ``(band, tilt)``. ``None`` if the mapping has no
    entry for that pair (caller should snap first)."""
    entry = load_tilt_mapping().get(band_code, {}).get(float(tilt_deg))
    return entry.uid if entry else None


def get_vbw(band_code: str, tilt_deg: float) -> Optional[float]:
    """Vertical beamwidth (deg) for the named (band, tilt) entry.

    Returns ``None`` when:
      * the band/tilt pair is not in the mapping, or
      * the operator-uploaded CSV did not include the optional
        ``vertical_bw_deg`` column.

    Callers use this to apply a **half-VBW correction** to the geometry-
    derived tilt so the antenna's main-lobe peak (not its −3 dB edge)
    points at the score-weighted target distance. Without the correction
    half the beam energy lands short of the gap.
    """
    entry = load_tilt_mapping().get(band_code, {}).get(float(tilt_deg))
    return entry.vbw if entry else None


def get_band_vbw_mean(band_code: str) -> Optional[float]:
    """Mean VBW across all tilts in a band — useful as a pre-snap correction
    (the snap target is unknown at the time we add the VBW bias).

    Returns ``None`` when the band has no VBW data at all (legacy CSVs
    uploaded before the ``vertical_bw_deg`` column was introduced)."""
    band_map = load_tilt_mapping().get(band_code, {})
    vbws = [e.vbw for e in band_map.values() if e.vbw is not None]
    if not vbws:
        return None
    return sum(vbws) / len(vbws)


def snap_tilt(band_code: str, desired_tilt_deg: float) -> Optional[float]:
    """Round ``desired_tilt_deg`` to the nearest tilt the band supports.

    Ties (``|desired-a| == |desired-b|``) resolve to the **larger** value
    — prefer more aggressive downtilt because over-tilting still hits
    the target with a tighter ring, whereas under-tilting risks missing
    it entirely.

    Returns ``None`` when the band has no entries (caller falls back).
    """
    tilts = get_available_tilts(band_code)
    if not tilts:
        return None
    best = tilts[0]
    best_d = abs(desired_tilt_deg - best)
    for t in tilts[1:]:
        d = abs(desired_tilt_deg - t)
        if d < best_d or (d == best_d and t > best):
            best = t
            best_d = d
    return float(best)


def resolve_snapped(
    band_code: str, desired_tilt_deg: float
) -> Optional[Tuple[str, float]]:
    """Return ``(uid, snapped_tilt)`` for the closest tilt the band carries.
    ``None`` when the band has no mapping entries.
    """
    snapped = snap_tilt(band_code, desired_tilt_deg)
    if snapped is None:
        return None
    uid = resolve_uid(band_code, snapped)
    if uid is None:
        return None
    return uid, snapped


def dump_mapping() -> Dict[str, Dict[str, str]]:
    """JSON-friendly view of the current mapping for ``GET /setup/tilt-mapping``.

    Tilt keys are stringified so the JSON response uses string keys
    (``{"07": {"7.0": "..."}}``), which JS clients parse cleanly.
    """
    return {
        band: {str(tilt): entry.uid for tilt, entry in sorted(tilts.items())}
        for band, tilts in load_tilt_mapping().items()
    }
