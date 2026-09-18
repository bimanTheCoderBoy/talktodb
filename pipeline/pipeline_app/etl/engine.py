"""
Streaming producer-consumer pipeline engine.

Combines API page fetching and DB worker consumption into a single
class with connected backpressure: ``queue.put`` happens inside the
API semaphore so a full queue blocks further HTTP calls.

Public API:
    StreamingPipeline  -- reusable engine, call ``run()`` per entity flow
    FlowResult         -- frozen dataclass returned by each run
    PageHandler        -- type alias for the handler callable

Usage::

    pipeline = StreamingPipeline(api_config, db)

    async def handler(session, page):
        models = mapper.map_batch(page)
        count = await repo.save_batch(session, models)
        return {"entity": count}

    result = await pipeline.run("entity_name", "QueryType", handler)
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import orjson
from pipeline_app.core.config import APIConfig
from pipeline_app.core.logging_service import LoggingService
from pipeline_app.db.engine import DatabaseManager
from pipeline_app.etl.utils import (
    PageHandler, FlowResult, FailedFetch, FailedPage,
    is_retryable_error, is_transient_error, retry_delay,
)

logger = LoggingService.get_logger(__name__)

MAX_RETRIES = 3
_SENTINEL = None
MAX_DB_RETRIES = 3

class StreamingEngine:
    """Streams pages from the EDS API through a bounded queue to DB workers.

    One instance can be reused across multiple ``run()`` calls (e.g.
    Location -> MU -> Cell).  Each call is an independent execution with
    its own HTTP session, queue, semaphore, and workers.

    Backpressure design:
        ``queue.put(data)`` is called **inside** the API semaphore so that
        a full queue holds the semaphore slot, preventing new HTTP calls
        from starting.  At steady state the maximum pages in memory is
        bounded by ``queue_size + num_workers + api_concurrency``.

    Parameters
    ----------
    api_config : APIConfig
        EDS API connection and pagination settings.
    db : DatabaseManager
        Provides unmanaged async sessions for DB workers.
    queue_size : int, optional
        Bounded queue capacity.  Defaults to ``api_config.max_concurrent``.
    """

    def __init__(
        self,
        api_config: APIConfig,
        db: DatabaseManager,
        *,
        queue_size: Optional[int] = None,
    ) -> None:
        self._api_config = api_config
        self._db = db
        self._queue_size = queue_size or api_config.queue_size

        # Per-run state (set in run(), cleared after)
        self._http: Optional[aiohttp.ClientSession] = None
        self._queue: Optional[asyncio.Queue] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._url: str = ""
        self._headers: Dict[str, str] = {}
        self._timeout: int = 0
        self._max_results: int = 0
        self._query_filter: str = ""
        self._entity_name: str = ""
        self._num_workers: int = 0

    async def run(
        self,
        entity_name: str,
        query_type: str,
        handler: PageHandler,
    ) -> FlowResult:
        """Execute a complete streaming flow for one entity type.

        1. Opens an ``aiohttp`` session.
        2. Launches a producer task (handshake -> plan pages -> fetch).
        3. Launches *N* DB worker tasks (pop page -> handler -> commit).
        4. Waits for completion, aggregates results.

        Parameters
        ----------
        entity_name : str
            Human-readable name for logging (e.g. ``"location"``).
        query_type : str
            EDS API query type (e.g. ``"LocationObjectv214Type"``).
        handler : PageHandler
            ``async def handler(session, page) -> {"table": count}``
        """
        self._setup(entity_name, query_type)
        flow_start = time.perf_counter()
        errors: List[str] = []
        failed_fetches: List[FailedFetch] = []
        failed_pages: List[FailedPage] = []
        api_success = False
        total_fetched = 0

        async with aiohttp.ClientSession() as self._http:
            # --- Launch producer + workers concurrently ---
            producer_task = asyncio.create_task(
                self._produce(errors, failed_fetches),
                name=f"{entity_name}-producer",
            )
            worker_tasks = [
                asyncio.create_task(
                    self._consume(i, handler, errors, failed_pages),
                    name=f"{entity_name}-worker-{i}",
                )
                for i in range(self._num_workers)
            ]

            logger.info(
                "%s: streaming flow started (workers=%d, queue=%d, api_concurrency=%d)",
                entity_name,
                self._num_workers,
                self._queue_size,
                self._api_config.max_concurrent,
            )

            # Wait for producer, then workers
            total_fetched, api_success = await producer_task
            worker_results = await asyncio.gather(
                *worker_tasks, return_exceptions=True,
            )

        # --- Aggregate ---
        merged_counts: Dict[str, int] = {}
        for i, wr in enumerate(worker_results):
            if isinstance(wr, BaseException):
                errors.append(f"Worker-{i} crashed: {wr}")
                logger.error("%s worker-%d crashed: %s", entity_name, i, wr)
            else:
                for table, cnt in wr.items():
                    merged_counts[table] = merged_counts.get(table, 0) + cnt

        total_inserted = sum(merged_counts.values())
        elapsed = time.perf_counter() - flow_start

        logger.info(
            "%s flow complete: fetched=%d, inserted=%d, tables=%s, errors=%d, %.2fs",
            entity_name,
            total_fetched,
            total_inserted,
            merged_counts,
            len(errors),
            elapsed,
        )

        self._teardown()

        return FlowResult(
            entity=entity_name,
            api_success=api_success,
            db_success=len(errors) == 0,
            total_fetched=total_fetched,
            total_inserted=total_inserted,
            rows_by_table=merged_counts,
            errors=errors,
            failed_fetches=failed_fetches,
            failed_pages=failed_pages,
            elapsed_seconds=round(elapsed, 3),
        )

    async def _produce(
        self,
        errors: List[str],
        failed_fetches: List[FailedFetch],
    ) -> Tuple[int, bool]:
        """Handshake, plan pages, fetch concurrently into the queue.

        Returns ``(total_fetched, api_success)``.
        Sentinels are always sent in the ``finally`` block so workers
        shut down even on failure.
        """
        total_fetched = 0
        page_count = 0
        api_success = False

        try:
            # -- Handshake --
            logger.info(
                "%s: handshake (row=0, max=0)", self._entity_name,
            )
            handshake_data, next_row, remaining = await self._fetch_page(
                row=0, max_val=0,
            )

            if handshake_data:
                total_fetched += len(handshake_data)
                page_count += 1
                await self._queue.put(handshake_data)
                logger.info(
                    "%s: handshake returned %d records",
                    self._entity_name,
                    len(handshake_data),
                )

            start_row = (
                next_row
                if next_row is not None
                else len(handshake_data or [])
            )
            total_remaining = remaining if remaining is not None else 0

            logger.info(
                "%s: handshake done, start_row=%d, remaining=%d",
                self._entity_name,
                start_row,
                total_remaining,
            )

            if total_remaining <= 0:
                api_success = True
                return total_fetched, api_success

            # -- Plan pages --
            pages = self._plan_pages(start_row, total_remaining)
            logger.info(
                "%s: %d pages to fetch (concurrency=%d)",
                self._entity_name,
                len(pages),
                self._api_config.max_concurrent,
            )

            # -- Fetch concurrently, enqueue inside semaphore --
            fetch_counters: Dict[str, int] = {
                "fetched": 0, "pages": page_count,
            }

            async def _fetch_and_enqueue(row: int, limit: int) -> None:
                async with self._semaphore:
                    data, _, _ = await self._fetch_page(row, limit)
                    if data:
                        await self._queue.put(data)
                        fetch_counters["fetched"] += len(data)
                        fetch_counters["pages"] += 1
                        logger.info(
                            "%s producer: page %d enqueued (%d records, queue=%d/%d)",
                            self._entity_name,
                            fetch_counters["pages"],
                            len(data),
                            self._queue.qsize(),
                            self._queue_size,
                        )

            tasks = [
                asyncio.create_task(
                    _fetch_and_enqueue(r, lim),
                    name=f"{self._entity_name}-fetch-{r}",
                )
                for r, lim in pages
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect fetch errors and dead letters
            for i, result in enumerate(results):
                if isinstance(result, BaseException):
                    row_offset, limit = pages[i]
                    errors.append(f"Fetch row={row_offset}: {result}")
                    failed_fetches.append(FailedFetch(
                        row_offset=row_offset,
                        limit=limit,
                        error=str(result),
                    ))
                    logger.error(
                        "%s: fetch failed at row=%d: %s",
                        self._entity_name,
                        row_offset,
                        result,
                    )

            total_fetched += fetch_counters["fetched"]
            page_count = fetch_counters["pages"]
            api_success = not any(
                isinstance(r, BaseException) for r in results
            )

        except Exception as exc:
            errors.append(f"API error: {exc}")
            logger.error(
                "%s producer error: %s",
                self._entity_name,
                exc,
                exc_info=True,
            )
        finally:
            for _ in range(self._num_workers):
                await self._queue.put(_SENTINEL)
            logger.info(
                "%s producer: done (pages=%d, fetched=%d), sent %d sentinels",
                self._entity_name,
                page_count,
                total_fetched,
                self._num_workers,
            )

        return total_fetched, api_success

    async def _consume(
        self,
        worker_id: int,
        handler: PageHandler,
        errors: List[str],
        failed_pages: List[FailedPage],
    ) -> Dict[str, int]:
        """Pop pages from the queue, call *handler*, commit per page.

        Returns accumulated ``{table_name: row_count}`` for this worker.
        """
        table_counts: Dict[str, int] = {}
        pages_done = 0
        sess = self._db.unmanaged_session()

        try:
            while True:
                page = await self._queue.get()
                if page is _SENTINEL:
                    break

                for attempt in range(MAX_DB_RETRIES):
                    try:
                        counts = await handler(sess, page)
                        await sess.commit()
                        pages_done += 1
                        for table, cnt in counts.items():
                            table_counts[table] = table_counts.get(table, 0) + cnt
                        logger.info(
                            "%s worker-%d: page %d done %s (total: %s)",
                            self._entity_name,
                            worker_id,
                            pages_done,
                            counts,
                            table_counts,
                        )
                        break
                    except Exception as exc:
                        await sess.rollback()

                        if is_transient_error(exc) and attempt < MAX_DB_RETRIES - 1:
                            await sess.close()
                            sess = self._db.unmanaged_session()
                            delay = retry_delay(attempt)
                            logger.warning(
                                "%s worker-%d: transient error, retrying in %.1fs",
                                self._entity_name,
                                worker_id,
                                delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                        errors.append(f"Worker-{worker_id}: {exc}")
                        failed_pages.append(FailedPage(
                            worker_id=worker_id,
                            page=page,
                            error=str(exc),
                        ))
                        logger.error(
                            "%s worker-%d page error: %s",
                            self._entity_name,
                            worker_id,
                            exc,
                            exc_info=True,
                        )
                        break
        finally:
            await sess.close()
            logger.info(
                "%s worker-%d: shutting down (%d pages, %s)",
                self._entity_name,
                worker_id,
                pages_done,
                table_counts,
            )

        return table_counts

    async def _fetch_page(
        self, row: int, max_val: int,
    ) -> Tuple[List[Dict[str, Any]], Optional[int], Optional[int]]:
        """Fetch a single page from EDS with retry.

        Returns ``(records, next_row, remaining)``.
        Raises ``RuntimeError`` after all retries are exhausted.
        """
        params: Dict[str, Any] = {
            "format": "json",
            "row": row,
            "max": max_val,
            "timeout": self._timeout,
        }
        if self._query_filter:
            params["qry"] = self._query_filter

        client_timeout = aiohttp.ClientTimeout(total=self._timeout)
        last_error = ""

        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(
                    "%s: fetch row=%d max=%d (attempt %d/%d)",
                    self._entity_name,
                    row,
                    max_val,
                    attempt + 1,
                    MAX_RETRIES,
                )
                async with self._http.get(
                    self._url,
                    headers=self._headers,
                    params=params,
                    timeout=client_timeout,
                ) as resp:
                    if resp.status == 200:
                        data = orjson.loads(await resp.read())
                        app_data = data.get("appData", [])
                        summary = data.get("summary", {})
                        logger.debug(
                            "%s: fetched row=%d, received=%d",
                            self._entity_name,
                            row,
                            len(app_data),
                        )
                        return (
                            app_data,
                            summary.get("next"),
                            summary.get("remaining"),
                        )

                    body = await resp.text()
                    last_error = f"HTTP {resp.status}: {body[:300]}"

                    if (
                        is_retryable_error(resp.status, body)
                        and attempt < MAX_RETRIES - 1
                    ):
                        delay = retry_delay(attempt)
                        logger.warning(
                            "%s: retryable error row=%d (attempt %d/%d), "
                            "retry in %.1fs",
                            self._entity_name,
                            row,
                            attempt + 1,
                            MAX_RETRIES,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    raise RuntimeError(last_error)

            except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < MAX_RETRIES - 1:
                    delay = retry_delay(attempt)
                    logger.warning(
                        "%s: network error row=%d (attempt %d/%d): %s, "
                        "retry in %.1fs",
                        self._entity_name,
                        row,
                        attempt + 1,
                        MAX_RETRIES,
                        last_error,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise RuntimeError(last_error) from exc

        raise RuntimeError(
            f"All {MAX_RETRIES} retries exhausted for "
            f"{self._entity_name} row={row}: {last_error}"
        )

    def _plan_pages(
        self, start_row: int, remaining: int,
    ) -> List[Tuple[int, int]]:
        """Build a list of ``(row_offset, page_limit)`` tuples."""
        pages: List[Tuple[int, int]] = []
        current_row, left = start_row, remaining
        while left > 0:
            limit = min(self._max_results, left)
            pages.append((current_row, limit))
            current_row += limit
            left -= limit
        return pages

    def _setup(self, entity_name: str, query_type: str) -> None:
        """Initialise per-run state from config."""
        cfg = self._api_config
        self._entity_name = entity_name
        self._url = f"{cfg.base_url.rstrip('/')}/{query_type}"
        self._headers = cfg.get_headers()
        self._timeout = cfg.timeout
        self._max_results = cfg.max_results
        self._query_filter = cfg.query_filter or ""
        self._num_workers = self._db.pool_size
        self._queue = asyncio.Queue(maxsize=self._queue_size)
        self._semaphore = asyncio.Semaphore(cfg.max_concurrent)

    def _teardown(self) -> None:
        """Clear per-run state so the instance can be reused cleanly."""
        self._http = None
        self._queue = None
        self._semaphore = None
