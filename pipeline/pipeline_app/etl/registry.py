"""
Flow registry — single source of truth for all pipeline flow definitions.

Each FlowSpec entry carries:
    - name:       identity key (matches FLOW_REGISTRY dict key)
    - category:   dispatch selector ("entity" | "audit")
    - run_type:   value written to pipeline_metadata.run_type
    - execute:    the flow function callable
    - depends_on: flow names that must succeed before this one runs
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Tuple

from pipeline_app.etl.flows.location import execute_location_flow
from pipeline_app.etl.flows.mu import execute_mu_flow
from pipeline_app.etl.flows.cell import execute_cell_flow
from pipeline_app.etl.flows.audit import run_audit_flow


@dataclass(frozen=True)
class FlowSpec:
    """Static configuration for a single pipeline flow."""

    name: str
    category: str
    run_type: str
    execute: Callable
    depends_on: Tuple[str, ...] = ()


FLOW_REGISTRY: Dict[str, FlowSpec] = {
    "location": FlowSpec(
        name="location",
        category="entity",
        run_type="pipeline",
        execute=execute_location_flow,
    ),
    "mu": FlowSpec(
        name="mu",
        category="entity",
        run_type="pipeline",
        execute=execute_mu_flow,
        depends_on=("location",),
    ),
    "cell": FlowSpec(
        name="cell",
        category="entity",
        run_type="pipeline",
        execute=execute_cell_flow,
        depends_on=("mu",),
    ),
    "audit": FlowSpec(
        name="audit",
        category="audit",
        run_type="audit_import",
        execute=run_audit_flow,
    ),
}
