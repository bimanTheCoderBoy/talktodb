"""
Shared IID hashing utility for the backend.

Mirrors the pipeline's iid_hasher.py logic so both pipeline and backend
produce identical hashes for the same input.
"""
import hashlib
import logging
import os
import re
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

_DIGEST_SIZE = 16  # 32 hex chars — matches pipeline/utils/iid_hasher.py

logger.info(f"[IID_HASH_UTILS] IID_HASHING_ENABLED: {os.getenv('IID_HASHING_ENABLED', 'false').lower()}")

HASHING_ENABLED = os.getenv("IID_HASHING_ENABLED", "false").lower() == "true"

# Column names that hold hashed IIDs — used to detect which result columns need reverse mapping
IID_COLUMN_NAMES: Set[str] = {
    "iid", "cell_iid", "mu_iid", "location_iid", "parent_iid", "tower_iid",
    "site_iid", "lte_cellname", "lte_ecgi", "nrt_ncgi", "cell_name", "enodeb_name",
}

# Regex to detect a 32-char hex string (BLAKE2b hash output)
_HASH_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def unwrap_hash_token(value: str) -> str:
    """Strip <HASH:xxx> wrapper from old encryption tokens. Returns raw hash or value as-is."""
    if value.startswith("<HASH:") and value.endswith(">"):
        return value[6:-1]
    return value


def normalize_to_db_value(value: Optional[str]) -> Optional[str]:
    """
    Convert any identifier format to the DB-ready value.
    When HASHING ENABLED:
      - <HASH:xxx> token (from old encryption) → strip wrapper, return raw hash
      - 32-char hex (already a hash) → return as-is
      - Original name → hash it
    When HASHING DISABLED: complete no-op, returns value untouched.
    """
    if value is None:
        return None
    if not HASHING_ENABLED:
        return str(value)
    stripped = unwrap_hash_token(str(value))
    if is_hashed_value(stripped):
        return stripped
    return hashlib.blake2b(stripped.strip().encode(), digest_size=_DIGEST_SIZE).hexdigest()


def hash_iid(value: Optional[str]) -> Optional[str]:
    """Deterministic BLAKE2b hash of an IID string. Returns value as-is when hashing is disabled."""
    if not HASHING_ENABLED or value is None:
        return value
    return hashlib.blake2b(str(value).strip().encode(), digest_size=_DIGEST_SIZE).hexdigest()


def is_hashed_value(value: str) -> bool:
    """Check if a string looks like a BLAKE2b hash (32 lowercase hex chars)."""
    return bool(_HASH_PATTERN.match(value))


async def reverse_map_hashes(
    conn,
    hashes: Set[str],
) -> Dict[str, str]:
    """
    Query iid_mapping table to get original values for a set of hashes.
    Uses asyncpg connection directly (from DatabaseManager pool).

    Returns {hash: original} dict.
    """
    if not HASHING_ENABLED or not hashes:
        return {}

    hashes_list = list(hashes)
    rows = await conn.fetch(
        "SELECT hash, original FROM iid_mapping WHERE hash = ANY($1::text[])",
        hashes_list,
    )
    return {r["hash"]: r["original"] for r in rows}


def collect_hashes_from_rows(
    rows: List[Dict],
    columns: Optional[List[str]] = None,
) -> Set[str]:
    """
    Scan result rows and collect ALL string values that look like BLAKE2b hashes.
    Scans all columns by default — handles LLM-generated SQL aliases like "Cell IID"
    that don't match exact column names like "cell_iid".
    """
    if not HASHING_ENABLED:
        return set()

    hashes: Set[str] = set()
    for row in rows:
        cols_to_scan = columns if columns else row.keys()
        for col in cols_to_scan:
            val = row.get(col)
            if val and isinstance(val, str) and is_hashed_value(val):
                hashes.add(val)
    return hashes


def apply_reverse_map(
    rows: List[Dict],
    reverse_map: Dict[str, str],
    columns: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Replace hashed values with originals in result rows.
    Scans all columns by default — handles LLM-generated SQL aliases.
    """
    if not reverse_map:
        return rows

    for row in rows:
        cols_to_scan = columns if columns else list(row.keys())
        for col in cols_to_scan:
            val = row.get(col)
            if val and isinstance(val, str) and val in reverse_map:
                row[col] = reverse_map[val]
    return rows
