import asyncio
from contextlib import asynccontextmanager
import contextlib
import time
from api.db.database import user_db_session
from api.db.models import UserProjectConfig
from sqlalchemy import select, func
from typing import Any, Dict, List, Optional, Sequence, Tuple
from db_agent_v2.tools.asset_db_rag.DBRagPromptTemplate import FUZZY_IDENTIFIER
from security.encryption.iid_hash_utils import hash_iid
import asyncpg
import logging
import json

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
                hashed = [hash_iid(iid) for iid in raw_iids]
                logger.info(f"[RLS-DEBUG] raw_iids count={len(raw_iids)}, first 5 raw: {raw_iids[:5]}")
                logger.info(f"[RLS-DEBUG] hashed_iids count={len(hashed)}, first 5 hashed: {hashed[:5]}")
                return hashed
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
        Execute a SQL query with transaction-local RLS scope settings.

        Sets session variables (app.scope_mode, app.scoped_cell_iids) inside a
        transaction so RLS policies can filter rows. The settings are transaction-local
        (set_config with is_local=true) so they auto-clear when the transaction ends,
        preventing scope leakage across pooled connections.

        Args:
            project_name: Target database name.
            query: SQL query string.
            params: Optional positional parameters ($1, $2, ...).
            scoped_cell_iids: List of cell IIDs to restrict results to. If None or empty,
                              runs in 'unrestricted' mode (all rows visible).

        Returns:
            Same dict format as execute_query().
        """
        try:
            scoped_cell_iids = await self.find_scope_cell_iids(project_name, user_email)
            logger.info(f"[DATABASE MANAGER] Scope cell iids: {len(scoped_cell_iids)}")



            if not scoped_cell_iids or len(scoped_cell_iids) == 0:
                raise ValueError("No scope cell iids found for the user")

            # Extract cell names from the query's WHERE clause for debugging
            import re as _re
            _where_cell_names = _re.findall(r"lower\s*\(\s*'([^']+)'\s*\)", query, _re.IGNORECASE)
            if _where_cell_names:
                for _cn in _where_cell_names:
                    _found = _cn in scoped_cell_iids
                    _found_lower = _cn.lower() in [s.lower() for s in scoped_cell_iids]
                    logger.info(f"[RLS-DEBUG] WHERE references '{_cn}' -> exact_match_in_scope={_found}, case_insensitive_match={_found_lower}")

            async with self.connection(project_name) as conn:
                async with conn.transaction():
                    mode = "restricted" if (scoped_cell_iids and len(scoped_cell_iids) > 0) else "unrestricted"
                    logger.info(f"[RLS-DEBUG] scope_mode={mode}, scoped_iids_count={len(scoped_cell_iids or [])}")
                    logger.info(f"[RLS-DEBUG] Query (first 300 chars): {query[:300]}")
                    await conn.execute(
                        "SELECT set_config('app.scope_mode', $1, true)",
                        mode,
                    )
                    await conn.execute(
                        "SELECT set_config('app.scoped_cell_iids', $1, true)",
                        json.dumps(scoped_cell_iids or []),
                    )

                    if params is None:
                        records = await conn.fetch(query)
                    else:
                        records = await conn.fetch(query, *params)

            logger.info(f"[RLS-DEBUG] Query returned {len(records)} rows")

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
            logger.error(f"[RLS-DEBUG] execute_query EXCEPTION: {e}")
            return {
                "status": False,
                "columns": [],
                "data": [],
                "count": 0,
                "error": str(e),
            }
    
    def _format_sql_value(self, val: Any) -> str:
        """Helper to convert Python types into raw SQL strings."""
        try:
            if val is None:
                return "NULL"
            if isinstance(val, bool):
                return "TRUE" if val else "FALSE"
            if isinstance(val, (int, float)):
                return str(val)
            if isinstance(val, str):
            # Escape single quotes so the SQL syntax doesn't break
                escaped = val.replace("'", "''")
                return f"'{escaped}'"
            # Fallback for dates/other types
            escaped = str(val).replace("'", "''")
            return f"'{escaped}'"
        except Exception as e:
            logger.error(f"[DATABASE MANAGER] Error formatting SQL value: {e}")
            raise e
    
    def _bind_parameters(self, query: str, params: Tuple[Any, ...]) -> str:
        """Replaces $1, $2 with formatted values. Iterates backwards to handle $10 vs $1."""
        bound_query = query
        for i in range(len(params), 0, -1):
            val_str = self._format_sql_value(params[i-1])
            bound_query = bound_query.replace(f"${i}", val_str)
        return bound_query

    async def execute_bulk_queries(
        self,
        project_name: str,
        queries: List[Tuple[str, Tuple[Any, ...]]],
        user_email: str,
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
        logger.info(f"[DATABASE MANAGER] Executing bulk queries: {len(queries)}")
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

        formatted_queries = []
        for query, params in queries:
            formatted_queries.append(self._bind_parameters(query, params))
        
        logger.info(f"[DATABASE MANAGER] Formatted queries: {formatted_queries[0]}")
        
        json_payload = json.dumps(formatted_queries)

        success_count = 0
        failed_queries = []


        try:
            async with self.connection(project_name) as conn:
                scoped_cell_iids = await self.find_scope_cell_iids(project_name, user_email)
                mode = "restricted" if (scoped_cell_iids and len(scoped_cell_iids) > 0) else "unrestricted"

                cm = conn.transaction() if use_transaction else contextlib.nullcontext()

                async with cm:
                    await conn.execute(
                        "SELECT set_config('app.scope_mode', $1, true)",
                        mode,
                    )
                    await conn.execute(
                        "SELECT set_config('app.scoped_cell_iids', $1, true)",
                        json.dumps(scoped_cell_iids or []),
                    )
                    
                    await conn.execute("""
                        CREATE OR REPLACE FUNCTION pg_temp.execute_batch_json(q_array jsonb)
                        RETURNS jsonb AS $$
                        DECLARE
                             q text;
                             s_count int := 0;
                             f_queries jsonb := '[]'::jsonb;
                             err_msg text;
                        BEGIN
                            FOR q IN SELECT * FROM jsonb_array_elements_text(q_array)
                                LOOP
                                    BEGIN
                                        EXECUTE q;
                                        s_count := s_count + 1;
                                    EXCEPTION WHEN OTHERS THEN
                                        GET STACKED DIAGNOSTICS err_msg = MESSAGE_TEXT;
                                        f_queries := f_queries || jsonb_build_object(
                                             'query', q,
                                             'error', err_msg
                                        );
                                    END;
                                END LOOP;
                            RETURN jsonb_build_object(
                                'success_count', s_count,
                                'failed_queries', f_queries
                            );
                        END;
                        $$ LANGUAGE plpgsql;
                    """)
                
                    result = await conn.fetchval("SELECT pg_temp.execute_batch_json($1::jsonb)", json_payload)



                    result_data = json.loads(result)
                    success_count = result_data.get("success_count") or 0
                    failed_queries = result_data.get("failed_queries") or []

                    logger.info(f"[DATABASE MANAGER] Result: {result_data}")
                
                return {
                    "status": True,
                    "success_count": success_count,
                    "total_count": len(formatted_queries),
                    "failed_queries": failed_queries,
                    "error": None
                }
        except Exception as e:
            logger.error(f"[DATABASE MANAGER] Error executing bulk queries: {e}")
            return {
                "status": False,
                "success_count": success_count,
                "total_count": len(formatted_queries),
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
        fuzzy_flag = result.get("fuzzy_flag") or False
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

        if fuzzy_flag:
            logger.info(f"[DATABASE MANAGER] Fuzzy flag is True, adding fuzzy identifier")
            markdown += "\n\n"+FUZZY_IDENTIFIER
        # logger.info(f"[DATABASE MANAGER] Markdown: {markdown}")
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


