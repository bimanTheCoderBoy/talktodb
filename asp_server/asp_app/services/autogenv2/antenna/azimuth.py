"""
Per-site azimuth selection via weighted bearing histogram.

Algorithm:
  1. Compute bearing from candidate site to each poor-coverage pixel
     within a catchment radius.
  2. Build a 5-degree-bin histogram (72 bins over 0..360), weighted by
     composite severity x population so deeper/denser gaps attract sectors.
  3. Smooth with a rolling window to treat narrow arcs as single peaks.
  4. Greedy peak selection with minimum angular separation between sectors.

Output azimuths are always multiples of 5 degrees (field crews cannot
aim with sub-5-degree precision).
"""
from math import atan2, cos, degrees, radians, sin
from typing import List, Optional


AZIMUTH_BIN_DEG = 5
_N_BINS = 360 // AZIMUTH_BIN_DEG  # 72


def _angular_distance(a: float, b: float) -> float:
    """Smallest absolute difference on the 0-360 circle."""
    d = abs((a % 360) - (b % 360))
    return min(d, 360 - d)


def bearing_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing in degrees [0, 360) from point 1 to point 2."""
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dlon = radians(lon2 - lon1)
    y = sin(dlon) * cos(phi2)
    x = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(dlon)
    return (degrees(atan2(y, x)) + 360.0) % 360.0


def compute_site_azimuths(
    site_lat: float,
    site_lon: float,
    poor_bins_nearby: List,
    weights: Optional[List[float]] = None,
    n_sectors: int = 3,
    min_sep_deg: int = 65,
    smoothing_bins: int = 2,
) -> List[float]:
    """
    Pick n_sectors azimuths (multiples of 5 deg) that maximise poor-coverage
    capture while enforcing minimum angular separation.

    Args:
        site_lat, site_lon: candidate site coordinates.
        poor_bins_nearby: list of (lat, lon) tuples within catchment.
        weights: per-pixel weight (severity x population). None = uniform.
        n_sectors: number of sectors (default 3).
        min_sep_deg: minimum degrees between any two chosen azimuths.
        smoothing_bins: half-width of rolling-sum window (in 5-deg bins).

    Returns:
        Sorted list of n_sectors azimuths, each a multiple of 5.
    """

    def _bin_to_az(bin_idx: int) -> float:
        return float((bin_idx * AZIMUTH_BIN_DEG) % 360)

    if not poor_bins_nearby or len(poor_bins_nearby) < n_sectors:
        step = 360.0 / n_sectors
        return [
            round(((i * step) % 360) / AZIMUTH_BIN_DEG) * AZIMUTH_BIN_DEG
            for i in range(n_sectors)
        ]

    use_weights = weights is not None and len(weights) == len(poor_bins_nearby)

    hist = [0.0] * _N_BINS
    for i, p in enumerate(poor_bins_nearby):
        try:
            b = bearing_between(site_lat, site_lon, float(p[0]), float(p[1]))
            inc = float(weights[i]) if use_weights else 1.0
            bin_idx = int((b % 360) / AZIMUTH_BIN_DEG) % _N_BINS
            hist[bin_idx] += inc
        except (TypeError, ValueError, IndexError):
            continue

    # Rolling-sum smoothing
    smoothed = [0.0] * _N_BINS
    for i in range(_N_BINS):
        s = 0.0
        for off in range(-smoothing_bins, smoothing_bins + 1):
            s += hist[(i + off) % _N_BINS]
        smoothed[i] = s

    sep_bins = max(1, min_sep_deg // AZIMUTH_BIN_DEG)

    # Greedy peak selection with separation mask
    chosen_bins: List[int] = []
    work = list(smoothed)

    for _ in range(n_sectors):
        peak_bin = max(range(_N_BINS), key=lambda j: work[j])
        if work[peak_bin] == 0:
            base = chosen_bins[0] if chosen_bins else 0
            step = _N_BINS // n_sectors
            for k in range(len(chosen_bins), n_sectors):
                cand = (base + k * step) % _N_BINS
                while any(
                    _angular_distance(_bin_to_az(cand), _bin_to_az(c)) < min_sep_deg
                    for c in chosen_bins
                ):
                    cand = (cand + 1) % _N_BINS
                chosen_bins.append(cand)
            break

        chosen_bins.append(peak_bin)
        for off in range(-sep_bins, sep_bins + 1):
            work[(peak_bin + off) % _N_BINS] = 0

    return sorted(_bin_to_az(b) for b in chosen_bins)
