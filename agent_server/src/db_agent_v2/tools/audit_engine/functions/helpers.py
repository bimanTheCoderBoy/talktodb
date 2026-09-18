"""Shared helper functions for audit engine functions."""
from typing import List, Dict, Optional

# Telecom / RF abbreviations to keep fully uppercase in report labels.
_AUDIT_ABBREVIATIONS = {
    "lte": "LTE",
    "nr": "NR",
    "nrt": "NRT",
    "pci": "PCI",
    "tac": "TAC",
    "rsi": "RSI",
    "eci": "ECI",
    "ecgi": "ECGI",
    "mimo": "MIMO",
    "rach": "RACH",
    "rf": "RF",
    "tx": "TX",
    "rx": "RX",
    "ca": "CA",
    "su": "SU",
    "mu": "MU",
    "dl": "DL",
    "ul": "UL",
    "rs": "RS",
    "rsrp": "RSRP",
    "sinr": "SINR",
    "csi": "CSI",
    "ss": "SS",
    "arfcn": "ARFCN",
    "earfcn": "EARFCN",
    "prb": "PRB",
    "prbs": "PRBs",
    "iid": "IID",
}


def format_audit_label(name: str) -> str:
    """Humanize snake_case / spaced labels with telecom abbreviations in ALL CAPS.

    Examples:
        carrier_assignment_lte -> Carrier Assignment LTE
        pci -> PCI
        Cell Name -> Cell Name
    """
    if not name:
        return name
    parts = str(name).replace("_", " ").split()
    formatted = []
    for part in parts:
        key = part.lower()
        if key in _AUDIT_ABBREVIATIONS:
            formatted.append(_AUDIT_ABBREVIATIONS[key])
        else:
            formatted.append(part[:1].upper() + part[1:].lower() if part else part)
    return " ".join(formatted)


def calculate_configured_stats(rows: List[Dict], check_columns: List[str]) -> Dict[str, int]:
    """Parameter presence: configured if ANY check_column is non-NULL (0/False are valid values)."""
    yes_count = 0
    no_count = 0
    for row in rows:
        has_value = any(row.get(col) is not None for col in check_columns)
        if has_value:
            yes_count += 1
        else:
            no_count += 1
    return {
        "total": len(rows),
        "yes": yes_count,
        "no": no_count,
        "yes_label": "Configured",
        "no_label": "Not configured",
        "rate_label": "Configuration rate",
    }


def calculate_status_stats(
    rows: List[Dict],
    status_column: str = "Status",
    ok_value: str = "OK",
) -> Dict[str, int]:
    """Validation audits: compliant when status column equals ok_value (e.g. 'OK')."""
    yes_count = sum(1 for row in rows if row.get(status_column) == ok_value)
    no_count = len(rows) - yes_count
    return {
        "total": len(rows),
        "yes": yes_count,
        "no": no_count,
        "yes_label": "Compliant",
        "no_label": "Non-compliant",
        "rate_label": "Compliance rate",
    }


def calculate_pass_fail_stats(
    rows: List[Dict],
    column: str,
    pass_value,
    *,
    yes_label: str = "Compliant",
    no_label: str = "Non-compliant",
) -> Dict[str, int]:
    """Rule-based pass/fail (e.g. within_compliance='Yes', beamforming_support='Yes')."""
    yes_count = sum(1 for row in rows if row.get(column) == pass_value)
    no_count = len(rows) - yes_count
    return {
        "total": len(rows),
        "yes": yes_count,
        "no": no_count,
        "yes_label": yes_label,
        "no_label": no_label,
        "rate_label": "Compliance rate",
    }


# Backward-compatible alias used by older imports
def calculate_compliance_stats(rows: List[Dict], check_columns: List[str]) -> Dict[str, int]:
    return calculate_configured_stats(rows, check_columns)


def generate_generic_markdown(
    function_name: str,
    description: str,
    rows: List[Dict],
    stats: Optional[Dict] = None,
    check_columns: Optional[List[str]] = None,
) -> str:
    markdown = f"### {format_audit_label(function_name)}\n\n"
    markdown += f"**Purpose**: {description}\n\n"

    if stats:
        yes_label = stats.get("yes_label", "Compliant")
        no_label = stats.get("no_label", "Non-compliant")
        rate_label = stats.get("rate_label", "Compliance rate")
        markdown += "#### Summary Statistics\n\n"
        markdown += f"- **Total records analyzed**: {stats.get('total', 0)}\n"
        if "yes" in stats and "no" in stats:
            total = stats.get("total", 1) or 1
            compliance_rate = (stats.get("yes", 0) / total) * 100
            markdown += f"- **{yes_label} records**: {stats.get('yes', 0)} ({compliance_rate:.1f}%)\n"
            markdown += (
                f"- **{no_label} records**: {stats.get('no', 0)} ({100 - compliance_rate:.1f}%)\n"
            )
            markdown += f"- **{rate_label}**: {compliance_rate:.1f}%\n"
        markdown += "\n"

    if rows and len(rows) > 0:
        markdown += "#### Detailed Data Analysis\n\n"
        first_row = rows[0]
        columns = list(first_row.keys())
        display_columns = [format_audit_label(col) for col in columns]

        markdown += "**Data Table**:\n\n"
        markdown += "| " + " | ".join(display_columns) + " |\n"
        markdown += "| " + " | ".join(["---"] * len(columns)) + " |\n"

        for row in rows:
            row_data = []
            for col in columns:
                value = row.get(col, "")
                if value is None:
                    row_data.append("N/A")
                elif len(str(value)) > 50:
                    row_data.append(str(value)[:47] + "...")
                else:
                    row_data.append(str(value))
            markdown += "| " + " | ".join(row_data) + " |\n"

        markdown += "\n"

        # Charts whenever yes/no breakdown exists (check_columns optional, kept for callers)
        if stats and "yes" in stats and "no" in stats:
            total = stats.get("total", 1) or 1
            yes_count = stats.get("yes", 0)
            no_count = stats.get("no", 0)
            yes_pct = (yes_count / total) * 100
            no_pct = (no_count / total) * 100
            bar_len = 20
            yes_bar = round(yes_pct / 100 * bar_len)
            no_bar = bar_len - yes_bar
            chart_yes = stats.get("yes_label", "Compliant")
            chart_no = stats.get("no_label", "Non-compliant")

            markdown += "#### Data Visualization\n\n"
            markdown += f"**{chart_yes} vs {chart_no}**\n\n"
            markdown += "| Status | Count | % | Distribution |\n"
            markdown += "|--------|------:|--:|-------------|\n"
            markdown += (
                f"| {chart_yes} | {yes_count} | {yes_pct:.1f}% | "
                f"{'█' * yes_bar}{'░' * (bar_len - yes_bar)} |\n"
            )
            markdown += (
                f"| {chart_no} | {no_count} | {no_pct:.1f}% | "
                f"{'█' * no_bar}{'░' * (bar_len - no_bar)} |\n"
            )
            markdown += "\n"

    return markdown
