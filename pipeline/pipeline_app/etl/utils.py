from __future__ import annotations
from dataclasses import dataclass, field
import random
from typing import Any, Callable, Coroutine, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import (
    OperationalError,
    DisconnectionError,
    TimeoutError
)

TRANSIENT_EXCEPTIONS = (
    OperationalError,
    DisconnectionError,
    TimeoutError
)

# Type Aliases

PageHandler = Callable[
    [AsyncSession, List[dict]],
    Coroutine[Any, Any, Dict[str, int]],
]

@dataclass
class FailedFetch:
    """API page that could not be fetched after all retries."""
    row_offset: int
    limit: int
    error: str

@dataclass
class FailedPage:
    """Page that was fetched but could not be inserted into the DB."""
    worker_id: int
    page: List[dict]
    error: str


@dataclass(frozen=True)
class FlowResult:
    """Immutable result of a single streaming flow execution."""

    entity: str
    api_success: bool
    db_success: bool
    total_fetched: int
    total_inserted: int
    rows_by_table: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    failed_fetches: List[FailedFetch] = field(default_factory=list)
    failed_pages: List[FailedPage] = field(default_factory=list)
    elapsed_seconds: float = 0.0


# Helper Functions

def is_retryable_error(status: int, body: str) -> bool:
    """Return True for server-side errors worth retrying."""
    if status == 500 and (
        "ORA-00028" in body
        or "session has been killed" in body.lower()
        or "Oracle.ManagedDataAccess" in body
    ):
        return True
    return status >= 500
    
def retry_delay(attempt: int) -> float:
    """Exponential backoff with jitter: 2^attempt ± 25% random."""
    base = 2 ** (attempt + 1)
    jitter = base * 0.25 * (2 * random.random() - 1)
    return max(0.5, base + jitter)


def is_transient_error(exc: Exception) -> bool:
    """Return True for SQLAlchemy exceptions worth retrying."""
    return isinstance(exc, TRANSIENT_EXCEPTIONS)