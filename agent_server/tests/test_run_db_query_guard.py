"""Tests that run_db_query guards the database before executing anything."""

import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("deepagents")

from computer.tools import database_context  # noqa: E402
from shared_server_libs.agent_db_access.domain.schema.query_result import (  # noqa: E402
    QueryResult,
)


@pytest.fixture
def repository(monkeypatch):
    repo = AsyncMock()

    @asynccontextmanager
    async def fake_get_repository(project_name):
        yield repo

    monkeypatch.setattr(database_context, "get_repository", fake_get_repository)
    return repo


def _run(query, params=None):
    tool = database_context._make_run_db_query_tool("proj", "user@example.com")
    args = {"query": query}
    if params is not None:
        args["params"] = params
    return asyncio.run(tool.ainvoke(args))


def test_write_query_never_reaches_the_database(repository):
    result = json.loads(_run("UPDATE t SET x = 1 WHERE id IN (SELECT id FROM s)"))
    assert result["success"] is False
    assert "UPDATE" in result["error"]
    repository.run_query.assert_not_awaited()


def test_explain_runs_before_the_real_query(repository):
    repository.run_query.return_value = QueryResult(
        success=True, columns=["n"], rows=[[1]], row_count=1
    )
    _run("SELECT n FROM t", params={"a": 1})

    explain_call, real_call = repository.run_query.await_args_list
    assert explain_call.args[2] == "EXPLAIN SELECT n FROM t"
    assert real_call.args[2] == "SELECT n FROM t"


def test_failed_explain_skips_execution(repository):
    repository.run_query.return_value = QueryResult(
        success=False, error='column "nope" does not exist'
    )
    result = json.loads(_run("SELECT nope FROM t"))

    assert result["success"] is False
    assert "EXPLAIN validation" in result["error"]
    assert 'column "nope" does not exist' in result["error"]
    assert repository.run_query.await_count == 1
