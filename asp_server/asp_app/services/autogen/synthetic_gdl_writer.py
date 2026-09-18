"""
Write synthesized candidate sites to a 40-column GDL CSV file under
GDL_STORAGE_DIR, so the existing CREATING_CANDIDATES pipeline step
(which reads from setup_state["loadCandidateGdl"]["filePath"]) works
unchanged for auto-generated sessions.

Per RESEARCH.md Pitfall 3 and Pattern 8: writing the CSV is the chosen
integration approach (over patching execution_service.py to skip the
file-load path). Reason: the EDS payload builders (LocationService,
MUService, CellService) all read from a GDL file on disk via
ExcelColumnValidator.validate_excel_columns + pd.read_excel. Writing
the synthetic CSV means zero downstream branches.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from asp_app.config.acss_config import get_acss_config, get_candidate_config

_COLUMNS_JSON_FALLBACK = str(
    Path(__file__).resolve().parent.parent.parent / "config" / "json_config" / "lte" / "columns.json"
)


def _load_required_columns() -> List[str]:
    """Load the 40-column list from the config, with fallback to canonical path."""
    config_path = get_candidate_config().columns_config_path
    if not os.path.exists(config_path):
        config_path = os.path.normpath(_COLUMNS_JSON_FALLBACK)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)["required_columns"]


def _avg_baseline_height(baseline_sites: List[Dict], template_default: float) -> float:
    """Average Property Antenna Height across baseline sites; fall back to template default.

    Kept for backwards-compat. New callers should use compute_smart_height,
    which adds goal-awareness and uses the median (more outlier-robust).
    """
    heights = []
    for s in baseline_sites or []:
        h = s.get("antenna_height_m") or s.get("height")
        if h is not None:
            try:
                heights.append(float(h))
            except (TypeError, ValueError):
                continue
    if not heights:
        return float(template_default)
    return float(sum(heights) / len(heights))


def compute_smart_height(
    baseline_sites: List[Dict],
    bias_m: float = 5.0,
    template_default: float = 15.0,
    bound_min: float = 10.0,
    bound_max: float = 50.0,
) -> float:
    """Antenna height = median(baseline) + bias, clamped.

    - Base value = **median** of nearby baseline-site heights (robust to
      outliers — one tall guyed tower won't skew the result).
    - ``bias_m`` is the aggression-indexed lift above the median. The RF
      brain selects this value from the operator's goal (see
      ``services.autogen.rf_brain.HEIGHT_BIAS_M``): a 5 m baseline lift
      always applies on top of the local infrastructure, with more for
      aggressive ``increase_rsrp`` targets.
    - Falls back to ``template_default`` when no nearby baseline sites
      have a usable height field.
    - Final value clamped to [``bound_min``, ``bound_max``] m to avoid
      pathological extremes when bad data slips through.
    """
    heights = []
    for s in baseline_sites or []:
        h = s.get("antenna_height_m") or s.get("height")
        if h is None:
            continue
        try:
            heights.append(float(h))
        except (TypeError, ValueError):
            continue

    if not heights:
        base = float(template_default)
    else:
        base = float(np.median(heights))

    return float(max(bound_min, min(bound_max, base + float(bias_m))))


def write_synthetic_gdl_csv(
    sites: List[Dict],
    baseline_sites: List[Dict],
    template_defaults: Dict,
    template_name: str,
    session_id: str,
    storage_dir: str = None,
    electrical_tilt_override: float = None,
    smart_height: float = None,
    project_name: str = None,
) -> str:
    """
    Materialize sites as a 40-column XLSX and return the absolute path.

    The output filename pattern matches the existing upload_gdl convention:
      {session_id}_{timestamp}_autogen.xlsx

    Per-cell smart values (when present on the cell dict) override their
    corresponding template defaults:
      cell["azimuth"]                       → Property: Physical Antenna: Azimuth (deg)
      cell["_electrical_tilt_deg"]          → Property: Logical Antenna: Electrical Tilt (deg)
                                              (per-site smart tilt; if absent, uses
                                               function-level electrical_tilt_override
                                               or the template default)
      cell["_height_m"]                     → Property: Physical Antenna: Height - Inventory (m)
                                              (per-site smart height; if absent, uses
                                               function-level smart_height arg or
                                               template default)

    Empty fields in the template (State, Address 1, Town) are populated
    with project-derived placeholders so the GDL preview never shows
    blanks — matches the manual-upload XLSX shape the customer is used to.
    """
    if storage_dir is None:
        storage_dir = get_acss_config().gdl_storage_dir
    os.makedirs(storage_dir, exist_ok=True)

    columns = _load_required_columns()
    height_default = template_defaults.get("Property: Physical Antenna: Height - Inventory (m)", 15)
    # Function-level fallback height when individual cells don't carry one.
    # `smart_height` takes precedence over the legacy avg_baseline_height.
    if smart_height is not None:
        avg_height = float(smart_height)
    else:
        avg_height = _avg_baseline_height(baseline_sites, height_default)

    # Project-derived placeholders for descriptive fields the customer's
    # manual XLSX always populates (State="Jersey", Address 1="Macro",
    # Town="Jersey-1" in their reference file). Using project_name keeps
    # them session-specific without needing more user input.
    bvid = project_name or "AutoGen"

    rows: List[Dict] = []
    for site in sites:
        for s_idx, cell in enumerate(site["cells"]):
            row = dict(template_defaults)  # start with template-provided defaults
            sector_index = s_idx + 1  # 1, 2, 3 for sectors A, B, C

            # ---- Identifiers / location ----
            row["Property: ID"] = site["site_iid"]
            row["Property: Location: X Coordinate"] = site["longitude"]
            row["Property: Location: Y Coordinate"] = site["latitude"]

            # ---- Always-populate the descriptive fields the template leaves blank ----
            # Empty strings in the template would surface as blank cells in
            # the GDL preview; replace with project-derived placeholders so
            # downstream readers and the operator both see meaningful values.
            if not row.get("Property: State"):
                row["Property: State"] = bvid
            if not row.get("Property: Address 1"):
                row["Property: Address 1"] = "Macro"
            if not row.get("Property: Town"):
                row["Property: Town"] = bvid

            # ---- Antenna indexes (must be unique within a location — EDS
            # LocationObjectv214Type rejects payloads where physicalAntennas[].index
            # or logicalAntennas[].index repeats across sectors of the same site
            # with autoCreatePhsAnt/LogAnt=true).
            row["Property: Logical Antenna: Index"] = sector_index
            row["Property: Physical Antenna: Index"] = sector_index

            # ---- Per-cell smart values (if present) ----
            row["Property: Physical Antenna: Azimuth (deg)"] = cell["azimuth"]
            # Per-site height takes precedence over the function-level value.
            row["Property: Physical Antenna: Height - Inventory (m)"] = float(
                cell.get("_height_m", avg_height)
            )
            # Tilt resolution order:
            #   per-cell smart tilt (cell["_electrical_tilt_deg"])
            #     → function-level user override (electrical_tilt_override)
            #     → template default (already in row from dict(template_defaults))
            cell_tilt = cell.get("_electrical_tilt_deg")
            if cell_tilt is not None:
                row["Property: Logical Antenna: Electrical Tilt (deg)"] = float(cell_tilt)
            elif electrical_tilt_override is not None:
                row["Property: Logical Antenna: Electrical Tilt (deg)"] = float(electrical_tilt_override)

            # Per-cell beam-pattern override. When the operator has uploaded
            # a tilt-mapping CSV and the auto-gen step resolved this site's
            # smart tilt to a specific beam-pattern UID, the antenna device
            # + master pattern + logical pattern columns all flip to the
            # resolved UID. This is what keeps the GDL row internally
            # consistent (Antenna Device's intrinsic ELEC_TILT matches the
            # Electrical Tilt row above) — EDS rejects payloads otherwise.
            resolved_uid = cell.get("_resolved_template_name")
            if resolved_uid:
                row["Property: Physical Antenna: Antenna Device"] = resolved_uid
                row["Property: Physical Antenna: Master Patterns: Master Pattern 1"] = resolved_uid
                row["Property: Logical Antenna: Pattern"] = resolved_uid

            # Per-cell smart power. Per-site Max TX / PPRE inherit from the
            # nearby baseline cells (median) + goal-aware bias + legal-range
            # clamp — see services.autogen.power_planner. Falls back to the
            # template default when the cell does not carry a smart value.
            cell_max_tx = cell.get("_max_tx_dbm")
            if cell_max_tx is not None:
                row["Cell: LTE: Max TX Power (dBm)"] = float(cell_max_tx)
            cell_ppre = cell.get("_ppre_dbm")
            if cell_ppre is not None:
                row["Cell: LTE: Ref Signal PPRE (dBm)"] = float(cell_ppre)

            # ---- MU / Cell identifiers + RAN attributes ----
            row["MU Node: Identity"] = f"{site['site_iid']}_MU"
            row["Cell: Identity"] = cell["cell_iid"]
            row["Cell: LTE: PCI ID"] = int(cell["pci"])
            row["Cell: LTE: TAC"] = int(cell.get("_tac", template_defaults.get("Cell: LTE: TAC", 1)))
            row["Cell: LTE: First assigned RSI"] = int(cell.get("_rsi", 0))
            rows.append(row)

    # Build a DataFrame with columns in EXACT order from columns.json. Any
    # column missing from a row is filled from the template; if even the
    # template lacks it, fall back to the project name (not empty) so the
    # GDL preview never surfaces blank cells.
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            fallback = template_defaults.get(col)
            df[col] = fallback if fallback not in (None, "") else bvid
    # Backfill any leftover empty values per column (some template entries
    # are intentionally empty strings — e.g. "Property: State": ""). Use
    # the template default first, project name as last resort.
    for col in columns:
        col_fallback = template_defaults.get(col)
        if col_fallback in (None, ""):
            col_fallback = bvid
        df[col] = df[col].apply(
            lambda v: col_fallback if (v is None or (isinstance(v, str) and v == "")) else v
        )
    df = df[columns]  # reorder + drop extras

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    # Write XLSX (not CSV) so the existing GDL validator's pd.read_excel() works.
    # The manual upload path validates with pd.read_excel which auto-detects xlsx
    # but cannot determine engine for raw CSV. Using openpyxl explicitly.
    filename = f"{session_id}_{timestamp}_autogen.xlsx"
    out_path = os.path.join(storage_dir, filename)
    df.to_excel(out_path, index=False, engine="openpyxl")
    return out_path
