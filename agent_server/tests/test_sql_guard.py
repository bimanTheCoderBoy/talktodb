"""Tests for the read-only SQL guard used by run_db_query."""

import pytest

from computer.utils.sql_guard import validate_read_only_sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "select * from cell_lte where iid = 10",
        "SELECT name, roll FROM students ORDER BY roll LIMIT 5",
        "WITH c AS (SELECT 1 AS x) SELECT * FROM c",
        "SELECT * FROM a UNION SELECT * FROM b",
        "SELECT (SELECT max(id) FROM s) AS m FROM t",
        "SELECT * FROM t WHERE id = :id",
        "SELECT * FROM t; ",
    ],
)
def test_accepts_read_only_queries(sql):
    is_read_only, reason = validate_read_only_sql(sql)
    assert is_read_only, reason
    assert reason is None


@pytest.mark.parametrize(
    "sql",
    [
        # Writes whose body contains a SELECT, which a prefix check would miss.
        "UPDATE t SET x = 1 WHERE id IN (SELECT id FROM s)",
        "INSERT INTO t SELECT * FROM s",
        "DELETE FROM t WHERE id IN (SELECT id FROM s)",
        "MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN UPDATE SET x = 1",
        "CREATE TABLE x AS SELECT 1",
        # Data-modifying CTE: the statement root is a SELECT.
        "WITH d AS (DELETE FROM t RETURNING *) SELECT * FROM d",
        "WITH u AS (UPDATE t SET x = 1 RETURNING *) SELECT * FROM u",
        # SELECT that still writes or locks.
        "SELECT * INTO new_t FROM t",
        "SELECT * FROM t FOR UPDATE",
        # Stacked statements.
        "SELECT 1; DROP TABLE t",
        "SELECT 1; UPDATE t SET x = 1",
        # DDL / privileges / session state.
        "DROP TABLE t",
        "TRUNCATE TABLE t",
        "ALTER TABLE t ADD COLUMN x int",
        "GRANT ALL ON t TO someone",
        "COPY t TO '/tmp/x'",
        "SET ROLE admin",
        "CALL do_thing()",
        "DO $$ BEGIN PERFORM 1; END $$",
        "VACUUM",
        "REFRESH MATERIALIZED VIEW mv",
        # EXPLAIN ANALYZE actually executes the inner statement.
        "EXPLAIN ANALYZE UPDATE t SET x = 1",
        # Unparseable input cannot be verified.
        "SELECT FROM WHERE ((",
        "",
        "   ",
    ],
)
def test_rejects_non_read_only_queries(sql):
    is_read_only, reason = validate_read_only_sql(sql)
    assert not is_read_only
    assert reason


def test_rejection_reason_names_the_operation():
    _, reason = validate_read_only_sql("UPDATE t SET x = 1 WHERE id IN (SELECT id FROM s)")
    assert "UPDATE" in reason


def test_rejection_reason_reports_statement_count():
    _, reason = validate_read_only_sql("SELECT 1; SELECT 2")
    assert "2" in reason
