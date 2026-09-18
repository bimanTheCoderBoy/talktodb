"""
Pipeline orchestrator — unified entry point for running pipeline flows.

Responsibilities:
    - Database provisioning and lifecycle
    - Sequential flow execution in FK dependency order
    - Shared imported_at timestamp across all flows
    - Pipeline metadata recording after each flow
    - Dependency-aware skip on failure (fail_fast mode)
    - Aggregate result collection

Usage::

    config = PipelineConfig.from_env()
    async with PipelineOrchestrator(config) as orch:
        result = await orch.run_full_pipeline()
        print(result.summary())
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import List, Optional

from pipeline_app.core.config import PipelineConfig
from pipeline_app.core.logging_service import LoggingService
from pipeline_app.db.engine import DatabaseManager
from pipeline_app.db.repository import MetadataRepository
from pipeline_app.etl.registry import FlowSpec, FLOW_REGISTRY
from pipeline_app.etl.result import FlowOutcome, PipelineResult
from pipeline_app.etl.utils import FlowResult

logger = LoggingService.get_logger(__name__)


def _validate_flow_names(names: List[str]) -> None:
    unknown = set(names) - FLOW_REGISTRY.keys()
    if unknown:
        raise ValueError(f"Unknown flows: {unknown}. Valid: {sorted(FLOW_REGISTRY)}")


def _skipped_outcome(name: str) -> FlowOutcome:
    now = datetime.now()
    return FlowOutcome(
        name=name,
        status="skipped",
        started_at=now,
        completed_at=now,
        elapsed_seconds=0.0,
    )


class PipelineOrchestrator:
    """Orchestrates the full EDS pipeline lifecycle.

    Parameters
    ----------
    config:
        Full pipeline configuration.
    db:
        Optional externally-managed DatabaseManager.  When provided the
        orchestrator will NOT dispose it on exit — the caller owns it.
    imported_at:
        Shared snapshot timestamp.  Defaults to ``datetime.now()`` at
        ``__aenter__``.
    fail_fast:
        When True, skip flows whose dependency failed in this run.
    setup_rls:
        Passed to ``db.provision()``.
    """

    def __init__(
        self,
        config: PipelineConfig,
        *,
        db: Optional[DatabaseManager] = None,
        imported_at: Optional[datetime] = None,
        fail_fast: bool = True,
        setup_rls: bool = True,
    ) -> None:
        self._config = config
        self._external_db = db
        self._db: Optional[DatabaseManager] = db
        self._imported_at = imported_at
        self._fail_fast = fail_fast
        self._setup_rls = setup_rls
        self._meta_repo: Optional[MetadataRepository] = None

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "PipelineOrchestrator":
        if self._db is None:
            self._db = DatabaseManager.from_config(self._config)
        await self._db.provision(setup_rls=self._setup_rls)
        self._meta_repo = MetadataRepository(self._db)
        if self._imported_at is None:
            self._imported_at = datetime.now()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._external_db is None and self._db is not None:
            await self._db.dispose()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_full_pipeline(self) -> PipelineResult:
        """Run all flows: location -> mu -> cell -> audit (compare + import)."""
        return await self.run_flows(
            ["location", "mu", "cell", "audit"]
        )

    async def run_entity_flows(self) -> PipelineResult:
        """Run entity ingestion flows only: location -> mu -> cell."""
        return await self.run_flows(["location", "mu", "cell"])

    async def run_audit_flows(self) -> PipelineResult:
        """Run audit comparison and discrepancy import."""
        return await self.run_flows(["audit"])

    async def run_flows(self, flow_names: List[str]) -> PipelineResult:
        """Run an arbitrary ordered subset of registered flows."""
        _validate_flow_names(flow_names)
        wall_start = time.perf_counter()
        outcomes: List[FlowOutcome] = []

        for i, name in enumerate(flow_names):
            spec = FLOW_REGISTRY[name]
            logger.info(
                "Starting flow %d/%d: %s", i + 1, len(flow_names), name,
            )

            if self._should_skip(spec, outcomes):
                outcomes.append(_skipped_outcome(name))
                logger.info("Skipped %s (dependency failed)", name)
                continue

            outcome = await self._execute_flow(spec)
            await self._record_metadata(spec, outcome)
            outcomes.append(outcome)

            logger.info(
                "Flow %s: %s (%.1fs, fetched=%d, inserted=%d)",
                name,
                outcome.status,
                outcome.elapsed_seconds,
                outcome.total_fetched,
                outcome.total_inserted,
            )

        return PipelineResult(
            project_name=self._config.project_name,
            imported_at=self._imported_at,
            outcomes=outcomes,
            total_elapsed=time.perf_counter() - wall_start,
        )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _execute_flow(self, spec: FlowSpec) -> FlowOutcome:
        started_at = datetime.now()
        t0 = time.perf_counter()
        try:
            if spec.category == "entity":
                return await self._run_entity(spec, started_at, t0)
            elif spec.category == "audit":
                return await self._run_audit(spec, started_at, t0)
            else:
                raise ValueError(f"Unknown flow category: {spec.category}")
        except Exception as exc:
            logger.error("Flow %s failed: %s", spec.name, exc, exc_info=True)
            return FlowOutcome(
                name=spec.name,
                status="failed",
                started_at=started_at,
                completed_at=datetime.now(),
                elapsed_seconds=time.perf_counter() - t0,
                errors=[str(exc)],
            )

    # ------------------------------------------------------------------
    # Category runners
    # ------------------------------------------------------------------

    async def _run_entity(
        self, spec: FlowSpec, started_at: datetime, t0: float,
    ) -> FlowOutcome:
        result: FlowResult = await spec.execute(
            self._db, self._config.api, self._imported_at,
        )
        return FlowOutcome(
            name=spec.name,
            status="success" if result.db_success else "failed",
            started_at=started_at,
            completed_at=datetime.now(),
            elapsed_seconds=time.perf_counter() - t0,
            total_fetched=result.total_fetched,
            total_inserted=result.total_inserted,
            rows_by_table=dict(result.rows_by_table),
            errors=list(result.errors),
            raw=result,
        )

    async def _run_audit(
        self, spec: FlowSpec, started_at: datetime, t0: float,
    ) -> FlowOutcome:
        result = await spec.execute(
            self._db, self._config, imported_at=self._imported_at,
        )
        return FlowOutcome(
            name=spec.name,
            status="success" if result["success"] else "failed",
            started_at=started_at,
            completed_at=datetime.now(),
            elapsed_seconds=time.perf_counter() - t0,
            total_fetched=result.get("mismatch_count", 0),
            total_inserted=result.get("rows_imported", 0),
            errors=[result["error"]] if result.get("error") else [],
            raw=result,
        )

    # ------------------------------------------------------------------
    # Metadata recording
    # ------------------------------------------------------------------

    async def _record_metadata(
        self, spec: FlowSpec, outcome: FlowOutcome,
    ) -> None:
        if outcome.status == "skipped":
            return
        try:
            await self._meta_repo.record_flow(
                project_name=self._config.project_name,
                entity_type=spec.name,
                run_type=spec.run_type,
                total_records=outcome.total_fetched,
                records_processed=outcome.total_inserted,
                started_at=outcome.started_at,
                error_message="; ".join(outcome.errors) if outcome.errors else None,
            )
        except Exception as exc:
            logger.warning(
                "Failed to record metadata for %s: %s", spec.name, exc,
            )

    # ------------------------------------------------------------------
    # Dependency-aware skip
    # ------------------------------------------------------------------

    def _should_skip(
        self, spec: FlowSpec, outcomes: List[FlowOutcome],
    ) -> bool:
        if not self._fail_fast:
            return False
        failed_names = {o.name for o in outcomes if o.status == "failed"}
        return bool(failed_names & set(spec.depends_on))
