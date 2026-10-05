from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryResult(BaseModel):
    success: bool = Field(description="Whether the query executed successfully")
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = Field(default=0)
    error: str | None = Field(default=None)


class BulkStatementResult(BaseModel):
    index: int
    success: bool
    error: str | None = None


class BulkQueryResult(BaseModel):
    success: bool = Field(description="Whether all statements completed successfully")
    statement_results: list[BulkStatementResult] = Field(default_factory=list)
    executed_count: int = Field(default=0)
    error: str | None = Field(default=None)
