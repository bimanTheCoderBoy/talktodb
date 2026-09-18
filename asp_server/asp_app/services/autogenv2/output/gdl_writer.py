"""
Generate a GDL XLSX for N candidate sites.

Two modes:
  - Skeleton mode (no centroids): coordinates are (0, 0), PCI/TAC/RSI
    use safe defaults.
  - Located mode (centroids provided): coordinates come from DBSCAN
    centroids, PCI/TAC/RSI come from the project DB. If centroids carry
    ``azimuths`` and ``antenna_info`` (from Step 7), those are used;
    otherwise falls back to fixed [0, 120, 240] grid.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd

from asp_app.config.acss_config import get_acss_config
from asp_app.config.tech_config_resolver import get_tech_config
from asp_app.services.autogenv2.utils.iid_factory import make_autogen_site_iid, make_autogen_cell_iid


SECTORS_PER_SITE = 3
AZIMUTH_GRID_FALLBACK = [0, 120, 240]

_defaults_cache: Dict[str, Dict] = {}


def _load_columns(tech: str) -> List[str]:
    """Load the ordered column list from the tech-specific columns.json."""
    cfg = get_tech_config(tech)
    with open(cfg.columns_path, "r", encoding="utf-8") as f:
        return json.load(f)["required_columns"]


def _get_defaults(tech: str) -> Dict:
    """Load defaults from config/json_config/{lte|nr}/gdl_defaults.json (cached)."""
    if tech not in _defaults_cache:
        cfg = get_tech_config(tech)
        with open(cfg.gdl_defaults_path, "r", encoding="utf-8") as f:
            _defaults_cache[tech] = json.load(f)
    return dict(_defaults_cache[tech])


def generate_gdl(
    n: int,
    tech: str,
    selected_band: str,
    session_id: str,
    seed: int = 0,
    project_name: Optional[str] = None,
    storage_dir: Optional[str] = None,
    centroids: Optional[List[Dict]] = None,
    population_weighted: bool = False,
) -> Tuple[str, List[Dict]]:
    """
    Create an XLSX with N sites x 3 sectors and correct columns.

    When ``centroids`` is provided, coordinates and cluster metadata are
    taken from the DBSCAN output.  Centroids carry ``azimuths``, ``antenna_info``
    (including per-sector TAC, ref_signal_ppre), ``pcis`` (per-site
    collision-free PCIs), and ``rsis`` (per-site incrementing RSI values
    from the 10 km DB scan) from Step 7.

    Returns (out_path, all_sites).
    """
    if storage_dir is None:
        storage_dir = get_acss_config().gdl_storage_dir
    os.makedirs(storage_dir, exist_ok=True)

    columns = _load_columns(tech)
    defaults = _get_defaults(tech)
    label = project_name or "AutoGen"

    is_nr = tech == "NR"
    carrier_col = "Cell: NR: Assigned Carrier" if is_nr else "Cell: LTE: Assigned Carrier"
    mu_carriers_col = "MU Node: NR Carriers" if is_nr else "MU Node: LTE Carriers"
    pci_col = "Cell: NR: PCI ID" if is_nr else "Cell: LTE: PCI ID"
    tac_col = "Cell: NR: TAC" if is_nr else "Cell: LTE: TAC"
    rsi_col = "Cell: NR: First assigned RSI" if is_nr else "Cell: LTE: First assigned RSI"

    has_centroids = centroids is not None and len(centroids) > 0
    tac_default = int(defaults.get(tac_col, 1))
    rsi_fallback_counter = 0

    rows: List[Dict] = []
    all_sites: List[Dict] = []

    for idx in range(n):
        site_iid = make_autogen_site_iid(session_id, seed, idx)
        mu_iid = f"{site_iid}_MU"

        if has_centroids and idx < len(centroids):
            centroid = centroids[idx]
            lat = float(centroid["lat"])
            lon = float(centroid["lon"])
            cluster_size = int(centroid.get("cluster_size", 0))
            site_azimuths = centroid.get("azimuths") or AZIMUTH_GRID_FALLBACK
            site_antenna_info = centroid.get("antenna_info") or []
            site_height = centroid.get("height_m")
            site_max_tx = centroid.get("max_tx_power")
            site_mimo_tx = centroid.get("mimo_tx")
            site_mimo_rx = centroid.get("mimo_rx")
            site_plmn = centroid.get("plmn")
            site_pcis = centroid.get("pcis") or []
            site_rsis = centroid.get("rsis") or []
        else:
            lat, lon = 0.0, 0.0
            cluster_size = 0
            site_azimuths = AZIMUTH_GRID_FALLBACK
            site_antenna_info = []
            site_height = None
            site_max_tx = None
            site_mimo_tx = None
            site_mimo_rx = None
            site_plmn = None
            site_pcis = []
            site_rsis = []

        site_cells = []

        for sector_idx in range(SECTORS_PER_SITE):
            cell_iid = make_autogen_cell_iid(site_iid, sector_idx)
            sector_num = sector_idx + 1
            pci_value = site_pcis[sector_idx] if sector_idx < len(site_pcis) else 0
            if sector_idx < len(site_rsis):
                rsi_value = site_rsis[sector_idx]
            else:
                rsi_fallback_counter += 1
                rsi_value = rsi_fallback_counter

            azimuth = float(site_azimuths[sector_idx]) if sector_idx < len(site_azimuths) else 0.0

            sector_info = site_antenna_info[sector_idx] if sector_idx < len(site_antenna_info) else {}
            ant_device = sector_info.get("antenna_device", "")
            master_pattern = sector_info.get("master_pattern", "")

            row = dict(defaults)

            row["Property: ID"] = site_iid
            row["Property: Location: X Coordinate"] = lon
            row["Property: Location: Y Coordinate"] = lat

            if not row.get("Property: State"):
                row["Property: State"] = label
            if not row.get("Property: Address 1"):
                row["Property: Address 1"] = "Macro"
            if not row.get("Property: Town"):
                row["Property: Town"] = label

            row["Property: Logical Antenna: Index"] = sector_num
            row["Property: Physical Antenna: Index"] = sector_num
            row["Property: Physical Antenna: Azimuth (deg)"] = azimuth

            if ant_device:
                row["Property: Physical Antenna: Antenna Device"] = ant_device
            if master_pattern:
                row["Property: Physical Antenna: Master Patterns: Master Pattern 1"] = master_pattern

            sec_logical_pattern = sector_info.get("logical_pattern")
            if sec_logical_pattern:
                row["Property: Logical Antenna: Pattern"] = sec_logical_pattern

            sec_etilt = sector_info.get("electrical_tilt")
            if sec_etilt is not None:
                row["Property: Logical Antenna: Electrical Tilt (deg)"] = sec_etilt

            if site_height is not None:
                row["Property: Physical Antenna: Height - Inventory (m)"] = site_height

            max_tx_col = "Cell: NR: Max TX Power (dBm)" if is_nr else "Cell: LTE: Max TX Power (dBm)"
            if site_max_tx is not None:
                row[max_tx_col] = site_max_tx

            # SU-MIMO TX/RX elements
            mimo_tx_col = "Cell: NR: SU-MIMO TX Elements" if is_nr else "Cell: LTE: SU-MIMO TX Elements"
            mimo_rx_col = "Cell: NR: SU-MIMO RX Elements" if is_nr else "Cell: LTE: SU-MIMO RX Elements"
            if site_mimo_tx is not None:
                row[mimo_tx_col] = int(site_mimo_tx)
            if site_mimo_rx is not None:
                row[mimo_rx_col] = int(site_mimo_rx)

            # NR BeamSet fields (per-sector from nearest match)
            if is_nr:
                bs_iid = sector_info.get("beamset_iid")
                if bs_iid:
                    row["Cell: BeamSet"] = bs_iid
                bf = sector_info.get("beam_frequency")
                if bf is not None:
                    row["NR BeampatternFrequency"] = bf
                bg = sector_info.get("beam_gain")
                if bg is not None:
                    row["NR BeampatternGain"] = bg
                be = sector_info.get("beam_etilt")
                if be is not None:
                    row["NR BeampatternETilt"] = be
                ba = sector_info.get("beam_angle")
                if ba is not None:
                    row["NR BeampatternAngle"] = ba

            # Power Auto-Calculated Method (per-sector from nearest match)
            auto_calc = sector_info.get("auto_calc_method")
            if auto_calc:
                auto_calc_col = "Cell: NR: Power Auto-Calculated Method" if is_nr else "Cell: LTE: Power Auto-Calculated Method"
                row[auto_calc_col] = auto_calc

            # Primary Prediction Model + Radius (per-sector from nearest match)
            primary_model = sector_info.get("primary_model")
            if primary_model:
                row["Property: Logical Antenna: Primary Prediction: Model"] = primary_model
            primary_radius = sector_info.get("primary_model_radius")
            if primary_radius is not None:
                row["Property: Logical Antenna: Primary Prediction: Radius (km)"] = primary_radius

            # Parent PLMN (site-level from locality)
            if site_plmn:
                row["MU Node: Parent PLMN"] = site_plmn

            row["MU Node: Identity"] = mu_iid
            row[mu_carriers_col] = selected_band
            row["Cell: Identity"] = cell_iid
            row[carrier_col] = selected_band

            row[pci_col] = int(pci_value)

            sector_tac = sector_info.get("tac")
            row[tac_col] = int(sector_tac) if sector_tac is not None else tac_default

            row[rsi_col] = rsi_value

            if not is_nr:
                ref_ppre = sector_info.get("ref_signal_ppre")
                if ref_ppre is not None:
                    row["Cell: LTE: Ref Signal PPRE (dBm)"] = ref_ppre

            rows.append(row)

            site_cells.append({
                "cell_iid": cell_iid,
                "azimuth": azimuth,
                "band": str(selected_band),
                "pci": int(pci_value),
                "technology": "NR" if is_nr else "LTE",
                "selected": True,
                "antenna_device": ant_device,
                "master_pattern": master_pattern,
            })

        site_obj = {
            "site_iid": site_iid,
            "latitude": lat,
            "longitude": lon,
            "technology": ["NR" if is_nr else "LTE"],
            "cells": site_cells,
            "auto_generated": True,
            "covers_poor_bins": cluster_size,
            "seed": seed,
            "population_weighted": population_weighted,
        }
        if population_weighted and has_centroids and idx < len(centroids):
            tw = centroids[idx].get("total_weight")
            if tw is not None:
                site_obj["covers_population"] = int(round(float(tw)))
        all_sites.append(site_obj)

    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = defaults.get(col, "")
    df = df[columns]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{session_id}_{timestamp}_autogenv2.xlsx"
    out_path = os.path.join(storage_dir, filename)
    df.to_excel(out_path, index=False, engine="openpyxl")

    return out_path, all_sites
