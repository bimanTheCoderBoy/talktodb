"""
Resolve antenna device, master pattern, SU-MIMO and (NR-only) BeamSet
for each new candidate cell.

Strategy:
  Site-level (no azimuth filter):
    - antenna_device and master_pattern are resolved ONCE per site from the
      nearest baseline cell on the same band (distance only, no azimuth).
    - This ensures all sectors of a candidate site share one antenna device.

  Per-sector (with azimuth filter):
    - All other fields (TAC, ref_signal_ppre, mimo, beamset, etc.) are still
      resolved per-sector using band + azimuth proximity.

  Fallback: most-common device on that band, then empty.
"""
import logging
from typing import Dict, List, Optional, Tuple

from asp_app.services.autogenv2.clustering.placement_service import haversine_km

logger = logging.getLogger(__name__)

_SECTOR_KEYS = (
    "antenna_device", "master_pattern",
    "mimo_tx", "mimo_rx",
    "beamset_iid", "beam_frequency", "beam_gain", "beam_etilt", "beam_angle",
    "auto_calc_method", "primary_model", "primary_model_radius",
    "tac", "ref_signal_ppre",
)

_SITE_LEVEL_KEYS = ("antenna_device", "master_pattern")

_STR_KEYS = ("antenna_device", "master_pattern", "beamset_iid", "auto_calc_method", "primary_model")


def _empty_sector() -> Dict:
    return {k: "" if k in _STR_KEYS else None for k in _SECTOR_KEYS}


def _sector_from_cell(cell: Dict) -> Dict:
    return {k: cell.get(k, "") if k in _STR_KEYS else cell.get(k) for k in _SECTOR_KEYS}


def _angular_distance(a: float, b: float) -> float:
    d = abs((a % 360) - (b % 360))
    return min(d, 360 - d)


def _is_unknown(value: str) -> bool:
    """True if value is empty, None, or contains 'Unknown'."""
    if not value:
        return True
    return "unknown" in value.lower()


def _find_most_common_device(
    baseline_sites: List[Dict], band: str,
) -> Optional[Dict]:
    """Fallback: pick the most frequently used antenna_device on this band."""
    counts: Dict[str, int] = {}
    device_to_cell: Dict[str, Dict] = {}

    for site in baseline_sites:
        for cell in site.get("cells", []):
            if str(cell.get("band", "")) != str(band):
                continue
            dev = cell.get("antenna_device")
            if _is_unknown(dev):
                continue
            counts[dev] = counts.get(dev, 0) + 1
            if dev not in device_to_cell:
                device_to_cell[dev] = cell

    if not counts:
        return None

    best_dev = max(counts, key=counts.get)
    return _sector_from_cell(device_to_cell[best_dev])


def _resolve_site_antenna(
    site_lat: float,
    site_lon: float,
    band: str,
    baseline_sites: List[Dict],
    max_distance_km: float = 5.0,
) -> Tuple[str, str]:
    """Find the nearest baseline cell with matching band (no azimuth filter).

    Returns (antenna_device, master_pattern) for the entire site.
    """
    best_device = ""
    best_pattern = ""
    best_distance = float("inf")

    for site in baseline_sites:
        slat = site.get("latitude")
        slon = site.get("longitude")
        if slat is None or slon is None:
            continue

        d = haversine_km(site_lat, site_lon, slat, slon)
        if d > max_distance_km:
            continue

        for cell in site.get("cells", []):
            if str(cell.get("band", "")) != str(band):
                continue

            dev = cell.get("antenna_device")
            if _is_unknown(dev):
                continue

            pattern = cell.get("master_pattern") or ""
            if _is_unknown(pattern):
                continue

            if d < best_distance:
                best_distance = d
                best_device = dev
                best_pattern = pattern

    return best_device, best_pattern


def resolve_antenna_for_sector(
    site_lat: float,
    site_lon: float,
    sector_azimuth: float,
    band: str,
    baseline_sites: List[Dict],
    max_distance_km: float = 5.0,
    azimuth_tolerance: float = 30.0,
) -> Optional[Dict]:
    """Find the nearest baseline cell with matching band + similar azimuth.

    Used for per-sector fields (TAC, ref_signal_ppre, mimo, beamset, etc.)
    — NOT for antenna_device/master_pattern which are resolved at site level.
    """
    best_match = None
    best_distance = float("inf")

    for site in baseline_sites:
        slat = site.get("latitude")
        slon = site.get("longitude")
        if slat is None or slon is None:
            continue

        d = haversine_km(site_lat, site_lon, slat, slon)
        if d > max_distance_km:
            continue

        for cell in site.get("cells", []):
            if str(cell.get("band", "")) != str(band):
                continue

            cell_az = cell.get("azimuth")
            if cell_az is None:
                continue

            if _angular_distance(sector_azimuth, float(cell_az)) > azimuth_tolerance:
                continue

            if d < best_distance:
                best_distance = d
                best_match = _sector_from_cell(cell)

    return best_match


def resolve_antennas_for_site(
    site_lat: float,
    site_lon: float,
    azimuths: List[float],
    band: str,
    baseline_sites: List[Dict],
    max_distance_km: float = 5.0,
    azimuth_tolerance: float = 30.0,
) -> List[Dict]:
    """
    Resolve antenna + MIMO + beamset for all sectors of a site.

    antenna_device and master_pattern are resolved ONCE per site (nearest
    baseline cell on same band, no azimuth filter). All other sector-level
    fields use azimuth proximity as before.

    Returns list of dicts (one per sector) with keys from ``_SECTOR_KEYS``.
    """
    total_cells = 0
    cells_with_band = 0
    cells_with_device = 0
    for s in baseline_sites:
        for c in s.get("cells", []):
            total_cells += 1
            if str(c.get("band", "")) == str(band):
                cells_with_band += 1
                if c.get("antenna_device"):
                    cells_with_device += 1

    logger.info(
        "antenna_resolver: band=%r | %d total, %d match band, %d have device",
        band, total_cells, cells_with_band, cells_with_device,
    )

    # Site-level: resolve antenna_device + master_pattern (no azimuth)
    site_device, site_pattern = _resolve_site_antenna(
        site_lat, site_lon, band, baseline_sites, max_distance_km,
    )

    # Fallback for site-level antenna
    fallback = _find_most_common_device(baseline_sites, band)
    if not site_device and fallback:
        site_device = fallback.get("antenna_device") or ""
        site_pattern = fallback.get("master_pattern") or ""

    site_ant_source = "nearest(no-az)" if site_device else "fallback" if fallback else "empty"
    logger.info(
        "  site-level antenna [%s]: device=%s | pattern=%s",
        site_ant_source, site_device or "—", site_pattern or "—",
    )

    empty = _empty_sector()

    results: List[Dict] = []
    for sec_idx, az in enumerate(azimuths):
        # Per-sector: resolve other fields with azimuth filter
        match = resolve_antenna_for_sector(
            site_lat, site_lon, az, band, baseline_sites,
            max_distance_km, azimuth_tolerance,
        )
        if match:
            source = "nearest"
            sector = match
        elif fallback:
            source = "fallback(most-common)"
            sector = dict(fallback)
        else:
            source = "empty(no data)"
            sector = dict(empty)

        # Override antenna_device + master_pattern with site-level values
        sector["antenna_device"] = site_device
        sector["master_pattern"] = site_pattern

        results.append(sector)

        logger.info(
            "  sector %d (az=%s°) [%s]: device=%s | pattern=%s | "
            "tac=%s | ref_ppre=%s | auto_calc=%s | model=%s | radius=%s",
            sec_idx + 1, az, source,
            sector.get("antenna_device") or "—",
            sector.get("master_pattern") or "—",
            sector.get("tac") if sector.get("tac") is not None else "—",
            sector.get("ref_signal_ppre") if sector.get("ref_signal_ppre") is not None else "—",
            sector.get("auto_calc_method") or "—",
            sector.get("primary_model") or "—",
            sector.get("primary_model_radius") if sector.get("primary_model_radius") is not None else "—",
        )

    return results
