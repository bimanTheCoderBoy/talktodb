"""
IID hashing utility for ACSS service.
Mirrors the pipeline/backend logic so all services produce identical hashes.
"""
import hashlib
import os
import re
from typing import Dict, List, Optional, Set

_DIGEST_SIZE = 16  # 32 hex chars

HASHING_ENABLED = os.getenv("IID_HASHING_ENABLED", "false").lower() == "true"

_HASH_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def hash_iid(value: Optional[str]) -> Optional[str]:
    """Deterministic BLAKE2b hash. Returns value as-is when hashing is disabled."""
    if not HASHING_ENABLED or value is None:
        return value
    return hashlib.blake2b(str(value).strip().encode(), digest_size=_DIGEST_SIZE).hexdigest()


def is_hashed_value(value: str) -> bool:
    return bool(_HASH_PATTERN.match(value))


async def reverse_map_hashes_sql(db_session, hashes: Set[str]) -> Dict[str, str]:
    """Query iid_mapping via SQLAlchemy async session. Returns {hash: original}."""
    if not HASHING_ENABLED or not hashes:
        return {}
    from sqlalchemy import text
    result = await db_session.execute(
        text("SELECT hash, original FROM iid_mapping WHERE hash = ANY(:hashes)"),
        {"hashes": list(hashes)},
    )
    return {r.hash: r.original for r in result}
