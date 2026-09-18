"""
Pipeline result data structures — pure data, no DB or IO.

FlowOutcome:   uniform per-flow result built by the orchestrator.
PipelineResult: aggregate result of a full pipeline run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass(frozen=True)
class FlowOutcome:
    """Uniform result of a single flow execution.

    Built by the orchestrator from whatever the underlying flow returns
    (FlowResult, tuple, or dict).  The original return value is kept on
    ``raw`` for callers that need flow-specific details.
    """

    name: str
    status: str  # "success" | "failed" | "skipped"
    started_at: datetime
    completed_at: datetime
    elapsed_seconds: float
    total_fetched: int = 0
    total_inserted: int = 0
    rows_by_table: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    raw: Any = None


@dataclass
class PipelineResult:
    """Aggregate result returned by every ``PipelineOrchestrator.run_*`` method."""

    project_name: str
    imported_at: datetime
    outcomes: List[FlowOutcome]
    total_elapsed: float

    @property
    def success(self) -> bool:
        return all(o.status in ("success", "skipped") for o in self.outcomes)

    @property
    def total_fetched(self) -> int:
        return sum(o.total_fetched for o in self.outcomes)

    @property
    def total_inserted(self) -> int:
        return sum(o.total_inserted for o in self.outcomes)

    @property
    def failed_flows(self) -> List[str]:
        return [o.name for o in self.outcomes if o.status == "failed"]

    def summary(self) -> str:
        """Formatted text table for CLI / log output."""
        if not self.outcomes:
            return "  No flows executed.\n"

        name_w = max(len(o.name) for o in self.outcomes) + 2

        header = (
            f"  {'Flow':<{name_w}} {'Status':<9} {'Time':>9} "
            f"{'Fetched':>9} {'Inserted':>9}  Detail"
        )
        sep = "  " + "-" * (len(header) - 2)
        lines: List[str] = [header, sep]

        passed = failed = skipped = 0

        for o in self.outcomes:
            detail = ""
            if o.rows_by_table:
                detail = ", ".join(f"{t}={c}" for t, c in o.rows_by_table.items())
            elif o.errors:
                detail = o.errors[0][:60]

            time_str = _fmt_duration(o.elapsed_seconds)
            lines.append(
                f"  {o.name:<{name_w}} {o.status:<9} {time_str:>9} "
                f"{o.total_fetched:>9} {o.total_inserted:>9}  {detail}"
            )

            if o.status == "success":
                passed += 1
            elif o.status == "failed":
                failed += 1
            else:
                skipped += 1

        lines.append(sep)
        lines.append(
            f"  {'TOTAL':<{name_w}} {'':9} "
            f"{_fmt_duration(self.total_elapsed):>9} "
            f"{self.total_fetched:>9} {self.total_inserted:>9}"
        )
        lines.append("")
        lines.append(
            f"  Passed: {passed}  |  Failed: {failed}  |  Skipped: {skipped}"
        )
        return "\n".join(lines)


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(seconds, 60)
    return f"{int(m)}m {s:.0f}s"
