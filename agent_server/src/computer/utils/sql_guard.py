from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

SQL_DIALECT = "postgres"

# Rejected anywhere in the tree, not just at the root: a data-modifying CTE such as
# `WITH d AS (DELETE FROM t RETURNING *) SELECT * FROM d` parses with a SELECT root.
_FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Grant,
    exp.Copy,
    exp.Into,  # SELECT ... INTO new_table materialises a table
    exp.Lock,  # SELECT ... FOR UPDATE / FOR SHARE takes row locks
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Set,
    exp.Use,
    # Fallback node for syntax sqlglot cannot model (CALL, DO, VACUUM, EXPLAIN ANALYZE,
    # REFRESH MATERIALIZED VIEW, ...). Unparsed means unverifiable, so it is refused.
    exp.Command,
)


def _describe(node: exp.Expression) -> str:
    if isinstance(node, exp.Command) and node.this:
        return str(node.this).upper()
    return type(node).__name__.upper()


def validate_read_only_sql(sql: str) -> tuple[bool, str | None]:
    """Check that ``sql`` is a single read-only statement.

    Returns:
        ``(True, None)`` when the statement is safe to execute, otherwise
        ``(False, reason)`` with a reason suitable for surfacing to the model.
    """
    if not sql or not sql.strip():
        return False, "Empty SQL statement: nothing to execute."

    try:
        statements = [stmt for stmt in sqlglot.parse(sql, dialect=SQL_DIALECT) if stmt is not None]
    except ParseError as exc:
        return False, f"SQL could not be parsed, so it cannot be verified as read-only: {exc}"

    if not statements:
        return False, "Empty SQL statement: nothing to execute."

    if len(statements) > 1:
        return False, (
            f"Only one SQL statement is allowed per call, but {len(statements)} were provided. "
            "Remove the extra statements and the semicolons separating them."
        )

    tree = statements[0]

    for node in tree.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            return False, (
                f"Only read-only SELECT queries are allowed. Forbidden operation found: "
                f"{_describe(node)}."
            )

    if not isinstance(tree, exp.Query):
        return False, (
            f"Only read-only SELECT queries are allowed, but the statement is "
            f"{_describe(tree)}."
        )

    return True, None
