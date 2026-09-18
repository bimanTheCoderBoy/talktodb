"""
Technology classification functions for EDS API records.

Pure functions that operate on raw JSON dicts from the API.
No DB, no Pydantic, no async -- just dict inspection.
"""

from __future__ import annotations


def is_lte_mu(record: dict) -> bool:
    """Return True if the MU record belongs to LTE technology."""
    tech = record.get("technology", {})
    if tech.get("fixedTechnology") == "LTE":
        return True
    lte_section = record.get("lte", {})
    if lte_section and lte_section.get("enabled") in (True, "True"):
        return True
    if tech.get("active") == "LTE":
        return True
    return False


def is_nr_mu(record: dict) -> bool:
    """Return True if the MU record belongs to NR technology."""
    tech = record.get("technology", {})
    if tech.get("fixedTechnology") == "NR":
        return True
    nrt_section = record.get("nrt", {})
    if nrt_section and nrt_section.get("enabled") in (True, "True"):
        return True
    if tech.get("active") == "NR":
        return True
    return False


def is_lte_cell(record: dict) -> bool:
    """Return True if the Cell record belongs to LTE technology."""
    return record.get("technology", {}).get("active", "") == "LTE"


def is_nr_cell(record: dict) -> bool:
    """Return True if the Cell record belongs to NR technology."""
    return record.get("technology", {}).get("active", "") == "NR"
