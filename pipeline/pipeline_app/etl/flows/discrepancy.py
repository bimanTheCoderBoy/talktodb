"""
Optimized discrepancy import flow — loads MISMATCH rows from the audit and
persists them into the ``discrepancies`` database table.

Key improvements over the original pipeline/flows/discrepancy_flow.py:
    - Accepts a DataFrame directly from audit flow (avoids CSV round-trip)
    - Falls back to CSV path if no DataFrame is provided
    - Uses the async DatabaseManager instead of a standalone sync engine
    - Batched insert using the existing repository layer (respects PG param limit)
    - Atomic: data insert + metadata recording in a single session/commit
    - No DDL execution on startup
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert

from pipeline_app.core.config import PipelineConfig
from pipeline_app.core.logging_service import LoggingService
from pipeline_app.db.engine import DatabaseManager
from pipeline_app.db.models.discrepancy import Discrepancy
from pipeline_app.db.models.pipeline_metadata import PipelineMetadata
from pipeline_app.db.repository import BATCH_SIZE, PG_MAX_PARAMS, _normalize_rows

logger = LoggingService.get_logger(__name__)


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _find_latest_discrepancy_csv(directory: Path) -> Optional[Path]:
    """Return the most recently modified discrepancies_*.csv, or None."""
    if not directory.exists():
        return None
    files = sorted(directory.glob("discrepancies_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _load_mismatch_rows(csv_path: Path) -> pd.DataFrame:
    """Load a discrepancy CSV and return only MISMATCH rows, with columns renamed for DB."""
    df = pd.read_csv(csv_path)
    if df.empty:
        return df

    if "status" in df.columns:
        before = len(df)
        df = df[df["status"] == "MISMATCH"].copy()
        skipped = before - len(df)
        if skipped:
            logger.info("Skipped %d non-MISMATCH rows.", skipped)

    df = df.rename(columns={
        "cellName": "cell_name",
        "ENODEB NAME": "enodeb_name",
        "column": "column_name",
    })
    df = df.where(pd.notnull(df), None)
    return df


def _df_to_db_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert a DataFrame of mismatch rows (audit output format) to DB-ready dicts.

    Handles both:
      - DataFrames passed directly from run_audit() (already has canonical column names)
      - DataFrames loaded from CSV (may need renaming)
    """
    rename_map = {
        "cellName": "cell_name",
        "ENODEB NAME": "enodeb_name",
        "column": "column_name",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    df = df.where(pd.notnull(df), None)

    # Cast values to string for TEXT columns in the DB
    for col in ("oss_value", "db_value", "location_eid", "cell_eid"):
        if col in df.columns:
            df[col] = df[col].apply(lambda v: str(v) if v is not None else None)

    return df.to_dict(orient="records")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

