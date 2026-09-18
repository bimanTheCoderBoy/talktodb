"""
MU combined streaming flow (single API fetch -> split LTE / NR -> upsert both).

The EDS API returns all MU records from one query type. Each record is
classified as LTE, NR, or both, then mapped and upserted into the
corresponding table.
"""

from __future__ import annotations

from datetime import datetime

from pipeline_app.core.config import APIConfig
from pipeline_app.core.json_mapper import JsonMapper
from pipeline_app.core.logging_service import LoggingService
from pipeline_app.db.engine import DatabaseManager
from pipeline_app.db.repository import mu_lte_repo, mu_nr_repo
from pipeline_app.etl.classifiers import is_lte_mu, is_nr_mu
from pipeline_app.etl.engine import StreamingEngine
from pipeline_app.etl.utils import FlowResult
from pipeline_app.schemas import MuLTEModel, MuNRModel

logger = LoggingService.get_logger(__name__)

QUERY_TYPE = "MUNodev214Type"


async def execute_mu_flow(
    db: DatabaseManager,
    api_config: APIConfig,
    imported_at: datetime,
) -> FlowResult:
    """Stream MU records from EDS, split by technology, upsert both."""
    lte_mapper = JsonMapper(MuLTEModel)
    nr_mapper = JsonMapper(MuNRModel)
    engine = StreamingEngine(api_config, db)

    async def handler(session, page):
        counts = {}

        lte_records = [r for r in page if is_lte_mu(r)]
        nr_records = [r for r in page if is_nr_mu(r)]

        if lte_records:
            lte_models = lte_mapper.map_batch(lte_records)
            counts["mu_lte"] = await mu_lte_repo.save_batch(
                session, lte_models, imported_at=imported_at,
            )

        if nr_records:
            nr_models = nr_mapper.map_batch(nr_records)
            counts["mu_nr"] = await mu_nr_repo.save_batch(
                session, nr_models, imported_at=imported_at,
            )

        return counts

    return await engine.run("mu_combined", QUERY_TYPE, handler)
