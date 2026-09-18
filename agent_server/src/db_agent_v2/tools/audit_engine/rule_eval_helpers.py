"""Shared evaluation helpers for configurable built-in audit rules."""
from typing import Any, Dict, List, Optional, Tuple


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_missing(value: Any) -> bool:
    """True when a DB value is unset or displayed as N/A."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "n/a", "na", "null", "none"}
    return False


def _coerce_expected_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "t", "yes", "1"}:
            return True
        if text in {"false", "f", "no", "0"}:
            return False
    return default


def _coerce_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "t", "yes", "1"}:
        return True
    if text in {"false", "f", "no", "0"}:
        return False
    return None


def value_in_range(value: Any, min_val: Optional[float], max_val: Optional[float]) -> bool:
    num = _to_float(value)
    if num is None:
        return False
    if min_val is not None and num < min_val:
        return False
    if max_val is not None and num > max_val:
        return False
    return True


def evaluate_pci_compliance(
    rows: List[Dict[str, Any]],
    pci_column: str,
    pci_min: float,
    pci_max: float,
    cell_name_col: str = "Cell Name",
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    evaluated = []
    compliant = 0
    configured = 0
    for row in rows:
        pci = row.get(pci_column)
        if pci is None:
            status = "Not configured"
        else:
            configured += 1
            if value_in_range(pci, pci_min, pci_max):
                status = "Compliant"
                compliant += 1
            else:
                status = "Non-compliant"
        evaluated.append({**row, "Status": status})
    stats = {
        "total": len(evaluated),
        "yes": compliant,
        "no": len(evaluated) - compliant,
        "configured": configured,
        "yes_label": "Compliant",
        "no_label": "Non-compliant",
        "rate_label": "Compliance rate",
    }
    return evaluated, stats


def evaluate_expected_boolean(
    rows: List[Dict[str, Any]],
    column: str,
    expected: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Configured if not null; compliant if value equals expected."""
    evaluated = []
    compliant = 0
    for row in rows:
        raw = row.get(column)
        if _is_missing(raw):
            status = "Not configured"
        elif _coerce_bool(raw) == expected:
            status = "Compliant"
            compliant += 1
        else:
            status = "Non-compliant (configured)"
        evaluated.append({**row, "Status": status})
    stats = {
        "total": len(evaluated),
        "yes": compliant,
        "no": len(evaluated) - compliant,
        "yes_label": "Compliant",
        "no_label": "Non-compliant / not configured",
        "rate_label": "Compliance rate",
    }
    return evaluated, stats


def evaluate_boolean_columns(
    rows: List[Dict[str, Any]],
    columns: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    columns: [{key, label, enabled, require_true}]
    Row compliant if all enabled columns pass (not null; if require_true then must be True).
    """
    enabled = [c for c in columns if c.get("enabled", True)]
    evaluated = []
    compliant = 0
    for row in rows:
        status = "Compliant"
        for col in enabled:
            val = row.get(col["key"])
            if _is_missing(val):
                status = "Not configured"
                break
            if col.get("require_true") and _coerce_bool(val) is not True:
                status = "Non-compliant"
                break
        if status == "Compliant":
            compliant += 1
        evaluated.append({**row, "Status": status})
    stats = {
        "total": len(evaluated),
        "yes": compliant,
        "no": len(evaluated) - compliant,
        "yes_label": "Compliant",
        "no_label": "Non-compliant / not configured",
        "rate_label": "Compliance rate",
    }
    return evaluated, stats


def evaluate_numeric_columns(
    rows: List[Dict[str, Any]],
    columns: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    columns: [{key, label, enabled, min, max, require_value}]
    """
    enabled = [c for c in columns if c.get("enabled", True)]
    evaluated = []
    compliant = 0
    for row in rows:
        status = "Compliant"
        for col in enabled:
            val = row.get(col["key"])
            if _is_missing(val):
                status = "Not configured"
                break
            if not value_in_range(val, col.get("min"), col.get("max")):
                status = "Non-compliant"
                break
        if status == "Compliant":
            compliant += 1
        evaluated.append({**row, "Status": status})
    stats = {
        "total": len(evaluated),
        "yes": compliant,
        "no": len(evaluated) - compliant,
        "yes_label": "Compliant",
        "no_label": "Non-compliant / not configured",
        "rate_label": "Compliance rate",
    }
    return evaluated, stats


def evaluate_mu_mimo_columns(
    rows: List[Dict[str, Any]],
    boolean_columns: List[Dict[str, Any]],
    numeric_columns: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    enabled_bool = [c for c in boolean_columns if c.get("enabled", True)]
    enabled_num = [c for c in numeric_columns if c.get("enabled", True)]
    evaluated = []
    compliant = 0
    for row in rows:
        status = "Compliant"
        for col in enabled_bool:
            val = row.get(col["key"])
            if _is_missing(val):
                status = "Not configured"
                break
            if col.get("require_true") and _coerce_bool(val) is not True:
                status = "Non-compliant"
                break
        if status == "Compliant":
            for col in enabled_num:
                val = row.get(col["key"])
                if _is_missing(val):
                    status = "Not configured"
                    break
                if not value_in_range(val, col.get("min"), col.get("max")):
                    status = "Non-compliant"
                    break
        if status == "Compliant":
            compliant += 1
        evaluated.append({**row, "Status": status})
    stats = {
        "total": len(evaluated),
        "yes": compliant,
        "no": len(evaluated) - compliant,
        "yes_label": "Compliant",
        "no_label": "Non-compliant / not configured",
        "rate_label": "Compliance rate",
    }
    return evaluated, stats


def evaluate_pass_fail_column(
    rows: List[Dict[str, Any]],
    column: str,
    pass_value,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    evaluated = []
    compliant = 0
    for row in rows:
        raw = row.get(column)
        if _is_missing(raw):
            status = "Not configured"
        elif raw == pass_value:
            status = "Compliant"
            compliant += 1
        else:
            status = "Non-compliant"
        evaluated.append({**row, "Status": status})
    return evaluated, {
        "total": len(evaluated),
        "yes": compliant,
        "no": len(evaluated) - compliant,
        "yes_label": "Compliant",
        "no_label": "Non-compliant / not configured",
        "rate_label": "Compliance rate",
    }


def stats_from_status_column(rows: List[Dict[str, Any]], status_column: str = "Status", ok_value: str = "OK") -> Dict[str, int]:
    yes_count = sum(1 for row in rows if row.get(status_column) == ok_value)
    return {
        "total": len(rows),
        "yes": yes_count,
        "no": len(rows) - yes_count,
        "yes_label": "Compliant",
        "no_label": "Non-compliant",
        "rate_label": "Compliance rate",
    }


def evaluate_downtilt_rows(
    rows: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    use_db = config.get("use_db_constraints", True)
    fixed_min = config.get("fixed_min")
    fixed_max = config.get("fixed_max")
    evaluated = []
    compliant = 0
    for row in rows:
        tilt = _to_float(row.get("current_tilt"))
        if tilt is None:
            within = False
        elif use_db:
            min_t = _to_float(row.get("min_allowed_tilt"))
            max_t = _to_float(row.get("max_allowed_tilt"))
            min_t = 0 if min_t is None else min_t
            max_t = 90 if max_t is None else max_t
            within = min_t <= tilt <= max_t
        else:
            within = value_in_range(tilt, fixed_min, fixed_max)
        row = {**row, "within_compliance": "Yes" if within else "No", "Status": "Compliant" if within else "Non-compliant"}
        if within:
            compliant += 1
        evaluated.append(row)
    return evaluated, {
        "total": len(evaluated),
        "yes": compliant,
        "no": len(evaluated) - compliant,
        "yes_label": "Compliant",
        "no_label": "Non-compliant",
        "rate_label": "Compliance rate",
    }


def evaluate_cell_identity(
    rows: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    pci_min = float(config.get("pci_min", 0))
    pci_max = float(config.get("pci_max", 503))
    require_eci = config.get("require_eci", True)
    require_ecgi = config.get("require_ecgi", True)
    require_tac = config.get("require_tac", True)
    require_pci = config.get("require_pci", True)
    evaluated = []
    compliant = 0
    for row in rows:
        issues = []
        if require_eci and row.get("ECI") is None:
            issues.append("Missing ECI")
        if require_ecgi and row.get("ECGI") is None:
            issues.append("Missing ECGI")
        if require_tac and row.get("TAC") is None:
            issues.append("Missing TAC")
        pci = row.get("PCI")
        if require_pci and pci is None:
            issues.append("Missing PCI")
        elif pci is not None and not value_in_range(pci, pci_min, pci_max):
            issues.append(f"PCI out of range ({pci_min}-{pci_max})")
        status = "OK" if not issues else "; ".join(issues)
        if not issues:
            compliant += 1
        evaluated.append({**row, "Status": status})
    return evaluated, stats_from_status_column(evaluated)


def evaluate_rach_rsi(
    rows: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    rsi_min = float(config.get("rsi_min", 0))
    rsi_max = float(config.get("rsi_max", 837))
    require_rsi = config.get("require_rsi", True)
    rsi_col = "RSI"
    evaluated = []
    for row in rows:
        rsi = row.get(rsi_col)
        if rsi is None:
            status = "Missing" if require_rsi else "OK"
        elif not value_in_range(rsi, rsi_min, rsi_max):
            status = f"Out of range ({rsi_min}-{rsi_max})"
        else:
            status = "OK"
        evaluated.append({**row, "Status": status})
    return evaluated, stats_from_status_column(evaluated)


def evaluate_rf_power(
    rows: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    tx_min = float(config.get("tx_min_dbm", 10))
    tx_max = float(config.get("tx_max_dbm", 60))
    require_rs = config.get("require_rs_power", True)
    tx_col = "Max Tx Power (dBm)"
    rs_col = "RS Power/RE (dBm)"
    evaluated = []
    for row in rows:
        tx = row.get(tx_col)
        rs = row.get(rs_col)
        if tx is None:
            status = "Missing Tx Power"
        elif not value_in_range(tx, tx_min, tx_max):
            status = f"Tx Power out of range ({tx_min}-{tx_max} dBm)"
        elif require_rs and rs_col in row and rs is None:
            status = "Missing RS Power"
        else:
            status = "OK"
        evaluated.append({**row, "Status": status})
    return evaluated, stats_from_status_column(evaluated)


def evaluate_site_beamforming(
    rows: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    expected = config.get("expected_outcome", "Yes")
    min_cells = int(config.get("min_cells_with_beamforming", 1))
    evaluated = []
    compliant = 0
    for row in rows:
        bf = row.get("beamforming_support")
        num_cells = int(row.get("num_cells") or 0)
        passed = bf == expected
        if expected == "Yes" and min_cells > 0:
            # Site passes if outcome matches AND has enough cells with beamforming when Yes expected
            passed = bf == "Yes" and num_cells >= min_cells
        elif expected == "No":
            passed = bf == "No"
        if passed:
            compliant += 1
        evaluated.append({**row, "Status": "Compliant" if passed else "Non-compliant"})
    return evaluated, {
        "total": len(evaluated),
        "yes": compliant,
        "no": len(evaluated) - compliant,
        "yes_label": "Compliant",
        "no_label": "Non-compliant",
        "rate_label": "Compliance rate",
    }


def build_column_specs(
    all_columns: List[Dict[str, Any]],
    config_columns: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Merge user column config with defaults."""
    if not config_columns:
        return all_columns
    by_key = {c["key"]: c for c in all_columns}
    merged = []
    for user_col in config_columns:
        key = user_col.get("key")
        if key not in by_key:
            continue
        base = dict(by_key[key])
        base.update({k: v for k, v in user_col.items() if v is not None})
        merged.append(base)
    return merged or all_columns
