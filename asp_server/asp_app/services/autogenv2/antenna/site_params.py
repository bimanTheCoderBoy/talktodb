"""
Per-site height, Max TX Power, and SU-MIMO TX/RX derived from nearby
baseline cells.

All use the same pattern: collect values from baseline cells within a
search radius, take the median, apply an optional bias, and clamp to
a safe range.  Falls back to a template default when no baseline data
is available.
"""
import logging
from math import atan, atan2, degrees, radians, cos, sin
from statistics import median
from typing import Dict, List, Optional, Tuple

import numpy as np

from asp_app.services.autogenv2.clustering.placement_service import haversine_km

logger = logging.getLogger(__name__)

HEIGHT_MIN_M = 10.0
HEIGHT_MAX_M = 50.0
HEIGHT_BIAS_M = 5.0
HEIGHT_DEFAULT_M = 15.0

MAX_TX_MIN_DBM = 23.0
MAX_TX_MAX_DBM = 46.0
MAX_TX_DEFAULT_DBM = 30.0

MIMO_DEFAULT_TX = 4
MIMO_DEFAULT_RX = 4


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def compute_site_height(
    site_lat: float,
    site_lon: float,
    baseline_sites: List[Dict],
    max_distance_km: float = 5.0,
    bias_m: float = HEIGHT_BIAS_M,
    default_m: float = HEIGHT_DEFAULT_M,
) -> float:
    """Median antenna height of nearby baseline cells + bias, clamped.

    Searches all baseline cells within max_distance_km, collects their
    antenna_height values, and returns median + bias.  Falls back to
    default_m when no heights are found.
    """
    heights: List[float] = []

    for site in baseline_sites:
        slat = site.get("latitude")
        slon = site.get("longitude")
        if slat is None or slon is None:
            continue
        if haversine_km(site_lat, site_lon, slat, slon) > max_distance_km:
            continue
        for cell in site.get("cells", []):
            h = cell.get("antenna_height")
            if h is None:
                continue
            try:
                heights.append(float(h))
            except (TypeError, ValueError):
                continue

    base = float(median(heights)) if heights else float(default_m)
    result = _clamp(base + float(bias_m), HEIGHT_MIN_M, HEIGHT_MAX_M)
    logger.info(
        "compute_site_height: found %d heights nearby → median=%.1f + bias=%.1f = %.1f%s",
        len(heights), base, bias_m, result,
        " (using default)" if not heights else "",
    )
    return result


def compute_site_max_tx(
    site_lat: float,
    site_lon: float,
    band: str,
    baseline_sites: List[Dict],
    max_distance_km: float = 5.0,
    default_dbm: float = MAX_TX_DEFAULT_DBM,
) -> float:
    """Median Max TX Power of nearby same-band baseline cells, clamped.

    Filters to cells on the same band within max_distance_km, takes the
    median of their max_tx_power values.  Falls back to default_dbm.
    """
    powers: List[float] = []

    for site in baseline_sites:
        slat = site.get("latitude")
        slon = site.get("longitude")
        if slat is None or slon is None:
            continue
        if haversine_km(site_lat, site_lon, slat, slon) > max_distance_km:
            continue
        for cell in site.get("cells", []):
            if str(cell.get("band", "")) != str(band):
                continue
            p = cell.get("max_tx_power")
            if p is None:
                continue
            try:
                powers.append(float(p))
            except (TypeError, ValueError):
                continue

    base = float(median(powers)) if powers else float(default_dbm)
    result = _clamp(base, MAX_TX_MIN_DBM, MAX_TX_MAX_DBM)
    logger.info(
        "compute_site_max_tx: band=%r, found %d powers nearby → median=%.1f → %.1f%s",
        band, len(powers), base, result,
        " (using default)" if not powers else "",
    )
    return result


def compute_site_mimo(
    site_lat: float,
    site_lon: float,
    band: str,
    baseline_sites: List[Dict],
    max_distance_km: float = 5.0,
    default_tx: int = MIMO_DEFAULT_TX,
    default_rx: int = MIMO_DEFAULT_RX,
) -> Tuple[int, int]:
    """Median SU-MIMO TX/RX elements from nearby same-band baseline cells.

    Returns (mimo_tx, mimo_rx) as integers.
    """
    tx_vals: List[int] = []
    rx_vals: List[int] = []

    for site in baseline_sites:
        slat = site.get("latitude")
        slon = site.get("longitude")
        if slat is None or slon is None:
            continue
        if haversine_km(site_lat, site_lon, slat, slon) > max_distance_km:
            continue
        for cell in site.get("cells", []):
            if str(cell.get("band", "")) != str(band):
                continue
            tx = cell.get("mimo_tx")
            rx = cell.get("mimo_rx")
            if tx is not None:
                try:
                    tx_vals.append(int(tx))
                except (TypeError, ValueError):
                    pass
            if rx is not None:
                try:
                    rx_vals.append(int(rx))
                except (TypeError, ValueError):
                    pass

    result_tx = int(median(tx_vals)) if tx_vals else default_tx
    result_rx = int(median(rx_vals)) if rx_vals else default_rx
    logger.info(
        "compute_site_mimo: band=%r, found %d tx / %d rx nearby → tx=%d rx=%d%s",
        band, len(tx_vals), len(rx_vals), result_tx, result_rx,
        " (default)" if not tx_vals and not rx_vals else "",
    )
    return result_tx, result_rx


PLMN_DEFAULT = "PLMN0"


def compute_site_plmn(
    site_lat: float,
    site_lon: float,
    baseline_sites: List[Dict],
    max_distance_km: float = 5.0,
    default_plmn: str = PLMN_DEFAULT,
) -> str:
    """Most-common PLMN from nearby baseline cells.

    Picks the PLMN that appears most frequently among cells within
    max_distance_km.  Falls back to default_plmn.
    """
    counts: Dict[str, int] = {}

    for site in baseline_sites:
        slat = site.get("latitude")
        slon = site.get("longitude")
        if slat is None or slon is None:
            continue
        if haversine_km(site_lat, site_lon, slat, slon) > max_distance_km:
            continue
        for cell in site.get("cells", []):
            plmn = cell.get("plmn")
            if plmn:
                counts[plmn] = counts.get(plmn, 0) + 1

    if not counts:
        logger.info("compute_site_plmn: no PLMN data nearby, using default=%s", default_plmn)
        return default_plmn

    result = max(counts, key=counts.get)
    logger.info(
        "compute_site_plmn: found %d values, most common=%s (count=%d)",
        sum(counts.values()), result, counts[result],
    )
    return result


PCI_MAX_LTE = 503
PCI_MAX_NR = 1007


def pick_collision_free_pcis(
    n_sectors: int,
    tech: str,
    db_used_pcis: set,
    already_assigned: Optional[set] = None,
) -> List[int]:
    """Pick *n_sectors* PCIs that collide with neither baseline cells nor
    previously assigned candidate sites.

    ``db_used_pcis`` comes from the 10 km radius DB query
    (``CellsService.get_nearby_pci_rsi``).  ``already_assigned`` tracks PCIs
    given to earlier candidate sites in this pipeline run.

    LTE range: 0-503, NR range: 0-1007.
    """
    pci_max = PCI_MAX_NR if tech == "NR" else PCI_MAX_LTE
    prev_count = len(already_assigned) if already_assigned else 0
    used: set = set(db_used_pcis)
    if already_assigned:
        used |= already_assigned

    picked: List[int] = []
    for candidate in range(0, pci_max + 1):
        if candidate not in used:
            picked.append(candidate)
            used.add(candidate)
            if len(picked) == n_sectors:
                break

    if len(picked) < n_sectors:
        for filler in range(0, pci_max + 1):
            if filler not in set(picked):
                picked.append(filler)
                if len(picked) == n_sectors:
                    break

    logger.info(
        "pick_collision_free_pcis [%s]: %d DB PCIs + %d prev-assigned = %d blocked | "
        "assigned %s (range 0-%d)",
        tech, len(db_used_pcis), prev_count, len(used) - len(picked),
        picked, pci_max,
    )
    return picked


# ── Collision-free RSI assignment (band-scoped) ───────────────────────

RSI_MAX_LTE = 839
RSI_MAX_NR_LONG = 837   # L_RA = 839 (long preamble)
RSI_MAX_NR_SHORT = 137  # L_RA = 139 (short preamble)


def _detect_nr_rsi_range(db_used_rsis: set) -> int:
    """Auto-detect NR RSI range from existing cell values.

    If any existing RSI exceeds 137, the network uses long preamble (max 837).
    Otherwise assume short preamble (max 137).
    """
    if not db_used_rsis:
        return RSI_MAX_NR_LONG
    max_existing = max(db_used_rsis)
    if max_existing > RSI_MAX_NR_SHORT:
        return RSI_MAX_NR_LONG
    return RSI_MAX_NR_SHORT


def pick_collision_free_rsis(
    n_sectors: int,
    tech: str,
    db_used_rsis: set,
    already_assigned: Optional[set] = None,
) -> List[int]:
    """Pick *n_sectors* RSIs that don't collide with same-band cells or
    previously assigned candidate sites.

    ``db_used_rsis`` comes from the 10 km radius DB query filtered by band.
    ``already_assigned`` tracks RSIs given to earlier candidate sites.

    LTE range: 0-839.
    NR range: auto-detected from existing values (0-137 or 0-837).
    """
    if tech == "NR":
        rsi_max = _detect_nr_rsi_range(db_used_rsis)
    else:
        rsi_max = RSI_MAX_LTE

    prev_count = len(already_assigned) if already_assigned else 0
    used: set = set(db_used_rsis)
    if already_assigned:
        used |= already_assigned

    picked: List[int] = []
    for candidate in range(0, rsi_max + 1):
        if candidate not in used:
            picked.append(candidate)
            used.add(candidate)
            if len(picked) == n_sectors:
                break

    if len(picked) < n_sectors:
        for filler in range(0, rsi_max + 1):
            if filler not in set(picked):
                picked.append(filler)
                if len(picked) == n_sectors:
                    break

    logger.info(
        "pick_collision_free_rsis [%s]: %d DB RSIs + %d prev-assigned = %d blocked | "
        "assigned %s (range 0-%d)",
        tech, len(db_used_rsis), prev_count, len(used) - len(picked),
        picked, rsi_max,
    )
    return picked


# ── Geometry-derived electrical tilt (per-sector) ─────────────────────

ETILT_MIN = 0.0
ETILT_MAX = 15.0
ETILT_DEFAULT = 6.0
ETILT_PERCENTILE = 85.0
SECTOR_HALF_WIDTH = 60.0


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from (lat1,lon1) to (lat2,lon2) in degrees [0,360)."""
    rlat1, rlon1 = radians(lat1), radians(lon1)
    rlat2, rlon2 = radians(lat2), radians(lon2)
    dlon = rlon2 - rlon1
    x = sin(dlon) * cos(rlat2)
    y = cos(rlat1) * sin(rlat2) - sin(rlat1) * cos(rlat2) * cos(dlon)
    return (degrees(atan2(x, y)) + 360.0) % 360.0


def _in_sector(bearing: float, sector_az: float, half_width: float) -> bool:
    diff = abs((bearing - sector_az + 180.0) % 360.0 - 180.0)
    return diff <= half_width


def compute_sector_etilt(
    site_lat: float,
    site_lon: float,
    sector_azimuth: float,
    height_m: float,
    nearby_poor: List,
    weights: Optional[List[float]] = None,
    sector_half_width: float = SECTOR_HALF_WIDTH,
    tilt_min: float = ETILT_MIN,
    tilt_max: float = ETILT_MAX,
    default: float = ETILT_DEFAULT,
    target_percentile: float = ETILT_PERCENTILE,
) -> float:
    """Per-sector electrical tilt: ``atan(height / target_distance)``.

    Only poor pixels whose bearing from the site falls within
    ``sector_azimuth ± sector_half_width`` are considered.

    ``target_distance`` is the weighted ``target_percentile``-th percentile
    of those distances.

    Returns a value clamped to ``[tilt_min, tilt_max]``, rounded to 1 dp.
    Falls back to ``default`` when too few sector pixels are available.
    """
    use_weights = weights is not None and len(weights) == len(nearby_poor)
    pairs: List[Tuple[float, float]] = []
    for i, p in enumerate(nearby_poor):
        try:
            plat, plon = float(p[0]), float(p[1])
            bearing = _bearing_deg(site_lat, site_lon, plat, plon)
            if not _in_sector(bearing, sector_azimuth, sector_half_width):
                continue
            d = haversine_km(site_lat, site_lon, plat, plon) * 1000.0
            w = float(weights[i]) if use_weights else 1.0
            pairs.append((d, w))
        except (TypeError, ValueError, IndexError):
            continue

    if len(pairs) < 3:
        result = round(max(tilt_min, min(tilt_max, default)), 1)
        logger.info(
            "compute_sector_etilt(az=%.0f°): %d pixels in sector → default=%.1f°",
            sector_azimuth, len(pairs), result,
        )
        return result

    q = max(1.0, min(99.0, float(target_percentile)))

    if use_weights:
        pairs.sort(key=lambda dw: dw[0])
        total_w = sum(w for _, w in pairs)
        if total_w <= 0.0:
            target_d_m = float(np.percentile([d for d, _ in pairs], q))
        else:
            q_frac = q / 100.0
            target = q_frac * total_w
            cum = 0.0
            target_d_m = pairs[-1][0]
            for d, w in pairs:
                cum += w
                if cum >= target:
                    target_d_m = d
                    break
    else:
        target_d_m = float(np.percentile([d for d, _ in pairs], q))

    if target_d_m < 1.0:
        tilt = tilt_max
    else:
        tilt = degrees(atan(float(height_m) / target_d_m))

    result = round(max(tilt_min, min(tilt_max, tilt)), 1)
    logger.info(
        "compute_sector_etilt(az=%.0f°): height=%.1fm, target_dist=%.0fm, "
        "raw=%.2f° → clamped=%.1f° (%d pixels in sector)",
        sector_azimuth, height_m,
        target_d_m if target_d_m >= 1.0 else 0.0,
        tilt if target_d_m >= 1.0 else tilt_max,
        result, len(pairs),
    )
    return result
