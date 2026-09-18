"""
Dominant azimuth-grid detection from baseline-site cells in polygon.

Algorithm: tolerance-based scoring against two canonical 3-sector grids
({0, 120, 240} vs {60, 180, 300}). The grid that has more baseline cells
within ±15° of any of its three azimuths wins. Ties → grid A. Insufficient
data (<3 cells) → fallback grid A.

This is the "ML-derived" approach CONTEXT.md asks for. CONTEXT explicitly
permits starting with this heuristic and upgrading to a real classifier
only if it proves flaky in real data.

Naming note: the function is deliberately named `detect_dominant_azimuth_grid`,
NOT anything with "ml_" in the name. The "ML-derived" label in CONTEXT.md
refers to the class of approach (data-driven, not hand-coded per site), not
to a trained model. Using "ml_" in the name would mislead future readers into
expecting a scikit-learn estimator or similar artefact.
"""
from math import radians, sin, cos, atan2, degrees
from typing import List

GRID_A = [0.0, 120.0, 240.0]
GRID_B = [60.0, 180.0, 300.0]
TOLERANCE_DEG = 15.0


def _angular_distance(a: float, b: float) -> float:
    """Smallest absolute difference on the 0-360 circle."""
    d = abs((a % 360) - (b % 360))
    return min(d, 360 - d)


def _grid_score(azimuths: List[float], grid: List[float]) -> int:
    return sum(
        1 for az in azimuths
        if any(_angular_distance(az, g) <= TOLERANCE_DEG for g in grid)
    )


def detect_dominant_azimuth_grid(cells_in_polygon: List[dict]) -> List[float]:
    """
    cells_in_polygon: list of site dicts in the same shape produced by
    CellsService.get_cells_in_bounds — each site has a "cells" list with
    objects carrying an "azimuth" float field.

    Returns: [az0, az1, az2] — the 3-sector azimuth pattern to apply to
    every auto-generated candidate. Falls back to [0, 120, 240] when
    insufficient baseline data exists.
    """
    azimuths: List[float] = []
    for site in cells_in_polygon or []:
        for cell in site.get("cells", []):
            az = cell.get("azimuth")
            if az is None:
                continue
            try:
                azimuths.append(float(az) % 360)
            except (TypeError, ValueError):
                continue

    if len(azimuths) < 3:
        return list(GRID_A)

    score_a = _grid_score(azimuths, GRID_A)
    score_b = _grid_score(azimuths, GRID_B)
    return list(GRID_B) if score_b > score_a else list(GRID_A)


def bearing_to_centroid(
    site_lat: float, site_lon: float, target_lat: float, target_lon: float
) -> float:
    """
    Initial-bearing in degrees [0, 360) from (site_lat, site_lon) to
    (target_lat, target_lon). Used as the FALLBACK primary azimuth when no
    dominant pattern can be detected. The single returned bearing is then
    expanded to a 3-sector layout by the caller (e.g. [bearing, bearing+120,
    bearing+240] mod 360).
    """
    phi1 = radians(site_lat)
    phi2 = radians(target_lat)
    dlon = radians(target_lon - site_lon)
    y = sin(dlon) * cos(phi2)
    x = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(dlon)
    theta = atan2(y, x)
    return (degrees(theta) + 360.0) % 360.0


AZIMUTH_BIN_DEG = 5  # Operator constraint: every chosen sector lands on a
                     # multiple of 5° (engineering-acceptable resolution —
                     # field crews can't physically aim with sub-5° precision).


def compute_smart_azimuths_per_site(
    site_lat: float,
    site_lon: float,
    poor_bins_nearby: List,
    n_sectors: int = 3,
    min_sep_deg: int = 65,
    smoothing_bins: int = 2,
    weights_nearby: List[float] = None,
) -> List[float]:
    """
    Pick ``n_sectors`` azimuths (each a multiple of 5°) that maximise
    poor-coverage capture from the candidate site, while keeping any two
    beams at least ``min_sep_deg`` apart.

    Algorithm:
      1. Compute the bearing from the site to every poor pixel inside
         its catchment. Build a **5°-bin** histogram (72 bins covering 0..360°).
         Constraining to 5° at this stage guarantees the output is
         operator-actionable — no sub-5° azimuths field crews can't aim at.
      2. Smooth with a rolling sum of ``smoothing_bins`` neighbours each
         side so a peak reflects a small arc, not a single bin.
      3. Greedy peak selection: pick the largest bin, then zero out the
         neighbouring bins within ``min_sep_deg`` so the next pick is
         forced to be at least that far away.

    Falls back to a sensible equispaced grid (still aligned to 5°) when
    there are too few poor pixels to fit the chosen sector count under
    the separation constraint.

    poor_bins_nearby: list of (lat, lon) tuples — the poor pixels the
    auto-gen pipeline already extracted, optionally filtered to those
    within the candidate's catchment radius.
    weights_nearby: per-pixel weight (composite gap-severity × population)
    for the histogram; uniform when None.
    """
    n_bins = 360 // AZIMUTH_BIN_DEG  # 72 bins of 5° each

    def _bin_to_az(bin_idx: int) -> float:
        return float((bin_idx * AZIMUTH_BIN_DEG) % 360)

    # Defensive: empty / undersized input → equispaced fallback, snapped to 5°.
    if not poor_bins_nearby or len(poor_bins_nearby) < n_sectors:
        step_deg = 360.0 / n_sectors
        return [round(((i * step_deg) % 360) / AZIMUTH_BIN_DEG) * AZIMUTH_BIN_DEG
                for i in range(n_sectors)]

    use_weights = weights_nearby is not None and len(weights_nearby) == len(poor_bins_nearby)

    # 5° bins. Weighted increment by composite score (severity × population)
    # so peaks reflect "where do the deep + dense gaps live" rather than
    # "where do I see the most pixels".
    hist = [0.0] * n_bins
    for i, p in enumerate(poor_bins_nearby):
        try:
            b = bearing_to_centroid(site_lat, site_lon, float(p[0]), float(p[1]))
            inc = float(weights_nearby[i]) if use_weights else 1.0
            bin_idx = int((b % 360) / AZIMUTH_BIN_DEG) % n_bins
            hist[bin_idx] += inc
        except (TypeError, ValueError, IndexError):
            continue

    # Rolling-sum smoothing over a ±smoothing_bins window (in 5° units).
    # smoothing_bins=2 → ±10°, comparable to today's ±5° on a finer grid.
    smoothed = [0.0] * n_bins
    for i in range(n_bins):
        s = 0.0
        for off in range(-smoothing_bins, smoothing_bins + 1):
            s += hist[(i + off) % n_bins]
        smoothed[i] = s

    # How many neighbouring 5° bins are at least ``min_sep_deg`` apart?
    # E.g. min_sep_deg=65, AZIMUTH_BIN_DEG=5 → mask 13 bins each side.
    sep_bins = max(1, min_sep_deg // AZIMUTH_BIN_DEG)

    # Greedy peak selection with min-separation mask.
    chosen_bins: List[int] = []
    work = list(smoothed)
    for _ in range(n_sectors):
        peak_bin = max(range(n_bins), key=lambda j: work[j])
        if work[peak_bin] == 0:
            # Histogram exhausted — fill remaining sectors with equispaced
            # offsets from the first chosen bin so the result still has
            # ``n_sectors`` distinct multiples of 5°.
            base = chosen_bins[0] if chosen_bins else 0
            step = n_bins // n_sectors
            for k in range(len(chosen_bins), n_sectors):
                cand = (base + k * step) % n_bins
                while any(_angular_distance(_bin_to_az(cand), _bin_to_az(c)) < min_sep_deg
                          for c in chosen_bins):
                    cand = (cand + 1) % n_bins
                chosen_bins.append(cand)
            break

        chosen_bins.append(peak_bin)
        for off in range(-sep_bins, sep_bins + 1):
            work[(peak_bin + off) % n_bins] = 0

    # Stable ordering for readability in logs / payloads
    return sorted(_bin_to_az(b) for b in chosen_bins)
