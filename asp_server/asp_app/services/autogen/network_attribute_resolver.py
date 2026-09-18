"""
Project DB queries to derive per-candidate network attributes:
  - PCI free-list (avoid collisions with baseline cells in polygon)
  - Nearest-baseline TAC (inherit TAC from closest existing site)
  - Polygon-max RSI (auto-incremented from existing maximum)

All queries use the SAME RLS-aware session pattern as
services/cells_service.py — they MUST go through get_rls_db_session, NOT
get_db_session, per RESEARCH.md Pitfall 7.

Schema discovery: the cell_lte column names for PCI/TAC/RSI are not all
self-evidently named (pipeline/db/models.py is commented out, see
RESEARCH.md Open Question 3). The PCI column is confirmed by
cells_service.py:CELLS_QUERY:

    c.lte_carrierparameters_physicalcellid

For TAC and RSI we run an introspection query at first call and cache the
results. The candidate column names tried (in order of likelihood) are:

    TAC : lte_carrierparameters_trackingareacode
          lte_tac
          tac
    RSI : lte_carrierparameters_rootsequenceindex
          lte_rsi
          rsi

If none of the candidate columns exist, the resolver returns sensible
defaults (TAC=1, RSI=polygon_max_known + 1 with offset baked in by
caller) and logs a warning so a human can wire the correct names later.

This soft-fallback is deliberate: per CONTEXT.md these annotations are
nice-to-have for the V1 release, and blocking the entire auto-gen feature
on a missing column name is worse than producing default values.
"""
import logging
from typing import List, Optional, Tuple

from shapely.geometry import Point, Polygon as ShapelyPolygon
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Cached column-name resolution per project DB. Keyed by repr(engine).
_TAC_COLUMN_CACHE: dict = {}
_RSI_COLUMN_CACHE: dict = {}

TAC_CANDIDATES = [
    "lte_carrierparameters_trackingareacode",
    "lte_tac",
    "tac",
]
RSI_CANDIDATES = [
    "lte_carrierparameters_rootsequenceindex",
    "lte_rsi",
    "rsi",
]
PCI_COLUMN = "lte_carrierparameters_physicalcellid"  # confirmed in cells_service.py


async def _resolve_column(db: AsyncSession, candidates: List[str], cache: dict) -> Optional[str]:
    """information_schema lookup in cell_lte, cached per engine.

    Uses the engine's url as cache key so multi-project deployments don't
    cross-pollute. Returns None if no candidate column exists.
    """
    engine_key = str(db.bind.url) if db.bind is not None else "unknown"
    if engine_key in cache:
        return cache[engine_key]
    for col in candidates:
        result = await db.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'cell_lte' AND column_name = :col LIMIT 1"
        ), {"col": col})
        if result.scalar_one_or_none() is not None:
            cache[engine_key] = col
            return col
    cache[engine_key] = None
    logger.warning(
        f"network_attribute_resolver: no column from {candidates} found in cell_lte; "
        "falling back to defaults"
    )
    return None


async def build_pci_freelist(
    db: AsyncSession, polygon_coords: List[List[float]],
) -> List[int]:
    """
    Returns a sorted list of PCI integers in [0, 503] that are NOT used by
    any baseline cell whose location falls inside the given polygon.

    polygon_coords: [[lon, lat], ...] (EPSG:4326). cell_lte has no geometry
    column on this schema; we mirror cells_service.CELLS_QUERY by joining to
    the `location` table on `location_iid` and applying polygon containment
    in Python via Shapely.
    """
    poly = ShapelyPolygon(polygon_coords)

    result = await db.execute(text(f"""
        SELECT c.{PCI_COLUMN} AS pci, loc.latitude, loc.longitude
        FROM cell_lte c
        LEFT JOIN (
            SELECT DISTINCT ON (iid) iid, latitude, longitude
            FROM location
            WHERE imported_at = (SELECT MAX(imported_at) FROM location)
        ) loc ON loc.iid = c.location_iid
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
          AND c.{PCI_COLUMN} IS NOT NULL
          AND loc.latitude IS NOT NULL AND loc.longitude IS NOT NULL
    """))

    used = set()
    for pci, lat, lon in result.all():
        if pci is None:
            continue
        pt = Point(float(lon), float(lat))
        if poly.contains(pt) or poly.touches(pt):
            used.add(int(pci))

    return [pci for pci in range(0, 504) if pci not in used]


async def nearest_baseline_tac(
    db: AsyncSession, candidate_lat: float, candidate_lon: float,
    baseline_sites: List[dict],
) -> int:
    """
    Returns the TAC of the baseline site geometrically closest to the
    candidate position. baseline_sites comes from setup_state and carries
    cell_iid only — so we look up TAC in the DB by joining on the cell_iid
    list.

    Falls back to TAC=1 if no resolvable column or no baseline cells.

    Note: cells_service.py:CELLS_QUERY confirms the cell_lte primary identity
    column is `cell_iid` (not `iid`). The lookup below uses `cell_iid = ANY(:iids)`.
    """
    if not baseline_sites:
        return 1

    tac_col = await _resolve_column(db, TAC_CANDIDATES, _TAC_COLUMN_CACHE)
    if tac_col is None:
        return 1

    # Find the closest baseline site by haversine
    from asp_app.services.autogen.placement_service import haversine_km
    best: Optional[Tuple[float, dict]] = None
    for site in baseline_sites:
        if site.get("latitude") is None or site.get("longitude") is None:
            continue
        d = haversine_km(candidate_lat, candidate_lon, site["latitude"], site["longitude"])
        if best is None or d < best[0]:
            best = (d, site)
    if best is None:
        return 1

    cell_iids = [c.get("cell_iid") for c in best[1].get("cells", []) if c.get("cell_iid")]
    if not cell_iids:
        return 1

    # cell_iid is the confirmed identity column in cell_lte (per cells_service.py:CELLS_QUERY)
    result = await db.execute(text(
        f"SELECT {tac_col} FROM cell_lte WHERE cell_iid = ANY(:iids) AND {tac_col} IS NOT NULL LIMIT 1"
    ), {"iids": cell_iids})
    row = result.scalar_one_or_none()
    return int(row) if row is not None else 1


async def polygon_max_rsi(
    db: AsyncSession, polygon_coords: List[List[float]],
) -> int:
    """
    Returns max(RSI) among baseline cells in the polygon. The synthesiser
    will increment from this value (max + 1, max + 2, ...) per new cell.

    Uses the same JOIN pattern as cells_service.CELLS_QUERY (cell_lte has no
    geometry column on this schema; polygon containment is evaluated in
    Python via Shapely). Returns 0 if no resolvable column or no rows fall
    inside the polygon.
    """
    rsi_col = await _resolve_column(db, RSI_CANDIDATES, _RSI_COLUMN_CACHE)
    if rsi_col is None:
        return 0

    poly = ShapelyPolygon(polygon_coords)

    result = await db.execute(text(f"""
        SELECT c.{rsi_col} AS rsi, loc.latitude, loc.longitude
        FROM cell_lte c
        LEFT JOIN (
            SELECT DISTINCT ON (iid) iid, latitude, longitude
            FROM location
            WHERE imported_at = (SELECT MAX(imported_at) FROM location)
        ) loc ON loc.iid = c.location_iid
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
          AND c.{rsi_col} IS NOT NULL
          AND loc.latitude IS NOT NULL AND loc.longitude IS NOT NULL
    """))

    max_rsi = 0
    for rsi, lat, lon in result.all():
        if rsi is None:
            continue
        pt = Point(float(lon), float(lat))
        if poly.contains(pt) or poly.touches(pt):
            max_rsi = max(max_rsi, int(rsi))
    return max_rsi
