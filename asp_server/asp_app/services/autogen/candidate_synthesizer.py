"""
Assemble final candidate site objects from Wave-1 outputs.

Output is a list of dicts in the EXACT shape produced by
SetupService._build_site_objects_from_df (setup_service.py:254). This is
the contract the rest of the ACSS pipeline assumes; matching it means
no downstream branching is needed.

Shape (pinned):
  {
    "site_iid": str,                # AUTO_<hex>_<idx>
    "latitude": float,              # centroid lat (EPSG:4326)
    "longitude": float,             # centroid lon (EPSG:4326)
    "technology": ["LTE"],          # always ["LTE"] for v1
    "cells": [
       {
         "cell_iid": str,           # AUTO_<hex>_<idx>_C<s>
         "azimuth": float,          # from dominant grid
         "band": str,               # str(int) of template band — e.g. "700"
         "pci": int,                # from PCI free-list, distinct per cell
         "technology": "LTE",
         "selected": True,
       }, ...   # 3 cells per site for v1
    ],
    # Auto-gen annotations (read by candidate-review modal in plan 02-09)
    "auto_generated": True,
    "covers_poor_bins": int,        # cluster_size from placement_service
    "seed": int,                    # for replay
    "template_name": str,
    # median_uplift_dB is populated AFTER candidate-coverage runs by plan 02-07
    # (left out here; downstream logic adds it to result_details, not the site dict).
  }
"""
from typing import Dict, List

from asp_app.services.autogen.iid_factory import make_autogen_site_iid, make_autogen_cell_iid

SECTORS_PER_SITE = 3  # v1 fixed; dynamic count is deferred per CONTEXT.md


def synthesize_candidates(
    centroids: List[Dict],          # [{"lat": .., "lon": .., "cluster_size": ..}, ...]
    baseline_sites: List[Dict],     # cellsInPolygon shape (from handoff)
    azimuth_grid: List[float],      # [az0, az1, az2] — 3 entries
    pci_freelist: List[int],
    base_rsi: int,
    nearest_tac: int,
    template_defaults: Dict,        # gdl_defaults from antenna_templates.json
    template_name: str,
    session_id: str,
    seed: int,
) -> List[Dict]:
    """
    Returns the list of synthesized site dicts. PCIs are drawn from the
    free-list left-to-right (idx*3 .. idx*3+2). RSI is incremented from
    base_rsi (base_rsi+1, base_rsi+2, ...) per cell across all sites.

    The `band` is derived from template_defaults["Cell: LTE: Assigned Carrier"]
    (the GDL "Cell: LTE: Assigned Carrier" column) and stringified to match
    the existing parser's type — see SetupService._build_site_objects_from_df
    line 299: `str(int(band_val))`.
    """
    if not centroids:
        return []
    if len(azimuth_grid) != SECTORS_PER_SITE:
        raise ValueError(
            f"azimuth_grid must have {SECTORS_PER_SITE} entries, got {len(azimuth_grid)}"
        )
    needed_pcis = SECTORS_PER_SITE * len(centroids)
    if len(pci_freelist) < needed_pcis:
        # Best-effort: if exhausted, wrap (collisions are tolerated within session
        # because EDS dedupes by full IID, not PCI).
        pci_freelist = list(pci_freelist) + [
            (pci_freelist[-1] + i + 1) % 504 if pci_freelist else i for i in range(needed_pcis)
        ]
    band_str = str(int(template_defaults.get("Cell: LTE: Assigned Carrier", 700)))

    sites: List[Dict] = []
    rsi_counter = base_rsi
    for idx, c in enumerate(centroids):
        site_iid = make_autogen_site_iid(session_id, seed, idx)
        cells: List[Dict] = []
        for s_idx in range(SECTORS_PER_SITE):
            cell_iid = make_autogen_cell_iid(site_iid, s_idx)
            pci = pci_freelist[idx * SECTORS_PER_SITE + s_idx]
            rsi_counter += 1
            cells.append({
                "cell_iid": cell_iid,
                "azimuth": float(azimuth_grid[s_idx]),
                "band": band_str,
                "pci": int(pci),
                "technology": "LTE",
                "selected": True,
                # Per-cell extras for the GDL writer (NOT in the GDL parser's
                # output shape, but harmless extras — the writer reads them by name)
                "_tac": int(nearest_tac),
                "_rsi": int(rsi_counter),
            })
        sites.append({
            "site_iid": site_iid,
            "latitude": float(c["lat"]),
            "longitude": float(c["lon"]),
            "technology": ["LTE"],
            "cells": cells,
            # Auto-gen annotations
            "auto_generated": True,
            "covers_poor_bins": int(c.get("cluster_size", 0)),
            "seed": int(seed),
            "template_name": template_name,
        })
    return sites
