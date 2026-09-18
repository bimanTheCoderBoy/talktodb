"""Apply user-configurable parameters to built-in audit rule results."""
from typing import Any, Dict, List, Optional, Tuple

from .builtin_rule_catalog import CUSTOMIZABLE_BUILTIN_RULE_KEYS
from .rule_eval_helpers import (
    _coerce_expected_bool,
    evaluate_boolean_columns,
    evaluate_cell_identity,
    evaluate_downtilt_rows,
    evaluate_expected_boolean,
    evaluate_mu_mimo_columns,
    evaluate_numeric_columns,
    evaluate_pci_compliance,
    evaluate_rach_rsi,
    evaluate_rf_power,
    evaluate_site_beamforming,
    stats_from_status_column,
)


def is_customizable(rule_key: str) -> bool:
    return rule_key in CUSTOMIZABLE_BUILTIN_RULE_KEYS


def evaluate_configurable_rule(
    rule_key: str,
    config: Dict[str, Any],
    rows: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Evaluate rows using merged rule config. Returns (rows_with_status, stats)."""
    if rule_key.startswith("carrier_assignment"):
        return evaluate_pci_compliance(
            rows,
            config.get("pci_column", "pci"),
            float(config.get("pci_min", 0)),
            float(config.get("pci_max", 503)),
        )

    if rule_key.startswith("carrier_aggregation"):
        column = config.get("column", "lte_carrierparameters_caenabledatcell")
        expected = _coerce_expected_bool(config.get("expected_value", True))
        return evaluate_expected_boolean(rows, column, expected)

    if rule_key.startswith("su_mimo"):
        return evaluate_boolean_columns(rows, config.get("columns", []))

    if rule_key.startswith("mu_mimo"):
        return evaluate_mu_mimo_columns(
            rows,
            config.get("boolean_columns", []),
            config.get("numeric_columns", []),
        )

    if rule_key.startswith("rx_tx_elements"):
        return evaluate_numeric_columns(rows, config.get("columns", []))

    if rule_key.startswith("beamforming_support_lte"):
        return evaluate_boolean_columns(rows, config.get("columns", []))

    if rule_key.startswith("beamforming_support_nr"):
        # NR beamforming audit uses Yes/No string column
        expected = "Yes"
        cols = config.get("columns", [])
        if cols:
            enabled = [c for c in cols if c.get("enabled", True)]
            if enabled and not any(c.get("require_true", True) for c in enabled):
                expected = "No"
        from .rule_eval_helpers import evaluate_pass_fail_column
        return evaluate_pass_fail_column(rows, "beamforming_support", expected)

    if rule_key.startswith(("signal_thresholds", "coverage_range", "interference", "cell_load", "coverage_and_height", "antenna_orientation")):
        return evaluate_numeric_columns(rows, config.get("columns", []))

    if rule_key.startswith("downtilt_compliance"):
        return evaluate_downtilt_rows(rows, config)

    if rule_key.startswith("cell_identity"):
        return evaluate_cell_identity(rows, config)

    if rule_key.startswith("rach_rsi"):
        return evaluate_rach_rsi(rows, config)

    if rule_key.startswith("rf_power"):
        return evaluate_rf_power(rows, config)

    if rule_key == "beamforming_support":
        return evaluate_site_beamforming(rows, config)

    return rows, stats_from_status_column(rows)


def build_cell_high_level_markdown(
    stats: Dict[str, Any],
    config: Dict[str, Any],
    *,
    tech_label: str = "LTE",
) -> str:
    """Build markdown for cell high-level stats respecting metric toggles."""
    metrics = config.get("metrics", {})
    total = stats.get("total", 0)
    total_with_antenna = stats.get("total_with_antenna", 0)

    identity_metrics = [
        ("eci_assigned", "ECI Assigned"),
        ("ecgi_assigned", "ECGI Assigned"),
        ("tac_assigned", "TAC Assigned"),
        ("carrier_assigned", "PCI Assigned"),
        ("rsi_assigned", "RACH RSI Assigned"),
        ("tx_power_configured", "Max Tx Power Set"),
        ("rs_power_configured", "RS Power (PPRE) Set"),
        ("bandwidth_configured", "Bandwidth Configured"),
        ("carrier_earfcn_configured", "Carrier/EARFCN Set"),
    ]
    if tech_label == "NR":
        identity_metrics = [
            ("tac_assigned", "TAC Assigned"),
            ("carrier_assigned", "PCI Assigned"),
            ("rsi_assigned", "RACH RSI Assigned"),
            ("tx_power_configured", "Max Tx Power Set"),
            ("dl_arfcn_configured", "DL ARFCN Configured"),
            ("dl_prbs_configured", "DL PRBs (Bandwidth) Set"),
        ]
    feature_metrics = [
        ("carrier_aggregation_enabled", "Carrier Aggregation Enabled"),
        ("su_mimo_enabled", "SU-MIMO Enabled"),
        ("mu_mimo_enabled", "MU-MIMO Enabled"),
        ("beamforming_enabled", "Beamforming Enabled"),
        ("coverage_range_configured", "Coverage Range Configured"),
        ("cell_load_configured", "Cell Load Configured"),
        ("downtilt_compliant", "Downtilt Compliant"),
    ]

    md = f"### Cell High Level Statistics ({tech_label})\n\n"
    md += f"**Total Cells Analyzed**: {total}\n\n"

    identity_rows = [
        (key, label)
        for key, label in identity_metrics
        if metrics.get(key, True) and key in stats
    ]
    if identity_rows and total > 0:
        md += "#### Cell Identity & RF Parameters\n\n"
        md += "| Parameter | Configured | Percentage |\n"
        md += "|-----------|-----------|------------|\n"
        for key, label in identity_rows:
            count = stats.get(key, 0)
            md += f"| {label} | {count} | {(count / total * 100):.1f}% |\n"
        md += "\n"

    feature_rows = [
        (key, label)
        for key, label in feature_metrics
        if metrics.get(key, True) and key in stats
    ]
    if feature_rows and total > 0:
        md += "#### Feature Configuration\n\n"
        md += "| Feature | Count | Percentage |\n"
        md += "|---------|-------|------------|\n"
        for key, label in feature_rows:
            count = stats.get(key, 0)
            denom = total_with_antenna if key == "downtilt_compliant" and total_with_antenna > 0 else total
            pct = (count / denom * 100) if denom else 0
            md += f"| {label} | {count} | {pct:.1f}% |\n"
        md += "\n"

    if metrics.get("downtilt_compliant", True) and total_with_antenna > 0:
        md += f"*Note: Downtilt compliance calculated from {total_with_antenna} cells with antenna data.*\n"

    return md


def build_site_high_level_markdown(stats: Dict[str, Any], config: Dict[str, Any]) -> str:
    """Build markdown for site high-level stats respecting metric toggles."""
    metrics = config.get("metrics", {})
    total = stats.get("total", 0)
    total_cells = stats.get("total_cells", 0)
    lte_cells = stats.get("lte_cells", 0)
    nr_cells = stats.get("nr_cells", 0)
    avg_cells = stats.get("avg_cells_per_site", 0)

    md = "### Site High Level Statistics\n\n"
    md += f"**Total Sites Analyzed**: {total}\n\n"

    if metrics.get("total_cells", True) or metrics.get("lte_cells", True) or metrics.get("nr_cells", True):
        md += f"**Total Cells**: {total_cells}"
        parts = []
        if metrics.get("lte_cells", True):
            parts.append(f"LTE: {lte_cells}")
        if metrics.get("nr_cells", True):
            parts.append(f"NR: {nr_cells}")
        if parts:
            md += f" ({', '.join(parts)})"
        md += "\n"
        if metrics.get("total_cells", True) and total > 0:
            md += f"**Average Cells per Site**: {avg_cells:.1f}\n"
        md += "\n"

    table_metrics = [
        ("beamforming_supported", "Beamforming Supported"),
        ("sites_with_antennas", "Sites with Antennas"),
        ("sites_with_lte_tac", "Sites with LTE TAC"),
        ("sites_with_nr_tac", "Sites with NR TAC"),
    ]
    enabled = [(k, lbl) for k, lbl in table_metrics if metrics.get(k, True)]
    if enabled and total > 0:
        md += "#### Feature Configuration Counts\n\n"
        md += "| Feature | Count | Percentage |\n"
        md += "|---------|-------|------------|\n"
        for key, label in enabled:
            count = stats.get(key, 0)
            md += f"| {label} | {count} | {(count / total * 100):.1f}% |\n"
        md += "\n"

    return md


def filter_high_level_stats_dict(stats: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only enabled metrics in stats dict (always retain total/total_with_antenna)."""
    metrics = config.get("metrics", {})
    keep = {"total", "total_with_antenna", "total_cells", "lte_cells", "nr_cells", "avg_cells_per_site"}
    keep.update(k for k, enabled in metrics.items() if enabled)
    return {k: v for k, v in stats.items() if k in keep}


def apply_configurable_or_default(
    rule_key: str,
    config: Dict[str, Any],
    rows: List[Dict[str, Any]],
    default_stats_fn,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Use configurable evaluation when rule is customizable, else fall back."""
    if is_customizable(rule_key):
        return evaluate_configurable_rule(rule_key, config, rows)
    return rows, default_stats_fn(rows)
