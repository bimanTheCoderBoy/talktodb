"""
Data access layer for the EDS pipeline.

Two components:
    EntityRepository   -- frozen dataclass for batch entity persistence (writes)
    MetadataRepository -- class for pipeline metadata and utility queries (reads + writes)

Private internals (_execute_upsert, _execute_insert) are the proven batch
engines from db_operation.py, moved here with zero logic changes.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Any, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline_app.core.logging_service import LoggingService
from pipeline_app.db.models.location import Location
from pipeline_app.db.models.mu import MuLTE, MuNR
from pipeline_app.db.models.cell import CellLTE, CellNR
from pipeline_app.db.models.antenna import CellPhysicalAntenna, CellLogicalAntenna
from pipeline_app.db.models.discrepancy import Discrepancy
from pipeline_app.db.models.pipeline_metadata import PipelineMetadata

logger = LoggingService.get_logger(__name__)

BATCH_SIZE = 500
PG_MAX_PARAMS = 32767

_SAFE_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _validate_identifier(name: str) -> str:
    if not name or not _SAFE_IDENT.fullmatch(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name

def _normalize_rows(rows: list[dict]) -> list[dict]:
    """Ensure every row dict has the same set of keys (missing keys -> None)."""
    all_keys: set[str] = set()
    for r in rows:
        all_keys.update(r.keys())
    return [{k: r.get(k) for k in all_keys} for r in rows]


async def _execute_upsert(
    session: AsyncSession,
    table_class,
    rows: list[dict],
    pk_col: str = "iid",
    imported_at: Optional[datetime] = None,
) -> int:
    """INSERT ... ON CONFLICT DO UPDATE, auto-splitting to respect the param limit."""
    if not rows:
        return 0

    if imported_at is not None:
        for r in rows:
            r["imported_at"] = imported_at

    rows = _normalize_rows(rows)
    num_cols = len(rows[0])
    safe_batch = min(BATCH_SIZE, max(1, PG_MAX_PARAMS // num_cols))

    count = 0
    for i in range(0, len(rows), safe_batch):
        batch = rows[i : i + safe_batch]
        stmt = pg_insert(table_class).values(batch)
        update_cols = {k: stmt.excluded[k] for k in batch[0] if k != pk_col}
        stmt = stmt.on_conflict_do_update(index_elements=[pk_col], set_=update_cols)
        await session.execute(stmt)
        count += len(batch)

    return count


async def _execute_insert(
    session: AsyncSession,
    table_class,
    rows: list[dict],
    imported_at: Optional[datetime] = None,
) -> int:
    """Plain INSERT (no conflict handling), auto-splitting to respect the param limit."""
    if not rows:
        return 0

    if imported_at is not None:
        for r in rows:
            r["imported_at"] = imported_at

    rows = _normalize_rows(rows)
    num_cols = len(rows[0])
    safe_batch = min(BATCH_SIZE, max(1, PG_MAX_PARAMS // num_cols))

    count = 0
    for i in range(0, len(rows), safe_batch):
        batch = rows[i : i + safe_batch]
        stmt = pg_insert(table_class).values(batch)
        await session.execute(stmt)
        count += len(batch)

    return count

def _location_to_dict(schema) -> dict:
    """Location-specific: adds PostGIS POINT geometry from lat/lon."""
    data = schema.model_dump(exclude_none=True)
    lon, lat = data.get("longitude"), data.get("latitude")
    if lon is not None and lat is not None:
        data["geom"] = f"SRID=4326;POINT({lon} {lat})"
    return data


@dataclass(frozen=True)
class EntityRepository:
    """Configuration for batch persistence of one entity type.

    Encapsulates: which table, which PK, upsert vs insert,
    and any pre-transform (e.g. Location's PostGIS geom builder).
    """
    table_class: type
    pk_col: str = "iid"
    use_upsert: bool = True
    pre_transform: Callable | None = None

    async def save_batch(
        self,
        session: AsyncSession,
        schemas: list,
        *,
        imported_at: Optional[datetime] = None,
    ) -> int:
        """Persist a batch of Pydantic models. Returns row count."""
        if self.pre_transform:
            rows = [self.pre_transform(s) for s in schemas]
        else:
            rows = [s.model_dump(exclude_none=True) for s in schemas]

        if self.use_upsert:
            return await _execute_upsert(
                session, self.table_class, rows, self.pk_col, imported_at,
            )
        return await _execute_insert(
            session, self.table_class, rows, imported_at,
        )


# Pre-built repository instances -- one per entity type
location_repo         = EntityRepository(Location, pre_transform=_location_to_dict)
mu_lte_repo           = EntityRepository(MuLTE)
mu_nr_repo            = EntityRepository(MuNR)
cell_lte_repo         = EntityRepository(CellLTE)
cell_nr_repo          = EntityRepository(CellNR)
physical_antenna_repo = EntityRepository(CellPhysicalAntenna, pk_col="id", use_upsert=False)
logical_antenna_repo  = EntityRepository(CellLogicalAntenna, pk_col="id", use_upsert=False)
discrepancy_repo      = EntityRepository(Discrepancy, pk_col="id", use_upsert=False)


class MetadataRepository:
    """Reads and writes against pipeline_metadata and utility queries.

    Receives a DatabaseManager and creates sessions internally via db.session().
    """

    def __init__(self, db):
        self._db = db

    async def record_flow(
        self,
        project_name: str,
        entity_type: str,
        run_type: str,
        total_records: int,
        records_processed: int,
        started_at: datetime,
        *,
        error_message: Optional[str] = None,
    ) -> None:
        """Insert one PipelineMetadata row."""
        async with self._db.session() as sess:
            sess.add(PipelineMetadata(
                project_name=project_name,
                entity_type=entity_type,
                run_type=run_type,
                status="failed" if error_message else "success",
                total_records=total_records,
                records_processed=records_processed,
                error_message=error_message,
                started_at=started_at,
                completed_at=datetime.now(),
            ))

    async def record_pending(
        self,
        project_name: str,
        entity_type: str,
        run_type: str,
    ) -> int:
        """Insert a PipelineMetadata row with status='pending'. Returns the row id."""
        row = PipelineMetadata(
            project_name=project_name,
            entity_type=entity_type,
            run_type=run_type,
            status="pending",
            total_records=0,
            records_processed=0,
            started_at=datetime.now(),
        )
        async with self._db.session() as sess:
            sess.add(row)
            await sess.flush()
            return row.id

    async def update_status(
        self,
        meta_id: int,
        status: str,
        total_records: int = 0,
        records_processed: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        """Update an existing PipelineMetadata row by id."""
        async with self._db.session() as sess:
            await sess.execute(
                text(
                    "UPDATE pipeline_metadata "
                    "SET status = :status, "
                    "    total_records = :total_records, "
                    "    records_processed = :records_processed, "
                    "    error_message = :error_message, "
                    "    completed_at = :completed_at "
                    "WHERE id = :id"
                ),
                {
                    "id": meta_id,
                    "status": status,
                    "total_records": total_records,
                    "records_processed": records_processed,
                    "error_message": error_message,
                    "completed_at": datetime.now(),
                },
            )

    async def get_latest_timestamp(
        self, table_name: str,
    ) -> Optional[datetime]:
        """Return MAX(imported_at) for a table."""
        safe = _validate_identifier(table_name)
        async with self._db.session() as sess:
            result = await sess.execute(
                text(f'SELECT MAX("imported_at") FROM "{safe}"')
            )
            return result.scalar()

    async def get_row_count(
        self, table_name: str, *, latest_only: bool = True,
    ) -> int:
        """Return row count -- total, or only rows from the latest import."""
        safe = _validate_identifier(table_name)
        if latest_only:
            query = text(
                f'SELECT COUNT(*) FROM "{safe}" '
                f'WHERE "imported_at" = (SELECT MAX("imported_at") FROM "{safe}")'
            )
        else:
            query = text(f'SELECT COUNT(*) FROM "{safe}"')

        async with self._db.session() as sess:
            result = await sess.execute(query)
            return int(result.scalar() or 0)

    async def get_summary(
        self,
        project_name: str,
        *,
        run_timestamp: Optional[datetime] = None,
        table_name: Optional[str] = None,
        technology: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Filtered query on pipeline_metadata."""
        clauses: List[str] = ["project_name = :project_name"]
        params: Dict[str, Any] = {"project_name": project_name}

        if run_timestamp is not None:
            clauses.append("started_at = :run_timestamp")
            params["run_timestamp"] = run_timestamp
        if table_name:
            clauses.append("entity_type LIKE :table_name")
            params["table_name"] = f"%{table_name}%"
        if technology:
            clauses.append("entity_type LIKE :technology")
            params["technology"] = f"%:{technology}%"

        where_sql = " AND ".join(clauses)
        async with self._db.session() as sess:
            result = await sess.execute(
                text(
                    "SELECT id, project_name, entity_type, run_type, status, "
                    "total_records, records_processed, error_message, "
                    "started_at, completed_at "
                    "FROM pipeline_metadata "
                    f"WHERE {where_sql} "
                    "ORDER BY started_at DESC, id DESC"
                ),
                params,
            )
            return [dict(r) for r in result.mappings().all()]

    async def load_iid_set(self, table_name: str) -> Set[str]:
        """Load all iid values from a table. Used for FK pre-validation."""
        safe = _validate_identifier(table_name)
        async with self._db.session() as sess:
            result = await sess.execute(text(f'SELECT iid FROM "{safe}"'))
            return {row[0] for row in result.fetchall() if row[0] is not None}

    async def fetch_table_df(self, table_name: str):
        """Fetch a full table into a pandas DataFrame. Used by audit flows."""
        import pandas as pd
        safe = _validate_identifier(table_name)
        async with self._db.session() as sess:
            result = await sess.execute(text(f'SELECT * FROM "{safe}"'))
            rows = result.fetchall()
            return pd.DataFrame(rows, columns=result.keys())
