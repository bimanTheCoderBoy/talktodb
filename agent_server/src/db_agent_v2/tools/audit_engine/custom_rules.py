"""Execute user-defined custom audit rules."""
import logging
import re
from typing import Any, Dict, List, Optional

from .base import AuditFunctionResult
from .catalog import build_multi_table_fetch_query, column_result_key, custom_rule_key
from .functions.helpers import generate_generic_markdown

logger = logging.getLogger(__name__)


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


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_column(rule_type: str, value: Any, rule_params: Dict[str, Any]) -> bool:
    """Return True when the column value passes the rule."""
    if rule_type == "not_null":
        return value is not None

    if rule_type == "boolean_true":
        return _coerce_bool(value) is True

    if rule_type == "boolean_false":
        return _coerce_bool(value) is False

    if rule_type == "in_range":
        num = _to_float(value)
        if num is None:
            return False
        min_val = _to_float(rule_params.get("min"))
        max_val = _to_float(rule_params.get("max"))
        if min_val is None or max_val is None:
            return False
        return min_val <= num <= max_val

    if rule_type in {"gt", "lt", "gte", "lte"}:
        num = _to_float(value)
        threshold = _to_float(rule_params.get("value"))
        if num is None or threshold is None:
            return False
        if rule_type == "gt":
            return num > threshold
        if rule_type == "lt":
            return num < threshold
        if rule_type == "gte":
            return num >= threshold
        return num <= threshold

    if rule_type == "eq":
        expected = rule_params.get("value")
        if value is None:
            return expected is None
        return str(value) == str(expected)

    if rule_type == "neq":
        expected = rule_params.get("value")
        if value is None:
            return expected is not None
        return str(value) != str(expected)

    if rule_type == "regex":
        if value is None:
            return False
        pattern = str(rule_params.get("pattern", ""))
        return re.search(pattern, str(value)) is not None

    return False


def normalize_column_checks(rule) -> List[Dict[str, Any]]:
    """Return column checks stored on the rule."""
    stored = getattr(rule, "column_checks", None) or []
    if not stored:
        raise ValueError(f"Custom rule {getattr(rule, 'id', '?')} has no column_checks")
    return list(stored)


def _check_result_key(check: Dict[str, Any]) -> str:
    return column_result_key(check["table_name"], check["column"])


def evaluate_row_checks(row: Dict[str, Any], column_checks: List[Dict[str, Any]]) -> bool:
    """All column checks must pass (AND logic)."""
    return all(
        evaluate_column(
            check["rule_type"],
            row.get(_check_result_key(check)),
            check.get("rule_params") or {},
        )
        for check in column_checks
    )


class CustomAuditRuleExecutor:
    """Runs a single user-defined audit rule."""

    def __init__(self, db_manager, rule):
        self.db_manager = db_manager
        self.rule = rule

    @property
    def name(self) -> str:
        return custom_rule_key(self.rule.id)

    @property
    def display_name(self) -> str:
        return self.rule.name

    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        try:
            if not entity_names:
                stats = {"total": 0, "yes": 0, "no": 0, "yes_label": "Compliant", "no_label": "Non-compliant", "rate_label": "Compliance rate"}
                md_data = generate_generic_markdown(self.display_name, self.rule.description or "Custom audit rule", [], stats)
                return AuditFunctionResult(
                    summary=f"{self.display_name}: No entities to audit",
                    md_data=md_data,
                    raw_data=[],
                    stats=stats,
                )

            column_checks = normalize_column_checks(self.rule)
            display_columns = [
                _check_result_key(check) for check in column_checks
            ]
            query = build_multi_table_fetch_query(self.rule.entity_type, column_checks)
            result = await self.db_manager.execute_query(project_name, query, user_email, (entity_names,))
            if not result["status"]:
                raise Exception(result["error"])

            rows = result["data"] or []
            evaluated_rows: List[Dict[str, Any]] = []
            yes_count = 0
            no_count = 0

            for row in rows:
                passed = evaluate_row_checks(row, column_checks)
                status = "Compliant" if passed else "Non-compliant"
                if passed:
                    yes_count += 1
                else:
                    no_count += 1
                evaluated_rows.append({**row, "Status": status})

            stats = {
                "total": len(evaluated_rows),
                "yes": yes_count,
                "no": no_count,
                "yes_label": "Compliant",
                "no_label": "Non-compliant",
                "rate_label": "Compliance rate",
            }

            description = self.rule.description or f"Custom rule on {', '.join(display_columns)}"
            md_data = generate_generic_markdown(
                self.display_name, description, evaluated_rows, stats, display_columns
            )

            return AuditFunctionResult(
                summary=f"{self.display_name}: {stats['yes']}/{stats['total']} records compliant",
                md_data=md_data,
                raw_data=evaluated_rows,
                stats=stats,
            )
        except Exception as exc:
            logger.error("Error executing custom rule %s: %s", self.rule.id, exc)
            return AuditFunctionResult(
                summary=f"Error in {self.display_name}",
                md_data=f"Error: {str(exc)}",
                error=str(exc),
                success=False,
            )
