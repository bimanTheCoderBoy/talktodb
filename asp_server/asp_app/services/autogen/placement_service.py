"""
DBSCAN-based placement on poor-bin (lat, lon) pairs.

Pipeline:
  1. cluster_and_pick_centroids(poor_bins, n, eps_km, min_samples, seed)
     → DBSCAN with metric='haversine', algorithm='ball_tree'.
     Returns up to top-N cluster centroids by cluster size, plus the cluster
     size for each centroid (used as `covers_poor_bins` annotation downstream).
  2. apply_spacing_constraints(centroids, baseline_sites,
     min_candidate_spacing_km=0.5, min_from_baseline_km=0.8)
     → drops centroids within 500m of another accepted candidate or 800m of
     any baseline site. Iterates in order so the largest cluster wins.

Determinism: sklearn DBSCAN is deterministic given the same input order. The
`seed` parameter is reserved for the future Regenerate-with-different-seed
feature and is currently used only to permute input ordering when seed != 0.

Coordinate convention:
  Input poor_bins  → [(lat, lon), ...]  (matches poor_bin_extractor output)
  DBSCAN input     → np.radians([[lat, lon], ...])  (haversine in radians)
  Output centroids → [{"lat": float, "lon": float, "cluster_size": int}, ...]

n_jobs note: n_jobs=1 is intentional (not n_jobs=-1). sklearn DBSCAN with
n_jobs=-1 can produce nondeterministic cluster-label ordering on some BLAS
builds, which would break the golden-file test in plan 02-10. The cost of
single-threaded DBSCAN is negligible at expected poor-bin counts (<10k
pixels per polygon at typical BIL resolutions).
"""
from math import radians, sin, cos, sqrt, atan2, atan, degrees
from typing import List, Tuple, Dict

import numpy as np
from sklearn.cluster import DBSCAN, KMeans

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two WGS84 points."""
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * atan2(sqrt(a), sqrt(1 - a))


def cluster_and_pick_centroids(
    poor_bins: List[Tuple[float, float]],
    n: int = 5,
    eps_km: float = 1.0,
    min_samples: int = 10,
    seed: int = 0,
    weights: List[float] = None,
) -> List[Dict]:
    """Run DBSCAN on poor-bin (lat, lon) coords and return top-N cluster centroids.

    poor_bins: [(lat, lon), ...] — in the same order as poor_bin_extractor output.

    seed: 0 means canonical order (deterministic across runs). Non-zero seeds
    permute the input ordering so DBSCAN's first-pass-wins density-tie behaviour
    yields an alternative "Regenerate" placement. The caller increments seed
    on each Regenerate button click.

    n_jobs=1: see module docstring for determinism rationale.

    Returns: [{"lat": float, "lon": float, "cluster_size": int}, ...] of length <= n,
             ordered by cluster_size descending. Empty list if no clusters found
             (i.e. no dense enough regions or too few points).
    """
    if not poor_bins or len(poor_bins) < min_samples:
        return []

    pts = list(poor_bins)
    # Per-pixel weights for population-density-aware ranking. None ⇒ uniform.
    use_weights = weights is not None
    wts = list(weights) if use_weights else [1.0] * len(pts)

    if seed:
        # Deterministic permutation for "Regenerate" alternative placements.
        # seed != 0 → permute input so different first-pass density winners emerge.
        rng = np.random.default_rng(seed)
        idx = rng.permutation(len(pts))
        pts = [pts[i] for i in idx]
        wts = [wts[i] for i in idx]

    # DBSCAN expects radians for haversine metric: shape (k, 2) in [lat, lon] radians
    coords_rad = np.radians(np.asarray(pts))
    eps_rad = eps_km / EARTH_RADIUS_KM

    db = DBSCAN(
        eps=eps_rad,
        min_samples=min_samples,
        metric='haversine',
        algorithm='ball_tree',
        n_jobs=1,  # n_jobs=1: deterministic label ordering (see module docstring)
    ).fit(coords_rad)

    labels = db.labels_
    clusters: Dict[int, List[int]] = {}
    for i, label in enumerate(labels):
        if label >= 0:  # -1 = noise point, skip
            clusters.setdefault(int(label), []).append(i)

    def _summarise_cluster(idxs: List[int]) -> Dict:
        """Build the centroid dict for a list of pts/wts indices.

        Centroid is the **weighted mean** when weights are non-uniform
        (= population centre of mass for the cluster). Both cluster_size
        (pixel count) and total_weight (sum of weights = people covered)
        are recorded — downstream synthesizer carries total_weight into
        the candidate annotation as ``covers_poor_bins``.
        """
        cluster_pts = [pts[i] for i in idxs]
        cluster_wts = [wts[i] for i in idxs]
        total_w = float(sum(cluster_wts))
        if use_weights and total_w > 0:
            lat = sum(p[0] * w for p, w in zip(cluster_pts, cluster_wts)) / total_w
            lon = sum(p[1] * w for p, w in zip(cluster_pts, cluster_wts)) / total_w
        else:
            lat = float(np.mean([p[0] for p in cluster_pts]))
            lon = float(np.mean([p[1] for p in cluster_pts]))
        return {
            "lat": float(lat),
            "lon": float(lon),
            "cluster_size": len(cluster_pts),
            "total_weight": total_w,
        }

    # If DBSCAN finds enough natural hotspots, use them — top-N by total weight
    # (sum of population in cluster) when weights present, by pixel count otherwise.
    if len(clusters) >= n:
        sort_key = (
            (lambda idxs: sum(wts[i] for i in idxs))
            if use_weights
            else (lambda idxs: len(idxs))
        )
        sorted_clusters = sorted(clusters.values(), key=sort_key, reverse=True)
        return [_summarise_cluster(idxs) for idxs in sorted_clusters[:n]]

    # Fewer natural clusters than requested N (typical for small / contiguous
    # poor-coverage polygons where DBSCAN chains every pixel into one giant
    # cluster). Force-partition the poor pixels into N groups via KMeans so
    # the user always gets the N candidate sites they asked for. KMeans uses
    # raw lat/lon — fine at N≤10 polygon scales, where the haversine vs
    # Euclidean error inside a single market is negligible for centroid
    # placement. Population weights are passed via sample_weight so KMeans
    # pulls partition centres toward dense areas instead of geometric mean.
    if len(pts) < n:
        # Pathological case: fewer poor pixels than requested clusters.
        # Return one cluster per pixel as the best we can do.
        return [
            {"lat": float(p[0]), "lon": float(p[1]), "cluster_size": 1, "total_weight": float(w)}
            for p, w in zip(pts, wts)
        ]

    coords = np.asarray(pts)  # shape (M, 2) → (lat, lon)
    sample_weight = np.asarray(wts, dtype=float) if use_weights else None
    km = KMeans(
        n_clusters=n,
        random_state=int(seed) if seed else 42,
        n_init=10,
    ).fit(coords, sample_weight=sample_weight)
    km_clusters: Dict[int, List[int]] = {}
    for i, label in enumerate(km.labels_):
        km_clusters.setdefault(int(label), []).append(i)
    sort_key = (
        (lambda idxs: sum(wts[i] for i in idxs))
        if use_weights
        else (lambda idxs: len(idxs))
    )
    sorted_km = sorted(km_clusters.values(), key=sort_key, reverse=True)
    return [_summarise_cluster(idxs) for idxs in sorted_km]


def _snap_to_available(value: float, available_tilts: List[float]) -> float:
    """Closest entry in ``available_tilts``; ties resolve to the larger value
    (prefer more aggressive downtilt — over-tilting still covers the target
    with a tighter ring, under-tilting risks missing it)."""
    best = available_tilts[0]
    best_d = abs(value - best)
    for t in available_tilts[1:]:
        d = abs(value - t)
        if d < best_d or (d == best_d and t > best):
            best = t
            best_d = d
    return float(best)


def compute_smart_tilt(
    site_lat: float,
    site_lon: float,
    poor_bins_nearby: List,
    height_m: float,
    tilt_min: float = 2.0,
    tilt_max: float = 11.0,
    default: float = None,
    weights_nearby: List[float] = None,
    available_tilts: List[float] = None,
    target_percentile: float = 85.0,
) -> float:
    """
    Geometry-derived per-site electrical tilt.

    Tilt formula:  ``optimal_tilt = atan(height_m / target_distance_m)``
    where target_distance is the **90th-percentile** distance (in metres)
    from the candidate site to the nearby poor pixels. The 90th percentile
    is robust against outlier far pixels that would otherwise drag tilt to
    near 0° (over-flat beam).

    When ``weights_nearby`` is provided, the percentile is computed on the
    **weighted** CDF of distances — i.e. "the distance below which 90% of
    the *people* are", not "the distance below which 90% of the pixels
    are". This makes tilt actually serve the population the auto-gen step
    is trying to cover.

    When ``available_tilts`` is supplied (from the operator-uploaded tilt
    mapping CSV — see ``services.autogen.tilt_mapping``), the geometry-
    derived value is **snapped to the closest tilt the antenna actually
    supports**. This is what keeps the GDL ``Electrical Tilt (deg)`` row
    in sync with the beam-pattern UID stamped on the same site — EDS
    rejects payloads where the two disagree.

    When ``available_tilts`` is empty/None, the legacy continuous clamp
    to ``[tilt_min, tilt_max]`` is used instead.

    Falls back to ``default`` (or the midpoint of [tilt_min, tilt_max] if
    no default is provided) when there are too few poor pixels to compute
    a meaningful percentile.
    """
    if default is None:
        default = (tilt_min + tilt_max) / 2.0

    snap = available_tilts is not None and len(available_tilts) > 0

    def _finalize(v: float) -> float:
        if snap:
            return _snap_to_available(v, available_tilts)
        return float(max(tilt_min, min(tilt_max, round(v, 1))))

    if not poor_bins_nearby or len(poor_bins_nearby) < 3:
        return _finalize(default)

    use_weights = weights_nearby is not None and len(weights_nearby) == len(poor_bins_nearby)

    pairs: List[Tuple[float, float]] = []  # (distance_m, weight)
    for i, p in enumerate(poor_bins_nearby):
        try:
            d = haversine_km(site_lat, site_lon, float(p[0]), float(p[1])) * 1000.0
            w = float(weights_nearby[i]) if use_weights else 1.0
            pairs.append((d, w))
        except (TypeError, ValueError, IndexError):
            continue

    if not pairs:
        return _finalize(default)

    # ``target_percentile`` is the percentile of the (weighted) distance
    # distribution at which the antenna should aim. Higher percentile →
    # farther target → lower tilt → broader coverage. The RF brain picks
    # the percentile from the operator's goal: aggressive goals want to
    # push energy farther (higher percentile, lower tilt); conservative
    # goals concentrate energy nearer (lower percentile, steeper tilt).
    q = max(1.0, min(99.0, float(target_percentile)))
    q_frac = q / 100.0

    if use_weights:
        # Weighted percentile over distance. Sort by distance; walk the
        # cumulative weight until we cross q_frac * total_weight.
        pairs.sort(key=lambda dw: dw[0])
        total_w = sum(w for _, w in pairs)
        if total_w <= 0.0:
            # All weights zero → fall through to unweighted percentile
            target_d_m = float(np.percentile([d for d, _ in pairs], q))
        else:
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
        # All pixels essentially co-located → max tilt to focus down
        return _finalize(tilt_max)

    tilt = degrees(atan(float(height_m) / target_d_m))
    return _finalize(tilt)


def apply_spacing_constraints(
    centroids: List[Dict],
    baseline_sites: List[Dict],
    min_candidate_spacing_km: float = 0.5,
    min_from_baseline_km: float = 0.8,
) -> List[Dict]:
    """Filter centroids by minimum spacing constraints.

    centroids: output of cluster_and_pick_centroids (ordered by cluster_size desc).
    baseline_sites: list of dicts with "latitude" and "longitude" float fields
                    (same shape as DB site rows from the existing candidate services).

    Constraints:
      1. Min distance from any baseline site: min_from_baseline_km (default 800m).
         Avoids co-locating auto-generated candidates with existing infrastructure.
      2. Min distance between accepted candidates: min_candidate_spacing_km (default 500m).
         Ensures geographic spread among generated candidates.

    Iteration order: centroids arrive pre-sorted by cluster_size descending, so
    the largest (densest) cluster always wins when two centroids conflict.
    Per CONTEXT.md: "drop any centroid violating either constraint and pull the
    next-largest cluster centroid in" — this implementation does exactly that
    because the list is pre-sorted.

    Returns: subset of centroids satisfying both constraints, preserving
             the descending-size order.
    """
    accepted: List[Dict] = []
    for c in centroids:
        # Constraint 1: min distance from any baseline site >= 800m
        too_close_to_baseline = any(
            haversine_km(c["lat"], c["lon"], s["latitude"], s["longitude"])
            < min_from_baseline_km
            for s in baseline_sites
            if s.get("latitude") is not None and s.get("longitude") is not None
        )
        if too_close_to_baseline:
            continue

        # Constraint 2: min distance from any already-accepted candidate >= 500m
        too_close_to_accepted = any(
            haversine_km(c["lat"], c["lon"], a["lat"], a["lon"])
            < min_candidate_spacing_km
            for a in accepted
        )
        if too_close_to_accepted:
            continue

        accepted.append(c)
    return accepted
