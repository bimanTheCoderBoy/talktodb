"""
Optimized audit flow — compares OSS CSV data against the PostgreSQL cell_lte /
cell_nr tables, producing two output artefacts:

    comparisons_<ts>.csv   — every field check  (MATCH + MISMATCH)
    discrepancies_<ts>.csv — only MISMATCH rows

Key optimizations over the original pipeline/flows/audit_flow.py:
    - SELECT only the ~14 columns needed instead of SELECT * (~200 columns)
    - Vectorized index building via set_index + to_dict (no iterrows)
    - Merge-based comparison instead of double nested Python loop
    - Column-level normalisation via pandas ops instead of per-value function
    - Numeric conversion limited to columns that participate in the audit
    - No DDL execution (read-only operation)
    - Proper connection management (context-managed connections)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from pipeline_app.core.config import AuditColumnMapping, PipelineConfig
from pipeline_app.core.logging_service import LoggingService
from pipeline_app.db.engine import DatabaseManager
from pipeline_app.db.models.discrepancy import Discrepancy
from pipeline_app.db.repository import BATCH_SIZE, PG_MAX_PARAMS, _normalize_rows
from pipeline_app.etl.flows.discrepancy import _df_to_db_records

logger = LoggingService.get_logger(__name__)

_VALID_TABLES = frozenset({"cell_lte", "cell_nr"})

_RESULT_COLUMNS = [
    "cellName", "ENODEB NAME", "column", "oss_value", "db_value",
    "location_eid", "cell_eid", "technology", "status", "checked_at",
]

_YES = frozenset({"yes", "true", "1"})
_NO = frozenset({"no", "false", "0"})

_TECH_CONFIG: Dict[str, Dict[str, Any]] = {
    "LTE": {
        "db_table": "cell_lte",
        "oss_cell_name_col": "LTE Cell Name",
        "db_cell_name_col": "iid",
        "db_tech_value": "LTE",
        "column_mapping": AuditColumnMapping.get_default_mappings(),
    },
    "NR": {
        "db_table": "cell_nr",
        "oss_cell_name_col": "NR Cell Name",
        "db_cell_name_col": "iid",
        "db_tech_value": "NR",
        "column_mapping": AuditColumnMapping.get_default_mappings_nr(),
    },
}

# ---------------------------------------------------------------------------
# DB fetch — selective columns only
# ---------------------------------------------------------------------------

def _fetch_db_columns(
    engine,
    table_name: str,
    columns: list[str],
    *,
    export_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Fetch only the required columns from a DB table.

    Validates table_name against a strict allowlist.
    Optionally writes a CSV snapshot for audit trail.
    """
    if table_name not in _VALID_TABLES:
        raise ValueError(f"Invalid table: {table_name}")

    col_csv = ", ".join(columns)
    with engine.connect() as conn:
        df = pd.read_sql(text(f"SELECT {col_csv} FROM {table_name}"), conn)

    if export_path is not None:
        export_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(export_path, index=False)
        logger.info("Exported %d rows → %s", len(df), export_path)

    logger.info("Fetched %d rows × %d cols from %s", len(df), len(columns), table_name)
    return df


# ---------------------------------------------------------------------------
# OSS CSV discovery
# ---------------------------------------------------------------------------

def _detect_technology(filename: str) -> Optional[str]:
    lower = filename.lower()
    if any(kw in lower for kw in ("4g", "lte")):
        return "LTE"
    if any(kw in lower for kw in ("5g", "nr")):
        return "NR"
    return None


def _find_oss_csvs(directory: Path) -> Dict[str, Path]:
    result: Dict[str, Path] = {}
    if not directory.exists():
        return result
    for f in sorted(directory.glob("*.csv")):
        tech = _detect_technology(f.name)
        if tech:
            result[tech] = f
            logger.info("Detected OSS CSV  %-3s → %s", tech, f.name)
        else:
            logger.warning("Skipping unrecognised CSV: %s", f.name)
    return result


# ---------------------------------------------------------------------------
# Normalisation — column-level vectorized
# ---------------------------------------------------------------------------

def _normalise_series(series: pd.Series) -> pd.Series:
    """Coerce an entire column to canonical comparable form.

    Handles: NaN → None, bool strings, numeric strings.
    Operates on whole columns via pandas vectorised ops instead of
    the per-value try/except approach used in the old pipeline.
    """
    s = series.copy()
    s = s.where(s.notna(), None)

    mask_notnull = s.notna()
    if not mask_notnull.any():
        return s

    str_vals = s[mask_notnull].astype(str).str.strip().str.lower()

    bool_map = {v: True for v in _YES} | {v: False for v in _NO}
    mapped_bools = str_vals.map(bool_map)
    bool_mask = mapped_bools.notna()
    s.loc[bool_mask[bool_mask].index] = mapped_bools[bool_mask]

    remaining_idx = str_vals.index.difference(bool_mask[bool_mask].index)
    if len(remaining_idx) > 0:
        remaining_vals = s[remaining_idx]
        numeric = pd.to_numeric(remaining_vals, errors="coerce")
        numeric_mask = numeric.notna()
        s.loc[numeric_mask[numeric_mask].index] = numeric[numeric_mask]

        str_idx = remaining_idx.difference(numeric_mask[numeric_mask].index)
        if len(str_idx) > 0:
            s.loc[str_idx] = str_vals.reindex(str_idx)

    return s


def _to_numeric_column(series: pd.Series) -> pd.Series:
    """Attempt numeric conversion on a single column (for CSV loading)."""
    converted = pd.to_numeric(series, errors="coerce")
    return converted.where(converted.notna(), series)


# ---------------------------------------------------------------------------
# Comparison engine — merge-based
# ---------------------------------------------------------------------------

def _compare_technology(
    oss_df: pd.DataFrame,
    db_df: pd.DataFrame,
    technology: str,
    oss_cell_name_col: str,
    db_cell_name_col: str,
    column_mapping: Dict[str, str],
    timestamp: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare OSS rows against DB rows for one technology using a vectorised merge.

    Returns (comparisons_df, discrepancies_df).
    """
    empty = pd.DataFrame(columns=_RESULT_COLUMNS)

    oss = oss_df.copy()
    db = db_df.copy()

    # Build join keys
    oss["_key"] = oss[oss_cell_name_col].astype(str).str.strip().str.lower()
    db["_key"] = db[db_cell_name_col].astype(str).str.strip().str.lower()
    db = db.drop_duplicates(subset="_key", keep="last")

    # Log cells present in OSS but absent from DB
    missing_mask = ~oss["_key"].isin(db["_key"])
    missing_count = int(missing_mask.sum())
    if missing_count:
        missing_names = oss.loc[missing_mask, oss_cell_name_col].tolist()
        for name in missing_names[:50]:
            logger.warning("[%s] Cell NOT in DB (skipping): '%s'", technology, name)
        if missing_count > 50:
            logger.warning("[%s] ... and %d more missing cells", technology, missing_count - 50)

    # Select only columns needed for the merge
    oss_cols = [c for c in [oss_cell_name_col, "_key", "ENODEB NAME"] + list(column_mapping.keys()) if c in oss.columns]
    db_cols = [c for c in ["_key", "location_eid", "cell_eid", "eid"] + list(column_mapping.values()) if c in db.columns]

    # Deduplicate column lists
    oss_cols = list(dict.fromkeys(oss_cols))
    db_cols = list(dict.fromkeys(db_cols))

    merged = oss[oss_cols].merge(db[db_cols], on="_key", how="inner")
    matched_count = len(merged)
    logger.info("[%s] Cells matched=%d  missing=%d", technology, matched_count, missing_count)

    if merged.empty:
        return empty, empty.copy()

    # Context columns
    merged["cellName"] = merged[oss_cell_name_col].astype(str).str.strip()
    merged["enodeb_name"] = merged["ENODEB NAME"].astype(str).str.strip() if "ENODEB NAME" in merged.columns else ""
    merged["cell_eid_resolved"] = merged["cell_eid"].where(merged["cell_eid"].notna(), merged.get("eid"))

    # Unpivot: one chunk per mapped column pair, then concat
    chunks: list[pd.DataFrame] = []
    for oss_col, db_col in column_mapping.items():
        if oss_col not in merged.columns or db_col not in merged.columns:
            logger.warning("[%s] Column missing from data: oss=%s db=%s", technology, oss_col, db_col)
            continue

        oss_norm = _normalise_series(merged[oss_col])
        db_norm = _normalise_series(merged[db_col])

        # Vectorised match: both None → MATCH, equal values → MATCH
        both_none = oss_norm.isna() & db_norm.isna()
        equal_vals = oss_norm == db_norm
        status = pd.Series("MISMATCH", index=merged.index)
        status[both_none | equal_vals] = "MATCH"

        chunk = pd.DataFrame({
            "cellName": merged["cellName"],
            "ENODEB NAME": merged["enodeb_name"],
            "column": oss_col,
            "oss_value": oss_norm,
            "db_value": db_norm,
            "location_eid": merged["location_eid"],
            "cell_eid": merged["cell_eid_resolved"],
            "technology": technology,
            "status": status,
            "checked_at": timestamp,
        })
        chunks.append(chunk)

    if not chunks:
        return empty, empty.copy()

    comparisons_df = pd.concat(chunks, ignore_index=True)
    discrepancies_df = comparisons_df[comparisons_df["status"] == "MISMATCH"].copy()

    logger.info("[%s] total_checks=%d  mismatches=%d", technology, len(comparisons_df), len(discrepancies_df))
    return comparisons_df, discrepancies_df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_audit(
    db: DatabaseManager,
    config: PipelineConfig,
    *,
    technology_filter: Optional[str] = None,
    oss_csv_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    export_db_snapshot: bool = False,
) -> tuple[Optional[Path], Optional[pd.DataFrame]]:
    """Run the OSS-vs-DB audit comparison.

    Parameters
    ----------
    db:
        DatabaseManager instance — sync_engine is used for read queries.
    config:
        Pipeline configuration (provides project name, paths).
    technology_filter:
        If set to 'LTE' or 'NR', only that technology is audited.
    oss_csv_dir:
        Override directory to scan for OSS CSV files.
    output_dir:
        Override directory for comparison/discrepancy CSV output.
    export_db_snapshot:
        If True, write a CSV snapshot of the fetched DB columns.

    Returns
    -------
    (disc_csv_path, discrepancies_df)
        disc_csv_path is the Path to the discrepancies CSV, or None if no mismatches.
        discrepancies_df is the DataFrame of MISMATCH rows (or None), allowing the
        caller to pass it directly to the discrepancy import flow without a CSV round-trip.
    """
    paths = config.paths
    oss_dir = oss_csv_dir or paths.get_oss_csv_path(config.project_name)
    out_dir = output_dir or paths.get_update_path()
    export_dir = paths.get_csv_export_path() if export_db_snapshot else None

    out_dir.mkdir(parents=True, exist_ok=True)
    if export_dir:
        export_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    engine = db.sync_engine

    # 1. Discover OSS CSVs
    oss_files = _find_oss_csvs(oss_dir)
    if not oss_files:
        logger.error("No OSS CSV files found in %s. Aborting.", oss_dir)
        return None, None

    if technology_filter:
        tech_upper = technology_filter.upper()
        oss_files = {k: v for k, v in oss_files.items() if k.upper() == tech_upper}
        if not oss_files:
            logger.error("No OSS CSV for technology '%s' in %s.", tech_upper, oss_dir)
            return None, None
        logger.info("technology_filter='%s' — auditing: %s", tech_upper, list(oss_files.keys()))

    all_comparisons: list[pd.DataFrame] = []
    all_discrepancies: list[pd.DataFrame] = []

    # 2. Per-technology comparison
    for technology, oss_path in oss_files.items():
        cfg = _TECH_CONFIG.get(technology)
        if cfg is None:
            logger.warning("No config for technology '%s', skipping.", technology)
            continue

        column_mapping: Dict[str, str] = cfg["column_mapping"]

        # Read OSS CSV — only convert columns that participate in the audit
        logger.info("[%s] Reading OSS CSV: %s", technology, oss_path.name)
        oss_df = pd.read_csv(oss_path, dtype=str)
        used_oss_cols = {cfg["oss_cell_name_col"], "ENODEB NAME"} | set(column_mapping.keys())
        for col in used_oss_cols:
            if col in oss_df.columns:
                oss_df[col] = _to_numeric_column(oss_df[col])
        logger.info("[%s] OSS rows: %d", technology, len(oss_df))

        # Fetch only the columns needed from the DB
        needed_db_cols = [
            cfg["db_cell_name_col"],
            "technology_active",
            "location_eid",
            "cell_eid",
            "eid",
        ]
        needed_db_cols.extend(column_mapping.values())
        needed_db_cols = list(dict.fromkeys(needed_db_cols))

        snapshot_path = (export_dir / f"{cfg['db_table']}_export_{timestamp}.csv") if export_dir else None
        db_df = _fetch_db_columns(engine, cfg["db_table"], needed_db_cols, export_path=snapshot_path)

        # Filter by technology_active
        tech_val = cfg["db_tech_value"]
        if "technology_active" in db_df.columns:
            before = len(db_df)
            db_df = db_df[db_df["technology_active"].astype(str).str.upper() == tech_val].copy()
            logger.info("[%s] DB rows after technology_active='%s' filter: %d / %d", technology, tech_val, len(db_df), before)
        else:
            logger.warning("[%s] 'technology_active' column not found; skipping filter.", technology)

        comp_df, disc_df = _compare_technology(
            oss_df=oss_df,
            db_df=db_df,
            technology=technology,
            oss_cell_name_col=cfg["oss_cell_name_col"],
            db_cell_name_col=cfg["db_cell_name_col"],
            column_mapping=column_mapping,
            timestamp=timestamp,
        )
        all_comparisons.append(comp_df)
        all_discrepancies.append(disc_df)

    if not all_comparisons:
        logger.warning("No comparisons produced.")
        return None, None

    # 3. Combine and save
    comparisons_df = pd.concat(all_comparisons, ignore_index=True)
    discrepancies_df = pd.concat(all_discrepancies, ignore_index=True)

    total = len(comparisons_df)
    mismatches = len(discrepancies_df)

    comparisons_df.to_csv(out_dir / f"comparisons_{timestamp}.csv", index=False)
    logger.info("Saved comparisons (%d rows) → %s", total, out_dir / f"comparisons_{timestamp}.csv")

    if discrepancies_df.empty:
        logger.info("Audit complete | Checks: %d | All values MATCH.", total)
        return None, None

    disc_path = out_dir / f"discrepancies_{timestamp}.csv"
    discrepancies_df.to_csv(disc_path, index=False)
    logger.warning(
        "Audit complete | Checks: %d | Matches: %d | Mismatches: %d",
        total, total - mismatches, mismatches,
    )
    return disc_path, discrepancies_df


# ---------------------------------------------------------------------------
# Combined audit + import (orchestrator entry point)
# ---------------------------------------------------------------------------

async def run_audit_flow(
    db: DatabaseManager,
    config: PipelineConfig,
    *,
    imported_at: datetime,
    technology_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Run OSS-vs-DB comparison and import mismatches into the discrepancies table.

    This is the orchestrator-facing entry point that combines the comparison
    (sync, read-only) with the discrepancy import (async, write) in one step.
    Eliminates the stale-CSV problem by only importing what was just compared.

    Parameters
    ----------
    db:
        DatabaseManager instance (sync_engine for reads, async session for writes).
    config:
        Pipeline configuration.
    imported_at:
        Shared snapshot timestamp for all inserted rows.
    technology_filter:
        If set to 'LTE' or 'NR', only that technology is audited.

    Returns
    -------
    Dict with keys: success, mismatch_count, rows_imported, disc_path, error.
    """
    result: Dict[str, Any] = {
        "success": False,
        "mismatch_count": 0,
        "rows_imported": 0,
        "disc_path": None,
        "error": None,
    }

    try:
        # Phase 1: sync comparison (writes CSV artifacts)
        disc_path, disc_df = run_audit(
            db, config, technology_filter=technology_filter,
        )

        if disc_df is None or disc_df.empty:
            result["success"] = True
            return result

        result["disc_path"] = str(disc_path) if disc_path else None
        result["mismatch_count"] = len(disc_df)

        # Phase 2: async import into discrepancies table
        records = _df_to_db_records(disc_df)
        if not records:
            result["success"] = True
            return result

        for rec in records:
            rec["imported_at"] = imported_at

        records = _normalize_rows(records)
        num_cols = len(records[0])
        safe_batch = min(BATCH_SIZE, max(1, PG_MAX_PARAMS // num_cols))

        logger.info("Importing %d MISMATCH rows into discrepancies table.", len(records))

        async with db.session() as session:
            count = 0
            for i in range(0, len(records), safe_batch):
                batch = records[i : i + safe_batch]
                stmt = pg_insert(Discrepancy).values(batch)
                await session.execute(stmt)
                count += len(batch)

        result["rows_imported"] = count
        result["success"] = True
        logger.info("Successfully imported %d discrepancies.", count)

    except Exception as exc:
        logger.error("Audit flow failed: %s", exc, exc_info=True)
        result["error"] = str(exc)

    return result
