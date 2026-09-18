import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Sequence, Tuple
import logging
import asyncpg
from api.db.database import user_db_session
from api.db.models import UserProjectConfig
from sqlalchemy import select
import json
from db_agent_v2.config.tool_config import DBconfig
from security.encryption.iid_hash_utils import hash_iid

logger = logging.getLogger(__name__)


class DynamicAsyncDatabaseManager:
    """
    Async Postgres manager with **dynamic per-project pools**.

    - One base config (host/port/user/password)
    - For each `project_name`, lazily creates an `asyncpg.Pool`
      with `database=project_name`
    - Exposes high-level helpers:
        - `execute_query(...)`  -> run a query and get JSON-serializable dict
        - `connection(...)`     -> low-level access to a pooled connection
        - `close_all()`         -> graceful shutdown of all pools
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        min_size: int = 1,
        max_size: int = 10,
    ) -> None:
        # Base connection parameters shared by all projects.
        # Only the `database` (db name) changes per project.
        self._base_params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
        }

        # In-memory registry: project_name -> asyncpg.Pool
        self._pools: Dict[str, asyncpg.Pool] = {}

        # Pool sizing options (per project)
        self._min_size = min_size
        self._max_size = max_size

        # Protects concurrent access to `_pools` (creation & closing of pools).
        # Without this, two coroutines could try to create the same pool
        # at the same time, causing race conditions or duplicate pools.
        self._pools_lock = asyncio.Lock()

    async def _get_or_create_pool(self, project_name: str) -> asyncpg.Pool:
        """
        Lazily create (or reuse) a connection pool for the given `project_name`.

        This method is safe to call from multiple coroutines concurrently
        because it is guarded by `_pools_lock`.
        """
        async with self._pools_lock:
            pool = self._pools.get(project_name)
            if pool is None:
                # First time we see this project_name: create a new pool
                pool = await asyncpg.create_pool(
                    database=project_name.lower().strip(),
                    min_size=self._min_size,
                    max_size=self._max_size,
                    # 1. Disable looking for .pgpass file (prevents os.getcwd/open)
                    passfile=None,
                    # 2. Disable implicit SSL lookups (only if your DB doesn't need SSL)
                    ssl=False,
                    **self._base_params,
                )
                self._pools[project_name] = pool
            return pool

    @asynccontextmanager
    async def connection(self, project_name: str):
        """
        Async context manager to get a **single pooled connection**.

        How it works:
        - Awaits `_get_or_create_pool` to ensure the pool for this project exists.
        - Calls `pool.acquire()` to borrow a connection from that pool.
        - Yields the connection to the `async with` block.
        - When the block exits, the connection is automatically released
          back into the pool.

        Example:
            async with db_manager.connection(project_name) as conn:
                rows = await conn.fetch("SELECT 1")
        """
        pool = await self._get_or_create_pool(project_name)
        async with pool.acquire() as conn:
            yield conn
    
    async def find_scope_cell_iids(self, project_name: str, user_email: str) -> List[str]:
        """
        Find the scope cell iids for the given user email.
        Hashes raw IIDs when IID_HASHING_ENABLED is true so they match hashed DB values.
        """
        logger.info(f"[DATABASE MANAGER] Finding scope cell iids for user email: {user_email} and project name: {project_name}")
        async with user_db_session() as session:
            try:
                result = await session.execute(select(UserProjectConfig.cell_iids).where(UserProjectConfig.email == user_email, UserProjectConfig.project_name == project_name))
                raw_iids = result.scalar() or []
                return [hash_iid(iid) for iid in raw_iids]
            except Exception as e:
                logger.error(f"[DATABASE MANAGER] Error finding scope cell iids: {e}")
                return []

    async def execute_query(
        self,
        project_name: str,
        query: str,
        user_email: str,
        params: Optional[Sequence[Any]] = None,
    ) -> Dict[str, Any]:
        """
        High-level helper to execute a SQL query and get JSON-serializable data.

        - Uses the `connection(...)` async context manager to safely borrow
          and release a pooled connection.
        - Supports queries with or without positional parameters.
          Use `$1, $2, ...` placeholders in the SQL string and pass a
          tuple/list as `params`.

        Returns a dict shaped like:
            {
                "status": bool,
                "columns": [col1, col2, ...],
                "data": [ {col: value, ...}, ... ],
                "count": int,
                "error": Optional[str],
            }
        """
        try:

            scoped_cell_iids = await self.find_scope_cell_iids(project_name, user_email)
            logger.info(f"[DATABASE MANAGER] Scope cell iids: {len(scoped_cell_iids)}")
            
            
            if not scoped_cell_iids or len(scoped_cell_iids) == 0:
                raise ValueError("No scope cell iids found for the user")
            
            async with self.connection(project_name) as conn:
                async with conn.transaction():
                    mode = "restricted" if (scoped_cell_iids and len(scoped_cell_iids) > 0) else "unrestricted"
                    logger.info(f"[DATABASE MANAGER] Setting scope mode to {mode} with scoped cell iids: length {len(scoped_cell_iids or [])}")
                    await conn.execute(
                        "SELECT set_config('app.scope_mode', $1, true)",
                        mode,
                    )
                    await conn.execute(
                        "SELECT set_config('app.scoped_cell_iids', $1, true)",
                        json.dumps(scoped_cell_iids or []),
                    )
                    # Execute query with or without parameters
                    if params is None:
                        records = await conn.fetch(query)
                    else:
                        # params should match the $1, $2, ... placeholders in `query`
                        records = await conn.fetch(query, *params)

            # Convert asyncpg.Record objects into plain Python structures
            if records:
                columns: List[str] = list(records[0].keys())
                rows: List[Dict[str, Any]] = [dict(row) for row in records]
            else:
                columns = []
                rows = []

            return {
                "status": True,
                "columns": columns,
                "data": rows,
                "count": len(rows),
                "error": None,
            }

        except Exception as e:
            return {
                "status": False,
                "columns": [],
                "data": [],
                "count": 0,
                "error": str(e),
            }

    async def execute_bulk_queries(
        self,
        project_name: str,
        queries: List[Tuple[str, Tuple[Any, ...]]],
        use_transaction: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute multiple non-select queries (UPDATE, DELETE, INSERT) in bulk using executemany optimization.

        Args:
            project_name: Target database name.
            queries: List of (query_string, params_tuple).
            use_transaction: Whether to wrap all queries in a single transaction.

        Returns:
            Dict with status, success_count, total_count, failed_queries, error.
        """
        success_count = 0
        failed_queries = []

        if not queries:
            return {
                "status": True,
                "success_count": 0,
                "total_count": 0,
                "failed_queries": [],
                "error": None
            }

        # Group adjacent identical queries to utilize executemany
        groups = []
        current_query = queries[0][0]
        current_params = [queries[0][1]]

        for q, p in queries[1:]:
            if q == current_query:
                current_params.append(p)
            else:
                groups.append((current_query, current_params))
                current_query = q
                current_params = [p]
        groups.append((current_query, current_params))

        try:
            async with self.connection(project_name) as conn:
                if use_transaction:
                    async with conn.transaction():
                        for query, params_list in groups:
                            try:
                                await conn.executemany(query, params_list)
                                success_count += len(params_list)
                            except Exception as e:
                                # If executemany fails, the whole batch fails.
                                failed_queries.append({
                                    "query": query,
                                    "params_batch_size": len(params_list),
                                    "error": str(e)
                                })
                                raise e  # Re-raise to trigger rollback of transaction
                else:
                    # No transaction - best effort
                    for query, params_list in groups:
                        try:
                            await conn.executemany(query, params_list)
                            success_count += len(params_list)
                        except Exception as e:
                            # Record failure for this batch
                            failed_queries.append({
                                "query": query,
                                "params_batch_size": len(params_list),
                                "error": str(e)
                            })

            return {
                "status": len(failed_queries) == 0,
                "success_count": success_count,
                "total_count": len(queries),
                "failed_queries": failed_queries,
                "error": None
            }

        except Exception as e:
            # Top level exception (e.g. connection failure or transaction rollback error)
            return {
                "status": False,
                "success_count": success_count,
                "total_count": len(queries),
                "failed_queries": failed_queries,
                "error": str(e)
            }

    @staticmethod
    async def get_formatted_result(result: Dict[str, Any]) -> Tuple[List[str], List[Tuple[Any, ...]], str]:
        """
        Convert an execute_query()-style result into:
          - columns: list[str]
          - rows: list[tuple]
          - markdown: str (markdown table or human message)

        Returns (columns, rows, markdown)
        """
        # default empty outputs
        columns: List[str] = []
        rows: List[Tuple[Any, ...]] = []
        markdown: str = ""

        status: bool = bool(result.get("status"))
        error: Optional[str] = result.get("error")
        count: int = int(result.get("count") or 0)
        data = result.get("data") or []
        columns = result.get("columns") or []

        if not status:
            # Error from DB / execution
            markdown = "**Error Executing Query**\n\n" + (str(error) if error is not None else "Unknown error")
            return columns, rows, markdown

        if count == 0 or not data:
            markdown = "**Query Result**\n\nNo data found."
            return columns, rows, markdown

        # Build rows as tuples in the same column order
        try:
            rows = [tuple(row.get(col) for col in columns) for row in data]
        except Exception as exc:
            # If something unexpected happened converting rows
            markdown = "**Query Result**\n\nError formatting rows: " + str(exc)
            return columns, rows, markdown

        # Build markdown table
        if not columns:
            markdown = "**Query Result**\n\nNo columns found."
            return columns, rows, markdown

        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join(["---"] * len(columns)) + " |"
        body_lines = []
        for r in rows:
            body_lines.append("| " + " | ".join("" if x is None else str(x) for x in r) + " |")

        markdown = "\n".join([header, separator] + body_lines)
        return columns, rows, markdown

    async def close_all(self) -> None:
        """
        Gracefully close all pools; call on shutdown.
        """
        async with self._pools_lock:
            for pool in self._pools.values():
                await pool.close()
            self._pools.clear()


global_db_manager: DynamicAsyncDatabaseManager | None = None


def init_db_manager(host: str, port: int, user: str, password: str, min_size: int = 1, max_size: int = 10) -> None:
    global global_db_manager
    if global_db_manager is None:
        global_db_manager = DynamicAsyncDatabaseManager(host, port, user, password, min_size, max_size)

db_config = DBconfig()
def get_global_db_manager() -> DynamicAsyncDatabaseManager:
    global global_db_manager
    if global_db_manager is None:
        init_db_manager(db_config.host, db_config.port, db_config.user, db_config.password, db_config.min_size, db_config.max_size)
    return global_db_manager

