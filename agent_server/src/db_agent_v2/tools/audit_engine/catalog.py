"""Catalog of auditable tables, columns, and rule types for user-defined audit rules."""
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

RULE_TYPE_OPTIONS: List[Dict[str, Any]] = [
    {"value": "not_null", "label": "Value is not null", "description": "Pass when the column has a non-null value.", "requires_params": []},
    {"value": "in_range", "label": "Within range", "description": "Pass when value is between min and max (inclusive).", "requires_params": ["min", "max"]},
    {"value": "gt", "label": "Greater than", "description": "Pass when value is greater than the threshold.", "requires_params": ["value"]},
    {"value": "lt", "label": "Less than", "description": "Pass when value is less than the threshold.", "requires_params": ["value"]},
    {"value": "gte", "label": "Greater than or equal", "description": "Pass when value is greater than or equal to the threshold.", "requires_params": ["value"]},
    {"value": "lte", "label": "Less than or equal", "description": "Pass when value is less than or equal to the threshold.", "requires_params": ["value"]},
    {"value": "eq", "label": "Equal to", "description": "Pass when value equals the expected value.", "requires_params": ["value"]},
    {"value": "neq", "label": "Not equal to", "description": "Pass when value does not equal the expected value.", "requires_params": ["value"]},
    {"value": "boolean_true", "label": "Boolean is true", "description": "Pass when the value is true.", "requires_params": []},
    {"value": "boolean_false", "label": "Boolean is false", "description": "Pass when the value is false.", "requires_params": []},
    {"value": "regex", "label": "Matches regex", "description": "Pass when the string value matches the regex pattern.", "requires_params": ["pattern"]},
]

VALID_RULE_TYPES: Set[str] = {opt["value"] for opt in RULE_TYPE_OPTIONS}

# Which check types are valid per column data_type (from catalog column metadata).
RULE_TYPES_BY_DATA_TYPE: Dict[str, List[str]] = {
    "boolean": ["not_null", "boolean_true", "boolean_false", "eq", "neq"],
    "integer": ["not_null", "in_range", "gt", "lt", "gte", "lte", "eq", "neq"],
    "float": ["not_null", "in_range", "gt", "lt", "gte", "lte", "eq", "neq"],
    "text": ["not_null", "eq", "neq", "regex"],
}

VALID_DATA_TYPES: Set[str] = set(RULE_TYPES_BY_DATA_TYPE.keys())


def column_data_type(table_name: str, column: str) -> Optional[str]:
    """Return catalog data_type for a column, or None if unknown."""
    table = TABLE_BY_NAME.get(table_name)
    if not table:
        return None
    for col_meta in table["columns"]:
        if col_meta["name"] == column:
            return col_meta.get("data_type")
    return None


def allowed_rule_types_for_column(table_name: str, column: str) -> List[str]:
    """Return rule types compatible with the column's data type."""
    data_type = column_data_type(table_name, column)
    if not data_type:
        return ["not_null"]
    return list(RULE_TYPES_BY_DATA_TYPE.get(data_type, ["not_null"]))


def validate_rule_type_for_column(table_name: str, column: str, rule_type: str) -> None:
    """Raise ValueError when rule_type is incompatible with the column data type."""
    data_type = column_data_type(table_name, column)
    if not data_type:
        return
    allowed = RULE_TYPES_BY_DATA_TYPE.get(data_type, [])
    if rule_type not in allowed:
        label = data_type
        allowed_labels = ", ".join(allowed)
        raise ValueError(
            f"Column '{table_name}.{column}' ({label}) does not support check type "
            f"'{rule_type}'. Allowed: {allowed_labels}"
        )



BOOLEAN_PARAM_VALUES = {"true", "false", "yes", "no"}
_NUMERIC_DATA_TYPES = {"integer", "float"}
_NUMERIC_THRESHOLD_RULE_TYPES = {"gt", "lt", "gte", "lte", "eq", "neq"}


def validate_rule_params_for_column(
    table_name: str,
    column: str,
    rule_type: str,
    rule_params: Dict[str, Any],
) -> None:
    """Raise ValueError when rule params are incompatible with the column data type."""
    data_type = column_data_type(table_name, column)
    if not data_type:
        return

    params = rule_params or {}
    prefix = f"Column '{column}': "

    if data_type in _NUMERIC_DATA_TYPES:
        if rule_type == "in_range":
            for key in ("min", "max"):
                raw = params.get(key)
                if raw is not None and str(raw).strip() != "":
                    try:
                        float(raw)
                    except (TypeError, ValueError):
                        raise ValueError(f"{prefix}{key} must be numeric")
        elif rule_type in _NUMERIC_THRESHOLD_RULE_TYPES:
            raw = params.get("value")
            if raw is not None and str(raw).strip() != "":
                try:
                    float(raw)
                except (TypeError, ValueError):
                    raise ValueError(f"{prefix}value must be numeric")

    if data_type == "boolean" and rule_type in {"eq", "neq"}:
        raw = params.get("value")
        if raw is not None and str(raw).strip() != "":
            if str(raw).strip().lower() not in BOOLEAN_PARAM_VALUES:
                raise ValueError(f"{prefix}value must be true, false, yes, or no")



AUDIT_TABLE_CATALOG: List[Dict[str, Any]] = [
    {
        "table_name": "cell_lte",
        "label": "LTE Cell",
        "entity_types": ["cell", "site"],
        "columns": [
            {"name": "lte_carrierparameters_physicalcellid", "label": "PCI", "data_type": "integer"},
            {"name": "lte_carrierparameters_caenabledatcell", "label": "CA Enabled", "data_type": "boolean"},
            {"name": "lte_tac", "label": "TAC", "data_type": "integer"},
            {"name": "lte_sumimosupportdl", "label": "SU-MIMO Support DL", "data_type": "boolean"},
            {"name": "lte_mumimosupportdl", "label": "MU-MIMO Support DL", "data_type": "boolean"},
            {"name": "lte_beamformingsupportdl", "label": "Beamforming Support DL", "data_type": "boolean"},
            {"name": "lte_carrierparameters_maxtxpower", "label": "Max TX Power", "data_type": "float"},
            {"name": "lte_prachconfigurationindex", "label": "PRACH Config Index", "data_type": "integer"},
            {"name": "lte_firstassignedrsi", "label": "First Assigned RSI", "data_type": "integer"},
            {"name": "lte_activation", "label": "Activation", "data_type": "boolean"},
        ],
    },
    {
        "table_name": "cell_nr",
        "label": "NR Cell",
        "entity_types": ["cell", "site"],
        "columns": [
            {"name": "nrt_carrierparameters_physicalcellid", "label": "PCI", "data_type": "integer"},
            {"name": "nrt_carrierparameters_caenabledatcell", "label": "CA Enabled", "data_type": "boolean"},
            {"name": "nrt_tac", "label": "TAC", "data_type": "integer"},
            {"name": "nrt_sumimosupportdl", "label": "SU-MIMO Support DL", "data_type": "boolean"},
            {"name": "nrt_mumimosupportdl", "label": "MU-MIMO Support DL", "data_type": "boolean"},
            {"name": "nrt_beamformingsupportdl", "label": "Beamforming Support DL", "data_type": "boolean"},
            {"name": "nrt_carrierparameters_maxtxpower", "label": "Max TX Power", "data_type": "float"},
            {"name": "nrt_prachconfigurationindex", "label": "PRACH Config Index", "data_type": "integer"},
            {"name": "nrt_activation", "label": "Activation", "data_type": "boolean"},
        ],
    },
    {
        "table_name": "location",
        "label": "Site (Location)",
        "entity_types": ["cell", "site"],
        "columns": [
            {"name": "address1", "label": "Address", "data_type": "text"},
            {"name": "town", "label": "Town", "data_type": "text"},
            {"name": "state", "label": "State", "data_type": "text"},
            {"name": "postcode", "label": "Postcode", "data_type": "text"},
            {"name": "latitude", "label": "Latitude", "data_type": "float"},
            {"name": "longitude", "label": "Longitude", "data_type": "float"},
            {"name": "groundhgt", "label": "Ground Height", "data_type": "float"},
            {"name": "buildingheight", "label": "Building Height", "data_type": "integer"},
        ],
    },
    {
        "table_name": "cell_physical_antenna",
        "label": "Physical Antenna",
        "entity_types": ["cell", "site"],
        "columns": [
            {"name": "azimuth", "label": "Azimuth", "data_type": "float"},
            {"name": "tilt", "label": "Tilt", "data_type": "float"},
            {"name": "height", "label": "Height", "data_type": "float"},
            {"name": "spatialdiversity", "label": "Spatial Diversity", "data_type": "boolean"},
            {"name": "constraints_azimuthfixed", "label": "Azimuth Fixed", "data_type": "boolean"},
            {"name": "constraints_heightfixed", "label": "Height Fixed", "data_type": "boolean"},
        ],
    },
    {
        "table_name": "cell_logical_antenna",
        "label": "Logical Antenna",
        "entity_types": ["cell", "site"],
        "columns": [
            {"name": "singlebeamenabled", "label": "Single Beam Enabled", "data_type": "boolean"},
            {"name": "correctionfactor", "label": "Correction Factor", "data_type": "float"},
            {"name": "primarymodel_radiuskm", "label": "Primary Model Radius (km)", "data_type": "float"},
        ],
    },
]

TABLE_BY_NAME: Dict[str, Dict[str, Any]] = {t["table_name"]: t for t in AUDIT_TABLE_CATALOG}

TABLE_ALIASES: Dict[str, str] = {
    "cell_lte": "c_lte",
    "cell_nr": "c_nr",
    "location": "loc",
    "cell_physical_antenna": "cpa",
    "cell_logical_antenna": "cla",
}

# Undirected adjacency for join-path planning (cell_lte and cell_nr are not connected).
TABLE_JOIN_GRAPH: Dict[str, List[str]] = {
    "cell_lte": ["cell_physical_antenna", "cell_logical_antenna", "location"],
    "cell_nr": ["cell_physical_antenna", "cell_logical_antenna", "location"],
    "location": ["cell_lte", "cell_nr", "cell_physical_antenna", "cell_logical_antenna"],
    "cell_physical_antenna": ["cell_lte", "cell_nr", "cell_logical_antenna", "location"],
    "cell_logical_antenna": ["cell_lte", "cell_nr", "cell_physical_antenna", "location"],
}

# Directed join SQL: (from_table, to_table) -> template with {parent} and {child} aliases.
JOIN_EDGE_SQL: Dict[Tuple[str, str], str] = {
    ("cell_lte", "cell_physical_antenna"): (
        "LEFT JOIN cell_physical_antenna {child} ON {parent}.cell_iid = {child}.cell_iid"
    ),
    ("cell_lte", "cell_logical_antenna"): (
        "LEFT JOIN cell_logical_antenna {child} ON {parent}.cell_iid = {child}.cell_iid"
    ),
    ("cell_lte", "location"): (
        "LEFT JOIN location {child} ON {parent}.location_iid = {child}.iid"
    ),
    ("cell_nr", "cell_physical_antenna"): (
        "LEFT JOIN cell_physical_antenna {child} ON {parent}.cell_iid = {child}.cell_iid"
    ),
    ("cell_nr", "cell_logical_antenna"): (
        "LEFT JOIN cell_logical_antenna {child} ON {parent}.cell_iid = {child}.cell_iid"
    ),
    ("cell_nr", "location"): (
        "LEFT JOIN location {child} ON {parent}.location_iid = {child}.iid"
    ),
    ("location", "cell_lte"): (
        "LEFT JOIN cell_lte {child} ON {parent}.eid = {child}.location_eid"
    ),
    ("location", "cell_nr"): (
        "LEFT JOIN cell_nr {child} ON {parent}.eid = {child}.location_eid"
    ),
    ("location", "cell_physical_antenna"): (
        "LEFT JOIN cell_physical_antenna {child} ON {parent}.eid = {child}.location_eid"
    ),
    ("location", "cell_logical_antenna"): (
        "LEFT JOIN cell_logical_antenna {child} ON {parent}.eid = {child}.location_eid"
    ),
    ("cell_physical_antenna", "cell_logical_antenna"): (
        "LEFT JOIN cell_logical_antenna {child} ON {parent}.cell_iid = {child}.cell_iid"
    ),
    ("cell_physical_antenna", "cell_lte"): (
        "LEFT JOIN cell_lte {child} ON {parent}.cell_iid = {child}.cell_iid"
    ),
    ("cell_physical_antenna", "cell_nr"): (
        "LEFT JOIN cell_nr {child} ON {parent}.cell_iid = {child}.cell_iid"
    ),
    ("cell_physical_antenna", "location"): (
        "LEFT JOIN location {child} ON {parent}.location_eid = {child}.eid"
    ),
    ("cell_logical_antenna", "cell_physical_antenna"): (
        "LEFT JOIN cell_physical_antenna {child} ON {parent}.cell_iid = {child}.cell_iid"
    ),
    ("cell_logical_antenna", "cell_lte"): (
        "LEFT JOIN cell_lte {child} ON {parent}.cell_iid = {child}.cell_iid"
    ),
    ("cell_logical_antenna", "cell_nr"): (
        "LEFT JOIN cell_nr {child} ON {parent}.cell_iid = {child}.cell_iid"
    ),
    ("cell_logical_antenna", "location"): (
        "LEFT JOIN location {child} ON {parent}.location_eid = {child}.eid"
    ),
}

CELL_TABLES = frozenset({"cell_lte", "cell_nr"})


def custom_rule_key(rule_id: int) -> str:
    return f"custom:{rule_id}"


def column_result_key(table_name: str, column: str) -> str:
    """Disambiguated row key for multi-table column checks."""
    return f"{table_name}.{column}"


def normalize_checks_table_names(column_checks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure every check has table_name."""
    normalized: List[Dict[str, Any]] = []
    for check in column_checks:
        table_name = (check.get("table_name") or "").strip()
        if not table_name:
            raise ValueError("Each column check must specify a table_name")
        normalized.append({**check, "table_name": table_name})
    return normalized


def resolve_anchor_table(entity_type: str, tables: Set[str]) -> str:
    """Pick the FROM-clause anchor for the entity type and selected tables."""
    if entity_type == "cell":
        if "cell_lte" in tables and "cell_nr" in tables:
            raise ValueError("Cannot mix LTE and NR cell tables in one rule")
        if "location" in tables and not (tables & CELL_TABLES):
            raise ValueError(
                "Location columns require an LTE or NR cell table for cell-level audits"
            )
        if "cell_lte" in tables:
            return "cell_lte"
        if "cell_nr" in tables:
            return "cell_nr"
        if "cell_physical_antenna" in tables:
            return "cell_physical_antenna"
        if "cell_logical_antenna" in tables:
            return "cell_logical_antenna"
        raise ValueError("At least one auditable table is required")

    if "cell_lte" in tables and "cell_nr" in tables:
        raise ValueError("Cannot mix LTE and NR cell tables in one rule")
    return "location"


def _entity_select_and_filter(entity_type: str, anchor: str) -> Tuple[str, str]:
    alias = TABLE_ALIASES[anchor]
    if entity_type == "cell":
        if anchor in CELL_TABLES:
            return f'{alias}.iid', f"{alias}.iid = ANY($1::text[])"
        return f"{alias}.cell_iid", f"{alias}.cell_iid = ANY($1::text[])"
    return f"{alias}.iid", f"{alias}.iid = ANY($1::text[])"


def _plan_join_order(anchor: str, tables: Set[str]) -> List[Tuple[str, str]]:
    """BFS join plan from anchor to every other table in the set."""
    if len(tables) <= 1:
        return []

    parent: Dict[str, Optional[str]] = {anchor: None}
    queue: deque[str] = deque([anchor])

    while queue:
        current = queue.popleft()
        for neighbor in TABLE_JOIN_GRAPH.get(current, []):
            if neighbor in tables and neighbor not in parent:
                parent[neighbor] = current
                queue.append(neighbor)

    unreachable = tables - set(parent.keys())
    if unreachable:
        labels = ", ".join(sorted(unreachable))
        raise ValueError(f"Selected tables cannot be joined together: {labels}")

    join_order: List[Tuple[str, str]] = []

    def append_joins_for(node: str) -> None:
        if node == anchor:
            return
        node_parent = parent[node]
        if node_parent is None:
            return
        append_joins_for(node_parent)
        join_order.append((node_parent, node))

    for table in sorted(tables - {anchor}):
        append_joins_for(table)

    deduped: List[Tuple[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    for edge in join_order:
        if edge not in seen:
            seen.add(edge)
            deduped.append(edge)
    return deduped


def _join_clause(from_table: str, to_table: str, from_alias: str, to_alias: str) -> str:
    template = JOIN_EDGE_SQL.get((from_table, to_table))
    if not template:
        raise ValueError(f"No join template from '{from_table}' to '{to_table}'")
    return template.format(parent=from_alias, child=to_alias)


def build_multi_table_fetch_query(
    entity_type: str,
    column_checks: List[Dict[str, Any]],
) -> str:
    """Build SQL that fetches columns from one or more joined tables."""
    checks = normalize_checks_table_names(column_checks)
    tables = {check["table_name"] for check in checks}
    anchor = resolve_anchor_table(entity_type, tables)
    query_tables = set(tables) | {anchor}

    aliases = {table: TABLE_ALIASES[table] for table in query_tables}
    join_order = _plan_join_order(anchor, query_tables)

    select_parts = [
        f'{aliases[check["table_name"]]}.{check["column"]} AS "{column_result_key(check["table_name"], check["column"])}"'
        for check in checks
    ]

    join_clauses = [
        _join_clause(parent, child, aliases[parent], aliases[child])
        for parent, child in join_order
    ]

    entity_col, entity_filter = _entity_select_and_filter(entity_type, anchor)
    imported_filters = [
        f"{aliases[table]}.imported_at = (SELECT MAX(imported_at) FROM {table})"
        for table in sorted(query_tables)
    ]

    anchor_alias = aliases[anchor]
    joins_sql = "\n            ".join(join_clauses)
    return f"""
            SELECT DISTINCT {entity_col} AS "Entity", {", ".join(select_parts)}
            FROM {anchor} {anchor_alias}
            {joins_sql}
            WHERE {entity_filter}
            AND {" AND ".join(imported_filters)}
        """


def build_fetch_query(
    entity_type: str,
    column_checks: List[Dict[str, Any]],
) -> str:
    """Build a parameterized SQL query to fetch rows for custom rule evaluation."""
    return build_multi_table_fetch_query(entity_type, column_checks)


def validate_custom_rule_payload(
    entity_type: str,
    column_checks: List[Dict[str, Any]],
) -> None:
    if entity_type not in {"cell", "site"}:
        raise ValueError("entity_type must be 'cell' or 'site'")

    if not column_checks:
        raise ValueError("At least one column check is required")

    checks = normalize_checks_table_names(column_checks)
    seen_pairs: Set[Tuple[str, str]] = set()

    for check in checks:
        check_table = check["table_name"]
        col = check.get("column", "")
        rule_type = check.get("rule_type", "")

        table = TABLE_BY_NAME.get(check_table)
        if not table:
            raise ValueError(f"Invalid table_name: {check_table}")

        if entity_type not in table["entity_types"]:
            raise ValueError(f"Table '{check_table}' is not available for entity type '{entity_type}'")

        pair = (check_table, col)
        if pair in seen_pairs:
            raise ValueError(f"Duplicate column check for '{check_table}.{col}'")
        seen_pairs.add(pair)

        if rule_type not in VALID_RULE_TYPES:
            raise ValueError(f"Invalid rule_type: {rule_type}")

        allowed_columns = {c["name"] for c in table["columns"]}
        if col not in allowed_columns:
            raise ValueError(f"Column '{col}' is not allowed for table '{check_table}'")

        validate_rule_type_for_column(check_table, col, rule_type)
        validate_rule_params_for_column(check_table, col, rule_type, check.get("rule_params") or {})

    tables = {check["table_name"] for check in checks}
    anchor = resolve_anchor_table(entity_type, tables)
    _plan_join_order(anchor, set(tables) | {anchor})
