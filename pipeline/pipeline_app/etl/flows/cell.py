"""
Cell combined streaming flow (single API fetch -> split LTE / NR + extract antennas).

The EDS API returns all Cell records from one query type (Cellv214Type).
Each record is classified as LTE or NR, then mapped and upserted into the
corresponding table.  Feeder sub-records are extracted for physical and
logical antennas and inserted separately.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Set

from sqlalchemy.ext.asyncio import AsyncSession

from pipeline_app.core.config import APIConfig
from pipeline_app.core.json_mapper import JsonMapper
from pipeline_app.core.logging_service import LoggingService
from pipeline_app.db.engine import DatabaseManager
from pipeline_app.db.repository import (
    MetadataRepository,
    cell_lte_repo,
    cell_nr_repo,
    physical_antenna_repo,
    logical_antenna_repo,
)
from pipeline_app.etl.classifiers import is_lte_cell, is_nr_cell
from pipeline_app.etl.engine import StreamingEngine
from pipeline_app.etl.utils import FlowResult
from pipeline_app.schemas import (
    CellLTEModel,
    CellNRModel,
    CellPhysicalAntennaModel,
    CellLogicalAntennaModel,
)

logger = LoggingService.get_logger(__name__)

QUERY_TYPE = "Cellv214Type"


def _inject_context(cell: dict) -> None:
    """Inject parent context fields into a cell record in-place."""
    cell["mu_iid"] = cell.get("parent", {}).get("iid")
    cell["mu_eid"] = cell.get("parent", {}).get("eid")
    cell["cell_iid"] = cell.get("iid")
    cell["cell_eid"] = cell.get("eid")


def _extract_antenna_records(
    cell_records: List[dict],
    antenna_key: str,
) -> List[dict]:
    """Pull antenna dicts out of cell feeders, injecting parent context."""
    rows: List[dict] = []
    for cell in cell_records:
        mu_iid = cell.get("parent", {}).get("iid")
        mu_eid = cell.get("parent", {}).get("eid")
        loc_iid = cell.get("location", {}).get("iid")
        loc_eid = cell.get("location", {}).get("eid")
        cell_iid = cell.get("iid")
        cell_eid = cell.get("eid")

        for feeder in cell.get("feeders", []) or []:
            antenna = feeder.get(antenna_key)
            if antenna is None:
                continue
            if isinstance(antenna, dict):
                antenna = [antenna]
            for ant in antenna:
                ant["mu_iid"] = mu_iid
                ant["mu_eid"] = mu_eid
                ant["location_iid"] = loc_iid
                ant["location_eid"] = loc_eid
                ant["cell_iid"] = cell_iid
                ant["cell_eid"] = cell_eid
                rows.append(ant)
    return rows


async def execute_cell_flow(
    db: DatabaseManager,
    api_config: APIConfig,
    imported_at: datetime,
) -> FlowResult:
    """Stream Cell records from EDS, split by technology, upsert cells + insert antennas."""
    lte_mapper = JsonMapper(CellLTEModel)
    nr_mapper = JsonMapper(CellNRModel)
    phys_mapper = JsonMapper(CellPhysicalAntennaModel)
    log_mapper = JsonMapper(CellLogicalAntennaModel)
    engine = StreamingEngine(api_config, db, queue_size=10)

    meta_repo = MetadataRepository(db)
    valid_mu_lte_ids: Set[str] = await meta_repo.load_iid_set("mu_lte")
    valid_mu_nr_ids: Set[str] = await meta_repo.load_iid_set("mu_nr")
    logger.info(
        "Cell flow: loaded FK sets (mu_lte=%d, mu_nr=%d)",
        len(valid_mu_lte_ids),
        len(valid_mu_nr_ids),
    )

    async def handler(session: AsyncSession, page: List[dict]) -> Dict[str, int]:
        counts: Dict[str, int] = {}

        lte_cells = [r for r in page if is_lte_cell(r)]
        nr_cells = [r for r in page if is_nr_cell(r)]

        for cell in lte_cells + nr_cells:
            _inject_context(cell)

        physical_dicts = _extract_antenna_records(page, "physicalAntenna")
        logical_dicts = _extract_antenna_records(page, "logicalAntenna")

        lte_cells = [
            c for c in lte_cells
            if c.get("parent", {}).get("iid") in valid_mu_lte_ids
        ]
        nr_cells = [
            c for c in nr_cells
            if c.get("parent", {}).get("iid") in valid_mu_nr_ids
        ]

        if lte_cells:
            lte_models = lte_mapper.map_batch(lte_cells)
            counts["cell_lte"] = await cell_lte_repo.save_batch(
                session, lte_models, imported_at=imported_at,
            )

        if nr_cells:
            nr_models = nr_mapper.map_batch(nr_cells)
            counts["cell_nr"] = await cell_nr_repo.save_batch(
                session, nr_models, imported_at=imported_at,
            )

        if physical_dicts:
            phys_models = phys_mapper.map_batch(physical_dicts)
            counts["cell_physical_antenna"] = await physical_antenna_repo.save_batch(
                session, phys_models, imported_at=imported_at,
            )

        if logical_dicts:
            log_models = log_mapper.map_batch(logical_dicts)
            counts["cell_logical_antenna"] = await logical_antenna_repo.save_batch(
                session, log_models, imported_at=imported_at,
            )

        return counts

    return await engine.run("cell_combined", QUERY_TYPE, handler)
