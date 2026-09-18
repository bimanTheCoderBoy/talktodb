"""
DBSCAN-based placement on poor-bin (lat, lon) pairs.

Pipeline:
  1. cluster_and_pick_centroids  → DBSCAN (haversine / ball_tree),
     top-N by composite weight, KMeans fallback when fewer natural clusters.
  2. apply_spacing_constraints   → drop centroids too close to baseline
     sites or to each other.

Coordinate convention:
  Input   → [(lat, lon), ...]
  DBSCAN  → np.radians([[lat, lon], ...])
  Output  → [{"lat": float, "lon": float, "cluster_size": int}, ...]
"""
from math import radians, sin, cos, sqrt, atan2
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
    """Run DBSCAN on poor-bin coords and return top-N cluster centroids.

    Returns [{"lat", "lon", "cluster_size", "total_weight"}, ...] ordered
    by weight/size descending.  Empty list when no clusters found.
    """
    if not poor_bins or len(poor_bins) < min_samples:
        return []

    pts = list(poor_bins)
    use_weights = weights is not None
    wts = list(weights) if use_weights else [1.0] * len(pts)

    if seed:
        rng = np.random.default_rng(seed)
        idx = rng.permutation(len(pts))
        pts = [pts[i] for i in idx]
        wts = [wts[i] for i in idx]

    coords_rad = np.radians(np.asarray(pts))
    eps_rad = eps_km / EARTH_RADIUS_KM

    db = DBSCAN(
        eps=eps_rad,
        min_samples=min_samples,
        metric='haversine',
        algorithm='ball_tree',
        n_jobs=1,
    ).fit(coords_rad)

    labels = db.labels_
    clusters: Dict[int, List[int]] = {}
    for i, label in enumerate(labels):
        if label >= 0:
            clusters.setdefault(int(label), []).append(i)

    def _summarise(idxs: List[int]) -> Dict:
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

    if len(clusters) >= n:
        sort_key = (
            (lambda idxs: sum(wts[i] for i in idxs))
            if use_weights
            else (lambda idxs: len(idxs))
        )
        sorted_clusters = sorted(clusters.values(), key=sort_key, reverse=True)
        return [_summarise(idxs) for idxs in sorted_clusters[:n]]

    # KMeans fallback
    if len(pts) < n:
        return [
            {"lat": float(p[0]), "lon": float(p[1]), "cluster_size": 1, "total_weight": float(w)}
            for p, w in zip(pts, wts)
        ]

    coords = np.asarray(pts)
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
    return [_summarise(idxs) for idxs in sorted_km]


def apply_spacing_constraints(
    centroids: List[Dict],
    baseline_sites: List[Dict],
    min_candidate_spacing_km: float = 0.5,
    min_from_baseline_km: float = 0.8,
) -> List[Dict]:
    """Filter centroids by minimum spacing constraints.

    Largest clusters win when two centroids conflict (input is pre-sorted
    by weight/size descending).
    """
    accepted: List[Dict] = []
    for c in centroids:
        too_close_to_baseline = any(
            haversine_km(c["lat"], c["lon"], s["latitude"], s["longitude"])
            < min_from_baseline_km
            for s in baseline_sites
            if s.get("latitude") is not None and s.get("longitude") is not None
        )
        if too_close_to_baseline:
            continue

        too_close_to_accepted = any(
            haversine_km(c["lat"], c["lon"], a["lat"], a["lon"])
            < min_candidate_spacing_km
            for a in accepted
        )
        if too_close_to_accepted:
            continue

        accepted.append(c)
    return accepted
