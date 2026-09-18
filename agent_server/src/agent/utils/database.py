"""
Async database utility functions for telecom coverage analysis.
"""

from typing import List, Dict, Any, Optional

from agent.db.DatabaseManager import get_global_db_manager
from security.encryption.iid_hash_utils import HASHING_ENABLED, reverse_map_hashes, is_hashed_value

# Database manager will be initialized on first use


async def get_cell_ids_by_region(project_name: str, region_values: List[str], user_email: str) -> List[str]:
    """
    Get cell IIDs by searching across location fields and connecting through location_eid.
    
    Args:
        project_name: Name of the project (used as database name)
        region_values: List of region values to search for
        
    Returns:
        List of cell IIDs matching the region criteria
    """
    query = """
        SELECT DISTINCT c1.iid 
        FROM cell_lte c1
        LEFT JOIN (
            SELECT DISTINCT ON (iid) *
            FROM location
            WHERE imported_at = (SELECT MAX(imported_at) FROM location)
        ) l1 ON l1.iid = c1.location_iid
        WHERE (l1.address1 ILIKE ANY($1::text[]) 
           OR l1.town ILIKE ANY($1::text[])
           OR l1.state ILIKE ANY($1::text[]))
        AND c1.imported_at = (
            SELECT MAX(imported_at)
            FROM cell_lte
        )

        UNION

        SELECT DISTINCT c1.iid 
        FROM cell_nr c1
        LEFT JOIN (
            SELECT DISTINCT ON (iid) *
            FROM location
            WHERE imported_at = (SELECT MAX(imported_at) FROM location)
        ) l1 ON l1.iid = c1.location_iid
        WHERE (l1.address1 ILIKE ANY($1::text[]) 
           OR l1.town ILIKE ANY($1::text[])
           OR l1.state ILIKE ANY($1::text[]))
        AND c1.imported_at = (
            SELECT MAX(imported_at)
            FROM cell_nr
        )
    """
    
    # Convert region values to ILIKE patterns (case-insensitive partial matching)
    like_patterns = [f"%{value}%" for value in region_values]

    try:
        result = await get_global_db_manager().execute_query(project_name, query, user_email, (like_patterns,))
        if result["status"]:
            return [row['iid'] for row in result["data"]]
        else:
            print(f"Warning: Could not fetch cell IDs by region: {result.get('error')}")
            raise ValueError(f"Could not fetch cell IDs by region: {result.get('error')}")
    except Exception as e:
        print(f"Warning: Could not fetch cell IDs by region: {e}")
        raise ValueError(f"Could not fetch cell IDs by region: {e}")


async def get_cell_ids_by_location_iids(project_name: str, location_iids: List[str], user_email: str) -> List[str]:
    """
    Get cell IIDs by location IIDs from the cell table.
    
    Args:
        project_name: Name of the project (used as database name)
        location_iids: List of location IIDs to search for
        
    Returns:
        List of cell IIDs matching the location IID criteria
    """

    query = """
        SELECT DISTINCT iid 
        FROM cell_lte
        WHERE location_iid = ANY($1::text[])
        AND imported_at = (
            SELECT MAX(imported_at)
            FROM cell_lte
        )

        UNION

        SELECT DISTINCT iid 
        FROM cell_nr
        WHERE location_iid = ANY($1::text[])
        AND imported_at = (
            SELECT MAX(imported_at)
            FROM cell_nr
        )
    """

    # Convert location IIDs to strings for the query
    location_iids_str = [str(loc_iid) for loc_iid in location_iids]

    try:
        result = await get_global_db_manager().execute_query(project_name, query, user_email, (location_iids_str,))
        if result["status"]:
            return [row['iid'] for row in result["data"]]
        else:
            print(f"Warning: Could not fetch cell IDs by location IIDs: {result.get('error')}")
            raise ValueError(f"Could not fetch cell IDs by location IIDs: {result.get('error')}")
    except Exception as e:
        print(f"Warning: Could not fetch cell IDs by location IIDs: {e}")
        raise ValueError(f"Could not fetch cell IDs by location IIDs: {e}")


async def get_all_cell_ids(project_name: str, user_email: str) -> List[str]:
    """
    Get all cell IIDs from the database.
    
    Args:
        project_name: Name of the project (used as database name)
        
    Returns:
        List of all cell IIDs
    """
    
    query = """
        SELECT DISTINCT iid 
        FROM cell_lte
        WHERE imported_at = (
            SELECT MAX(imported_at)
            FROM cell_lte   
        )

        UNION

        SELECT DISTINCT iid 
        FROM cell_nr
        WHERE imported_at = (
            SELECT MAX(imported_at)
            FROM cell_nr
        )
    """
    
    try:
        result = await get_global_db_manager().execute_query(project_name, query, user_email)
        print("All Cells In The Network", result)
        if result["status"]:
            return [row['iid'] for row in result["data"]]
        else:
            print(f"Warning: Could not fetch all cell IDs: {result.get('error')}")
            raise ValueError(f"Could not fetch all cell IDs: {result.get('error')}")
    except Exception as e:
        print(f"Warning: Could not fetch all cell IDs: {e}")
        raise ValueError(f"Could not fetch all cell IDs: {e}")


async def get_map_data_structure_from_iids(project_name: str, iids: List[str], user_email: str) -> List[Dict[str, Any]]:
    """
    Returns:
            List of dicts formatted like:
            [
            {
                "site_iid": "S1234",
                "latitude": 28.6139,
                "longitude": 77.2090,
                "technology": ["LTE", "NR"],
                "cells": [
                {
                    "cell_iid": "S1234_L1800_A",
                    "azimuth": 0,
                    "band": "LTE1800",
                    "pci": 45,
                    "technology": "LTE"
                    "selected": False
                }
                ]
            }
        ]
    """

    SQL = """
        SELECT
        loc.iid AS site_iid,
        loc.latitude,
        loc.longitude,
        c.cell_iid AS cell_iid,
        NULLIF(c.technology_active::text, '') AS technology,
        phy.azimuth,
        c.lte_carrierparameters_physicalcellid  AS pci,
        c.lte_carrierparameters_iid AS band
        FROM cell_lte c
        LEFT JOIN (
            SELECT DISTINCT ON (iid) 
                iid, latitude, longitude, imported_at
            FROM location
            ORDER BY iid, imported_at DESC
        ) loc ON loc.iid = c.location_iid
        LEFT JOIN (
            SELECT DISTINCT ON (cell_iid) cell_iid, azimuth
            FROM cell_physical_antenna
            WHERE imported_at = (SELECT MAX(imported_at) FROM cell_physical_antenna)
            ORDER BY cell_iid, imported_at DESC
        ) phy ON phy.cell_iid = c.cell_iid
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)

        UNION

        SELECT
        loc.iid AS site_iid,
        loc.latitude,
        loc.longitude,
        c.cell_iid AS cell_iid,
        NULLIF(c.technology_active::text, '') AS technology,
        phy.azimuth,
        c.nrt_carrierparameters_physicalcellid  AS pci,
        c.nrt_carrierparameters_iid AS band
        FROM cell_nr c
        LEFT JOIN (
            SELECT DISTINCT ON (iid) 
                iid, latitude, longitude, imported_at
            FROM location
            ORDER BY iid, imported_at DESC
        ) loc ON loc.iid = c.location_iid
        LEFT JOIN (
            SELECT DISTINCT ON (cell_iid) cell_iid, azimuth
            FROM cell_physical_antenna
            WHERE imported_at = (SELECT MAX(imported_at) FROM cell_physical_antenna)
            ORDER BY cell_iid, imported_at DESC
        ) phy ON phy.cell_iid = c.cell_iid
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
        """

    try:
        result = await get_global_db_manager().execute_query(project_name, SQL, user_email)
        if not result["status"]:
            raise ValueError(f"Could not fetch map data from database")

        rows = result["data"]

        # Reverse-map hashed IIDs for display
        rmap = {}
        if HASHING_ENABLED and rows:
            hashes = set()
            for r in rows:
                for col in ("site_iid", "cell_iid"):
                    val = r.get(col)
                    if val and isinstance(val, str) and is_hashed_value(val):
                        hashes.add(val)
            if hashes:
                async with get_global_db_manager().connection(project_name) as conn:
                    rmap = await reverse_map_hashes(conn, hashes)

        sites: Dict[str, Dict] = {}
        print("Rows", len(rows))
        for r in rows:
            raw_site = r.get("site_iid") or "unknown_site"
            raw_cell = r.get("cell_iid")
            site_key = rmap.get(raw_site, raw_site)
            cell_display = rmap.get(raw_cell, raw_cell) if raw_cell else raw_cell

            if site_key not in sites:
                sites[site_key] = {
                    "site_iid": site_key,
                    "latitude": r.get("latitude"),
                    "longitude": r.get("longitude"),
                    "technology": set(),
                    "cells": []
                }

            tech = r.get("technology")
            if tech:
                sites[site_key]["technology"].add(tech)

            # Construct cell object
            cell_obj = {
                "cell_iid": cell_display,
                "azimuth": r.get("azimuth"),
                "band": r.get("band"),
                "selected": False
            }

            if r.get("pci") is not None:
                cell_obj["pci"] = r.get("pci")

            if tech:
                cell_obj["technology"] = tech

            sites[site_key]["cells"].append(cell_obj)
            if r.get("cell_iid") in iids:
                cell_obj["selected"] = True

        # Finalize JSON output
        output = []
        for s in sites.values():
            output.append({
                "site_iid": s["site_iid"],
                "latitude": s["latitude"],
                "longitude": s["longitude"],
                "technology": sorted(list(s["technology"])),
                "cells": s["cells"]
            })
        #filter the output based on the user_email

        return output
    except Exception as e:
        raise ValueError(f"Could not fetch map data from database.")


async def get_coverage_map_data_structure_from_iids_only_iid_cells(project_name: str, iids: List[str], user_email: str) -> List[Dict[str, Any]]:
    """
    Returns:
            List of dicts formatted like:
            [
            {
                "site_iid": "S1234",
                "latitude": 28.6139,
                "longitude": 77.2090,
                "technology": ["LTE", "NR"],
                "cells": [
                {
                    "cell_iid": "S1234_L1800_A",
                    "azimuth": 0,
                    "band": "LTE1800",
                    "pci": 45,
                    "technology": "LTE"
                    
                }
                ]
            }
        ]
    """

    SQL = """
        SELECT
        loc.iid AS site_iid,
        loc.latitude,
        loc.longitude,
        c.cell_iid AS cell_iid,
        NULLIF(c.technology_active::text, '') AS technology,
        phy.azimuth,
        c.lte_carrierparameters_physicalcellid  AS pci,
        c.lte_carrierparameters_iid AS band
        FROM cell_lte c
        LEFT JOIN (
            SELECT DISTINCT ON (iid) 
                iid, latitude, longitude, imported_at
            FROM location
            ORDER BY iid, imported_at DESC
        ) loc ON loc.iid = c.location_iid
        LEFT JOIN (
            SELECT DISTINCT ON (cell_iid) cell_iid, azimuth
            FROM cell_physical_antenna
            WHERE imported_at = (SELECT MAX(imported_at) FROM cell_physical_antenna)
            ORDER BY cell_iid, imported_at DESC
        ) phy ON phy.cell_iid = c.cell_iid
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_lte)
        AND c.cell_iid = ANY($1::text[])

        UNION

        SELECT
        loc.iid AS site_iid,
        loc.latitude,
        loc.longitude,
        c.cell_iid AS cell_iid,
        NULLIF(c.technology_active::text, '') AS technology,
        phy.azimuth,
        c.nrt_carrierparameters_physicalcellid  AS pci,
        c.nrt_carrierparameters_iid AS band
        FROM cell_nr c
        LEFT JOIN (
            SELECT DISTINCT ON (iid) 
                iid, latitude, longitude, imported_at
            FROM location
            ORDER BY iid, imported_at DESC
        ) loc ON loc.iid = c.location_iid
        LEFT JOIN (
            SELECT DISTINCT ON (cell_iid) cell_iid, azimuth
            FROM cell_physical_antenna
            WHERE imported_at = (SELECT MAX(imported_at) FROM cell_physical_antenna)
            ORDER BY cell_iid, imported_at DESC
        ) phy ON phy.cell_iid = c.cell_iid
        WHERE c.imported_at = (SELECT MAX(imported_at) FROM cell_nr)
        AND c.cell_iid = ANY($1::text[])
        """
    
    identifiers_as_text = [str(x) for x in iids]    
    
    try:
        result = await get_global_db_manager().execute_query(project_name, SQL, user_email, (identifiers_as_text,))
        if not result["status"]:
            raise ValueError(f"Could not fetch map data from database")

        rows = result["data"]

        # Reverse-map hashed IIDs for display
        rmap = {}
        if HASHING_ENABLED and rows:
            hashes = set()
            for r in rows:
                for col in ("site_iid", "cell_iid"):
                    val = r.get(col)
                    if val and isinstance(val, str) and is_hashed_value(val):
                        hashes.add(val)
            if hashes:
                async with get_global_db_manager().connection(project_name) as conn:
                    rmap = await reverse_map_hashes(conn, hashes)

        sites: Dict[str, Dict] = {}

        for r in rows:
            raw_site = r.get("site_iid") or "unknown_site"
            raw_cell = r.get("cell_iid")
            site_key = rmap.get(raw_site, raw_site)
            cell_display = rmap.get(raw_cell, raw_cell) if raw_cell else raw_cell

            if site_key not in sites:
                sites[site_key] = {
                    "site_iid": site_key,
                    "latitude": r.get("latitude"),
                    "longitude": r.get("longitude"),
                    "technology": set(),
                    "cells": []
                }

            tech = r.get("technology")
            if tech:
                sites[site_key]["technology"].add(tech)

            # Construct cell object
            cell_obj = {
                "cell_iid": cell_display,
                "azimuth": r.get("azimuth"),
                "band": r.get("band"),
            }

            if r.get("pci") is not None:
                cell_obj["pci"] = r.get("pci")

            if tech:
                cell_obj["technology"] = tech

            sites[site_key]["cells"].append(cell_obj)

        # Finalize JSON output
        output = []
        for s in sites.values():
            output.append({
                "site_iid": s["site_iid"],
                "latitude": s["latitude"],
                "longitude": s["longitude"],
                "technology": sorted(list(s["technology"])),
                "cells": s["cells"]
            })

        return output
    except Exception as e:
        raise ValueError(f"Could not fetch map data from database.")


async def segregate_iids_by_technology(project_name: str, iids: List[str], user_email: str) -> Dict[str, List[str]]:
    """
    Split a combined list of cell IIDs into per-technology lists
    by checking which table each IID belongs to.

    Returns {"lte": [...], "nr": [...]}
    """
    identifiers = [str(x) for x in iids]

    lte_query = """
        SELECT DISTINCT iid
        FROM cell_lte
        WHERE iid = ANY($1::text[])
        AND imported_at = (SELECT MAX(imported_at) FROM cell_lte)
    """

    nr_query = """
        SELECT DISTINCT iid
        FROM cell_nr
        WHERE iid = ANY($1::text[])
        AND imported_at = (SELECT MAX(imported_at) FROM cell_nr)
    """

    try:
        db = get_global_db_manager()
        lte_result = await db.execute_query(project_name, lte_query, user_email, (identifiers,))
        nr_result = await db.execute_query(project_name, nr_query, user_email, (identifiers,))

        lte_iids = [row['iid'] for row in lte_result["data"]] if lte_result["status"] else []
        nr_iids = [row['iid'] for row in nr_result["data"]] if nr_result["status"] else []

        return {"lte": lte_iids, "nr": nr_iids}
    except Exception as e:
        raise ValueError(f"Could not segregate IIDs by technology: {e}")
