"""
Rule-based telecom entity detector — 3-layer detection engine.

Replaces LLM-based entity detection with:
  Layer 1: Keyword-value regex patterns
  Layer 2: DB dictionary lookup (known site names / cell IDs)
  Layer 3: Structural pattern matching (UPPER_SNAKE_CASE, alphanumeric codes)
"""

import re
from typing import List, Dict, Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .known_values import KnownValuesStore

# ---------------------------------------------------------------------------
# Exclusion zone patterns (spans within these are never entity values)
# ---------------------------------------------------------------------------

_METADATA_BOUNDS_RE = re.compile(r'\(min\s*=\s*\d+\s*,\s*max\s*=\s*\d+\s*\)', re.IGNORECASE)
_PCI_MOD_RE = re.compile(r'\bpci\s+mod\s+(\d+)', re.IGNORECASE)
_LIMIT_RE = re.compile(r'\blimit\s+(\d+)', re.IGNORECASE)
_TOP_N_RE = re.compile(r'\btop\s+(\d+)', re.IGNORECASE)
_AT_LEAST_RE = re.compile(r'\bat\s+least\s+(?:one|\d+)', re.IGNORECASE)

# ---------------------------------------------------------------------------
# Separator between keyword and numeric value
# ---------------------------------------------------------------------------
# Covers: =, <, >, >=, <=, !=, "is", "is like", "was", "should be",
#         "equals", "equal", bare whitespace
_OP = (
    r'(?:'
    r'\s*[><=!]{1,2}\s*'
    r'|'
    r'\s*:\s*'
    r'|'
    r'\s+(?:is\s+(?:like\s+)?|was\s+|should\s+be\s+|equals?\s+)'
    r'|'
    r'\s+'
    r')'
)

_NUM = r'(-?\d+)'

# ---------------------------------------------------------------------------
# Layer 1: Keyword-anchored entity patterns
# ---------------------------------------------------------------------------

_TILT_RE = re.compile(r'(?i)\b(?:down|up)?tilt' + _OP + _NUM)
_AZIMUTH_RE = re.compile(r'(?i)\b(?:azimuth|azi|bearing)' + _OP + _NUM)
_PCI_RE = re.compile(r'(?i)\b(?:pci|physical\s*cell\s*id|physicalcellid)' + _OP + _NUM)
_ECI_RE = re.compile(r'(?i)\b(?:eci|e-utran\s+cell\s+identity)' + _OP + _NUM)
_TAC_RE = re.compile(r'(?i)\b(?:tac|tracking\s+area\s+code)' + _OP + _NUM)

# EARFCN band codes after keyword
_EARFCN_BAND_KW_RE = re.compile(
    r'(?i)\bearfcn'
    r'(?:\s+(?:is\s+)?|\s*[=:]\s*)'
    r'(L\d+_\d+M_\d+|NbIOT_\d+)\b'
)
# EARFCN bare number after keyword
_EARFCN_NUM_KW_RE = re.compile(r'(?i)\bearfcn' + _OP + r'(\d+)')

# Cell ID after keywords
_CELL_KW_RE = re.compile(r'(?i)\b(?:cell|sector)\s+([A-Za-z0-9][A-Za-z0-9_]+)')
_CELL_EUTRAN_RE = re.compile(r'(?i)EUtranCellFDD\s*=\s*([A-Za-z0-9_]+)')
_CELL_NRCELL_RE = re.compile(r'(?i)NRCellDU\s*=\s*([A-Za-z0-9_]+)')

# Site ID after keywords
_SITE_KW_RE = re.compile(r'(?i)\bsites?\s+([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*)\b')

# Continuation: "not NUMBER" after a numeric match
_NOT_NUM_RE = re.compile(r'\s+not\s+(-?\d+)', re.IGNORECASE)

# ---------------------------------------------------------------------------
# Layer 3: Structural pattern matching
# ---------------------------------------------------------------------------

# UPPER_SNAKE_CASE with at least one underscore
_SITE_SNAKE_RE = re.compile(r'\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b')

# Standalone uppercase word (4+ alphabetic chars, no digits)
_SITE_STANDALONE_RE = re.compile(r'\b([A-Z]{4,})\b')

# Standalone EARFCN band codes (without keyword prefix)
_EARFCN_BAND_STANDALONE_RE = re.compile(r'\b(L\d+_\d+M_\d+|NbIOT_\d+)\b')

# Standalone cell ID: alphanumeric with both letters and digits
_CELL_STANDALONE_RE = re.compile(r'\b([A-Z0-9][A-Z0-9_]*[A-Z0-9])\b')

# ---------------------------------------------------------------------------
# Deny lists: tokens that look like entities but aren't
# ---------------------------------------------------------------------------

_TELECOM_KEYWORDS = {
    'PCI', 'TAC', 'ECI', 'EARFCN', 'NR', 'LTE', 'ALL', 'LIMIT',
    'ENCRYPTED', 'HASH', 'NULL', 'SELECT', 'FROM', 'WHERE', 'AND',
    'NOT', 'HAVING', 'FOR', 'THE', 'RUN', 'SHOW', 'ALSO', 'THEN',
    'AUDIT', 'CHECK', 'WITH', 'SITE', 'SITES', 'CELL', 'CELLS',
    'TILT', 'AZIMUTH', 'BEARING', 'SECTOR', 'DISCREPANCY', 'REPORT',
    'DISPLAY', 'LIST', 'RETRIEVE', 'EXECUTE', 'COMPARE', 'FIND',
    'EVERYTHING', 'ERROR', 'TRUE', 'FALSE', 'BETWEEN', 'ORDER',
    'PLEASE', 'WHAT', 'DOES', 'THIS', 'THAT', 'WHICH', 'DISTINCT',
    'INTERFERENCE', 'CONFLICTING', 'CONFLICT', 'MATCHES',
    'BEAMFORMING', 'TECHNOLOGIES', 'CONFIGURATION', 'FILTER',
    'INCLUDING', 'FILTERED', 'CARRIERS', 'WRONG', 'GIMME',
    'SEEMS', 'SHOULD', 'ENGINE', 'EXACTLY', 'DIFFERENCE',
    'PROVIDE', 'GIVE', 'NEED', 'WANT', 'QUERY', 'DATA',
    'NBIOT', 'NOKIA', 'ERICSSON', 'HUAWEI', 'TOTAL',
}

_COMMON_ENGLISH_UPPER = {
    'ABOUT', 'ABOVE', 'AFTER', 'AGAIN', 'ALSO', 'AREA', 'BACK',
    'BEEN', 'BEFORE', 'BELOW', 'BOTH', 'CASE', 'CODE', 'COME',
    'COULD', 'DATA', 'DONE', 'DOWN', 'EACH', 'EDIT', 'ELSE',
    'EVEN', 'EVER', 'FILL', 'FIRST', 'FROM', 'FULL', 'GOOD',
    'HAVE', 'HEAD', 'HELP', 'HERE', 'HIGH', 'HOME', 'INTO',
    'JUST', 'KEEP', 'KNOW', 'LAST', 'LEFT', 'LIKE', 'LINE',
    'LONG', 'LOOK', 'MADE', 'MAKE', 'MANY', 'MORE', 'MOST',
    'MUCH', 'MUST', 'NAME', 'NEAR', 'NEXT', 'NONE', 'ONLY',
    'OPEN', 'OVER', 'PART', 'SAME', 'SHOW', 'SIDE', 'SOME',
    'SUCH', 'SURE', 'TAKE', 'TELL', 'THAN', 'THEM', 'THEN',
    'THEY', 'TIME', 'TRUE', 'TYPE', 'UPON', 'VERY', 'WANT',
    'WELL', 'WERE', 'WHAT', 'WHEN', 'WILL', 'WITH', 'WORD',
    'WORK', 'YEAR', 'YOUR', 'ZERO', 'STUFF', 'THINK',
}

_DENY_SET = _TELECOM_KEYWORDS | _COMMON_ENGLISH_UPPER


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _is_earfcn_band(val: str) -> bool:
    return bool(
        re.match(r'^L\d+_\d+M_\d+$', val)
        or re.match(r'^NbIOT_\d+$', val, re.IGNORECASE)
    )


def _is_cell_id(val: str) -> bool:
    return (
        len(val) >= 5
        and bool(re.match(r'^[A-Za-z0-9_]+$', val))
        and any(c.isdigit() for c in val)
        and any(c.isalpha() for c in val)
    )


def _build_exclusion_zones(text: str) -> List[Tuple[int, int]]:
    zones: List[Tuple[int, int]] = []
    for m in _METADATA_BOUNDS_RE.finditer(text):
        zones.append((m.start(), m.end()))
    for m in _PCI_MOD_RE.finditer(text):
        zones.append((m.start(1), m.end(1)))
    for m in _LIMIT_RE.finditer(text):
        zones.append((m.start(1), m.end(1)))
    for m in _TOP_N_RE.finditer(text):
        zones.append((m.start(1), m.end(1)))
    for m in _AT_LEAST_RE.finditer(text):
        zones.append((m.start(), m.end()))
    return zones


def _overlaps_exclusion(start: int, end: int, zones: List[Tuple[int, int]]) -> bool:
    for z_start, z_end in zones:
        if start < z_end and end > z_start:
            return True
    return False


def _extract_group1(pattern: re.Pattern, text: str) -> List[Tuple[int, str]]:
    results = []
    for m in pattern.finditer(text):
        results.append((m.start(1), m.group(1)))
    return results


def _deduplicate(entities: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
    entities.sort(key=lambda e: (e[0], -len(e[1])))
    result = []
    last_end = -1
    for start, val in entities:
        end = start + len(val)
        if start >= last_end:
            result.append((start, val))
            last_end = end
    return result


# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------

def detect_entities(
    text: str,
    known_values: Optional['KnownValuesStore'] = None,
) -> List[Dict]:
    """
    Detect all sensitive telecom entities in the given text.

    Returns a list of dicts, each with:
        - "start_index": int  (position in original text)
        - "original_value": str  (the sensitive substring)

    Sorted by start_index ascending. No overlapping spans.
    """

    exclusions = _build_exclusion_zones(text)
    entities: List[Tuple[int, str]] = []

    # -- Layer 1: SKIPPED for user messages ---------------------------------
    # Numeric query parameters (tilt=-3, azimuth=0, PCI 45) are NOT encrypted.
    # The LLM needs these actual values to generate correct SQL queries.
    # Only identifiers (site names, cell IDs) are sensitive — handled by
    # Layer 2 (DB dictionary) and Layer 3 (structural patterns).
    # EARFCN band codes are identifiers, not numeric params — keep those.
    # -------------------------------------------------------------------

    # Cell ID after keywords
    for pattern in [_CELL_KW_RE, _CELL_EUTRAN_RE, _CELL_NRCELL_RE]:
        for m in pattern.finditer(text):
            val = m.group(1)
            if _is_cell_id(val):
                entities.append((m.start(1), val))

    # Site ID after keywords (value must be uppercase)
    for m in _SITE_KW_RE.finditer(text):
        val = m.group(1)
        if val == val.upper() and val not in _DENY_SET:
            entities.append((m.start(1), val))

    # -- Layer 2: DB dictionary lookup --------------------------------------

    if known_values is not None and known_values.is_loaded:
        db_entities = known_values.find_in_text(text)
        for entry in db_entities:
            entities.append((entry["start_index"], entry["original_value"]))

    # -- Layer 3: Structural pattern matching -------------------------------

    # Standalone EARFCN band codes
    entities.extend(_extract_group1(_EARFCN_BAND_STANDALONE_RE, text))

    # UPPER_SNAKE_CASE tokens (likely site names)
    for m in _SITE_SNAKE_RE.finditer(text):
        val = m.group(1)
        if val not in _DENY_SET and not _is_earfcn_band(val):
            entities.append((m.start(1), val))

    # Standalone uppercase words (potential site names)
    for m in _SITE_STANDALONE_RE.finditer(text):
        val = m.group(1)
        if val not in _DENY_SET and not _is_cell_id(val):
            entities.append((m.start(1), val))

    # Standalone cell IDs (alphanumeric with both letters and digits)
    for m in _CELL_STANDALONE_RE.finditer(text):
        val = m.group(1)
        if _is_cell_id(val) and val not in _DENY_SET:
            entities.append((m.start(1), val))

    # -- Filter exclusions, deduplicate, resolve overlaps -------------------

    filtered = [
        (start, val) for start, val in entities
        if not _overlaps_exclusion(start, start + len(val), exclusions)
    ]

    deduped = _deduplicate(filtered)

    return [{"start_index": s, "original_value": v} for s, v in deduped]
