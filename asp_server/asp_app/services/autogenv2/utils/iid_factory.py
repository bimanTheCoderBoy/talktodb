"""
Collision-safe naming for auto-generated site_iid and cell_iid values.

Naming convention:
  site_iid: AUTO_<8hex>_<idx>
  cell_iid: AUTO_<8hex>_<idx>_C<sector_idx>

The 8-char hex is md5(session_id || seed || idx)[:8] — collision probability
is negligible at the expected N (<=10) and seed range we use.
"""
import hashlib

AUTO_IID_PREFIX = "AUTO"


def _hex_token(session_id: str, seed: int, idx: int) -> str:
    raw = f"{session_id}_{seed}_{idx}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()[:8]


def make_autogen_site_iid(session_id: str, seed: int, idx: int) -> str:
    """Stable site_iid for the idx-th candidate of the given (session, seed)."""
    return f"{AUTO_IID_PREFIX}_{_hex_token(session_id, seed, idx)}_{idx}"


def make_autogen_cell_iid(site_iid: str, sector_idx: int) -> str:
    """Cell IID under a given site_iid. sector_idx is 0-based."""
    return f"{site_iid}_C{sector_idx}"


def is_autogen_iid(iid: str) -> bool:
    """True iff iid was produced by this factory."""
    return isinstance(iid, str) and iid.startswith(f"{AUTO_IID_PREFIX}_")
