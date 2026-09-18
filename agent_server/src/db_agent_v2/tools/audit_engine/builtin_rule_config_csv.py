"""Export/import customizable built-in audit rule configs as normalized CSV."""
from __future__ import annotations

import csv
import io
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Set, Tuple

from .builtin_rule_catalog import (
    BUILTIN_RULE_DEFAULTS,
    CUSTOMIZABLE_BUILTIN_RULE_KEYS,
    get_customizable_rule_schema,
    merge_rule_config,
)

CSV_HEADERS = ("rule_key", "rule_name", "setting", "value_type", "value")

_BOOL_TRUE = {"true", "t", "yes", "y", "1"}
_BOOL_FALSE = {"false", "f", "no", "n", "0"}

_COLUMN_PATH_RE = re.compile(
    r"^(?P<field>columns|boolean_columns|numeric_columns)\.(?P<col_key>[a-z0-9_]+)\.(?P<attr>enabled|require_true|require_value|min|max)$"
)


def rule_display_name(rule_key: str) -> str:
    """Return a human-readable rule name for CSV export."""
    from .functions.helpers import format_audit_label

    return format_audit_label(rule_key)


def _bool_to_str(value: Any) -> str:
    if value is None:
        return "false"
    if isinstance(value, bool):
        return "true" if value else "false"
    return "true" if str(value).strip().lower() in _BOOL_TRUE else "false"


def _select_to_str(value: Any) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def _number_to_str(value: Any) -> str:
    if value is None or value == "":
        return ""
    return str(value)


def _parse_bool(value: str) -> bool:
    text = (value or "").strip().lower()
    if text in _BOOL_TRUE:
        return True
    if text in _BOOL_FALSE:
        return False
    raise ValueError(f"invalid boolean value '{value}'")


def _parse_number(value: str) -> Optional[float]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        number = float(text)
        if number.is_integer():
            return int(number)
        return number
    except ValueError as exc:
        raise ValueError(f"invalid number value '{value}'") from exc


def _parse_select_value(field_key: str, value: str) -> Any:
    text = (value or "").strip()
    if field_key == "expected_value":
        lowered = text.lower()
        if lowered in _BOOL_TRUE:
            return True
        if lowered in _BOOL_FALSE:
            return False
        raise ValueError(f"expected_value must be True or False, got '{value}'")
    if field_key == "expected_outcome":
        lowered = text.lower()
        if lowered in {"yes", "y"}:
            return "Yes"
        if lowered in {"no", "n"}:
            return "No"
        if text in {"Yes", "No"}:
            return text
        raise ValueError(f"expected_outcome must be Yes or No, got '{value}'")
    return text


def _allowed_simple_settings(rule_key: str) -> Dict[str, str]:
    schema = get_customizable_rule_schema(rule_key)
    if not schema:
        return {}
    allowed: Dict[str, str] = {}
    for field in schema.get("fields", []):
        field_type = field["type"]
        if field_type in {"number", "boolean", "select"}:
            allowed[field["key"]] = field_type
        elif field_type == "metric_toggles":
            for metric_key in (schema.get("defaults", {}).get("metrics") or {}).keys():
                allowed[f"metrics.{metric_key}"] = "boolean"
        elif field_type in {"boolean_columns", "numeric_columns"}:
            field_key = field["key"]
            default_cols = schema.get("defaults", {}).get(field_key) or []
            is_numeric = field_type == "numeric_columns"
            for col in default_cols:
                col_key = col["key"]
                allowed[f"{field_key}.{col_key}.enabled"] = "boolean"
                if is_numeric:
                    allowed[f"{field_key}.{col_key}.require_value"] = "boolean"
                    allowed[f"{field_key}.{col_key}.min"] = "number"
                    allowed[f"{field_key}.{col_key}.max"] = "number"
                else:
                    allowed[f"{field_key}.{col_key}.require_true"] = "boolean"
    return allowed


def flatten_rule_config(rule_key: str, rule_name: str, config: Dict[str, Any]) -> List[Dict[str, str]]:
    """Flatten a merged rule config into normalized CSV rows."""
    schema = get_customizable_rule_schema(rule_key)
    if not schema:
        return []

    rows: List[Dict[str, str]] = []
    for field in schema.get("fields", []):
        field_key = field["key"]
        field_type = field["type"]

        if field_type == "number":
            rows.append({
                "rule_key": rule_key,
                "rule_name": rule_name,
                "setting": field_key,
                "value_type": "number",
                "value": _number_to_str(config.get(field_key)),
            })
        elif field_type == "boolean":
            rows.append({
                "rule_key": rule_key,
                "rule_name": rule_name,
                "setting": field_key,
                "value_type": "boolean",
                "value": _bool_to_str(config.get(field_key)),
            })
        elif field_type == "select":
            rows.append({
                "rule_key": rule_key,
                "rule_name": rule_name,
                "setting": field_key,
                "value_type": "select",
                "value": _select_to_str(config.get(field_key)),
            })
        elif field_type == "boolean_columns":
            for col in config.get(field_key) or []:
                col_key = col["key"]
                rows.append({
                    "rule_key": rule_key,
                    "rule_name": rule_name,
                    "setting": f"{field_key}.{col_key}.enabled",
                    "value_type": "boolean",
                    "value": _bool_to_str(col.get("enabled", True)),
                })
                rows.append({
                    "rule_key": rule_key,
                    "rule_name": rule_name,
                    "setting": f"{field_key}.{col_key}.require_true",
                    "value_type": "boolean",
                    "value": _bool_to_str(col.get("require_true", True)),
                })
        elif field_type == "numeric_columns":
            for col in config.get(field_key) or []:
                col_key = col["key"]
                rows.append({
                    "rule_key": rule_key,
                    "rule_name": rule_name,
                    "setting": f"{field_key}.{col_key}.enabled",
                    "value_type": "boolean",
                    "value": _bool_to_str(col.get("enabled", True)),
                })
                rows.append({
                    "rule_key": rule_key,
                    "rule_name": rule_name,
                    "setting": f"{field_key}.{col_key}.require_value",
                    "value_type": "boolean",
                    "value": _bool_to_str(col.get("require_value")),
                })
                rows.append({
                    "rule_key": rule_key,
                    "rule_name": rule_name,
                    "setting": f"{field_key}.{col_key}.min",
                    "value_type": "number",
                    "value": _number_to_str(col.get("min")),
                })
                rows.append({
                    "rule_key": rule_key,
                    "rule_name": rule_name,
                    "setting": f"{field_key}.{col_key}.max",
                    "value_type": "number",
                    "value": _number_to_str(col.get("max")),
                })
        elif field_type == "metric_toggles":
            for metric_key, enabled in (config.get("metrics") or {}).items():
                rows.append({
                    "rule_key": rule_key,
                    "rule_name": rule_name,
                    "setting": f"metrics.{metric_key}",
                    "value_type": "boolean",
                    "value": _bool_to_str(enabled),
                })
    return rows


def build_export_csv(
    user_configs: Dict[str, Dict[str, Any]],
    rule_names: Optional[Dict[str, str]] = None,
) -> str:
    """Build CSV containing merged defaults + saved user values for all customizable rules."""
    rule_names = rule_names or {}
    all_rows: List[Dict[str, str]] = []

    for rule_key in sorted(CUSTOMIZABLE_BUILTIN_RULE_KEYS):
        overrides = user_configs.get(rule_key)
        merged = merge_rule_config(rule_key, overrides)
        display = rule_names.get(rule_key) or rule_display_name(rule_key)
        all_rows.extend(flatten_rule_config(rule_key, display, merged))

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_HEADERS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(all_rows)
    return buffer.getvalue()


def _apply_setting(
    config: Dict[str, Any],
    rule_key: str,
    setting: str,
    value_type: str,
    raw_value: str,
) -> None:
    allowed = _allowed_simple_settings(rule_key)
    if setting not in allowed:
        raise ValueError(f"unknown setting '{setting}' for rule '{rule_key}'")
    if allowed[setting] != value_type:
        raise ValueError(
            f"value_type '{value_type}' does not match expected '{allowed[setting]}' for setting '{setting}'"
        )

    if value_type == "boolean":
        config.setdefault("metrics", {})
        if setting.startswith("metrics."):
            metric_key = setting.split(".", 1)[1]
            config["metrics"][metric_key] = _parse_bool(raw_value)
            return

        match = _COLUMN_PATH_RE.match(setting)
        if not match:
            config[setting] = _parse_bool(raw_value)
            return

        field_key = match.group("field")
        col_key = match.group("col_key")
        attr = match.group("attr")
        columns = config.setdefault(field_key, deepcopy(BUILTIN_RULE_DEFAULTS[rule_key].get(field_key, [])))
        col = next((c for c in columns if c.get("key") == col_key), None)
        if col is None:
            raise ValueError(f"unknown column '{col_key}' for rule '{rule_key}'")
        col[attr] = _parse_bool(raw_value)
        return

    if value_type == "number":
        match = _COLUMN_PATH_RE.match(setting)
        if match:
            field_key = match.group("field")
            col_key = match.group("col_key")
            attr = match.group("attr")
            columns = config.setdefault(field_key, deepcopy(BUILTIN_RULE_DEFAULTS[rule_key].get(field_key, [])))
            col = next((c for c in columns if c.get("key") == col_key), None)
            if col is None:
                raise ValueError(f"unknown column '{col_key}' for rule '{rule_key}'")
            col[attr] = _parse_number(raw_value)
            return
        config[setting] = _parse_number(raw_value)
        return

    if value_type == "select":
        simple_key = setting.split(".", 1)[0]
        config[setting] = _parse_select_value(simple_key, raw_value)
        return

    raise ValueError(f"unsupported value_type '{value_type}'")


def _validate_column_ranges(config: Dict[str, Any], rule_key: str) -> None:
    schema = get_customizable_rule_schema(rule_key)
    if not schema:
        return
    for field in schema.get("fields", []):
        if field["type"] != "numeric_columns":
            continue
        for col in config.get(field["key"]) or []:
            min_val = col.get("min")
            max_val = col.get("max")
            if min_val is not None and max_val is not None and min_val > max_val:
                raise ValueError(
                    f"min must be <= max for {field['key']}.{col.get('key')} in rule '{rule_key}'"
                )


def parse_import_csv(csv_content: str) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Parse uploaded CSV into rule_key -> config mappings."""
    reader = csv.DictReader(io.StringIO(csv_content))
    if not reader.fieldnames:
        raise ValueError("CSV file is empty or missing a header row")

    normalized_headers = {h.strip().lower(): h for h in reader.fieldnames if h}
    missing = [h for h in CSV_HEADERS if h not in normalized_headers]
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

    parsed_rows: List[Dict[str, str]] = []
    errors: List[str] = []
    seen: Set[Tuple[str, str]] = set()

    for line_no, row in enumerate(reader, start=2):
        rule_key = (row.get(normalized_headers["rule_key"]) or "").strip()
        setting = (row.get(normalized_headers["setting"]) or "").strip()
        value_type = (row.get(normalized_headers["value_type"]) or "").strip().lower()
        value = row.get(normalized_headers["value"], "")

        if not rule_key and not setting:
            continue
        if not rule_key:
            errors.append(f"Line {line_no}: rule_key is required")
            continue
        if rule_key not in CUSTOMIZABLE_BUILTIN_RULE_KEYS:
            errors.append(f"Line {line_no}: unknown or non-customizable rule_key '{rule_key}'")
            continue
        if not setting:
            errors.append(f"Line {line_no}: setting is required for rule '{rule_key}'")
            continue
        if not value_type:
            errors.append(f"Line {line_no}: value_type is required for rule '{rule_key}'")
            continue

        dedupe_key = (rule_key, setting)
        if dedupe_key in seen:
            errors.append(f"Line {line_no}: duplicate setting '{setting}' for rule '{rule_key}'")
            continue
        seen.add(dedupe_key)
        parsed_rows.append({
            "rule_key": rule_key,
            "setting": setting,
            "value_type": value_type,
            "value": value if value is not None else "",
        })

    if errors:
        return {}, errors

    configs: Dict[str, Dict[str, Any]] = {}
    for row in parsed_rows:
        rule_key = row["rule_key"]
        if rule_key not in configs:
            configs[rule_key] = deepcopy(BUILTIN_RULE_DEFAULTS[rule_key])
        try:
            _apply_setting(
                configs[rule_key],
                rule_key,
                row["setting"],
                row["value_type"],
                row["value"],
            )
        except ValueError as exc:
            errors.append(f"Rule '{rule_key}', setting '{row['setting']}': {exc}")

    for rule_key, config in configs.items():
        try:
            _validate_column_ranges(config, rule_key)
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        return {}, errors
    return configs, []
