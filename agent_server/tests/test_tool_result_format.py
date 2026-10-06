"""Tests for LLM compact and UI formatters on database tool results."""

import json

import pytest

from computer.utils.tool_result_format import (
    MAX_TOOL_RESULT_SIZE_CHAR,
    TOOL_GET_DATABASE_COLUMN,
    TOOL_GET_DATABASE_RELATION,
    TOOL_GET_DATABASE_TABLE,
    TOOL_RUN_DB_QUERY,
    TOOL_SEARCH_DATABASE_CONTEXT,
    TRUNCATION_MARKER,
    format_llm_tool_result,
    format_ui_tool_result,
    truncate_tool_result_for_llm,
)
from database_context_retrieval.domain.schema.catalog_column import (
    CatalogColumnInfo,
    CatalogColumnLookupResult,
)
from database_context_retrieval.domain.schema.catalog_context_search import (
    CatalogContextSearchResult,
    CatalogRetrievalColumnHit,
    CatalogTableEnrichedContext,
)
from database_context_retrieval.domain.schema.catalog_relation import (
    CatalogRelationInfo,
    CatalogRelationLookupResult,
)
from database_context_retrieval.domain.schema.catalog_table import (
    CatalogColumnSummary,
    CatalogTableInfo,
    CatalogTableLookupResult,
)
from shared_server_libs.agent_db_access.domain.schema.query_result import QueryResult


def _expand_table_lookup(compact: dict) -> dict:
    out = dict(compact)
    fields = out.pop("column_fields", [])
    rows = out.pop("column_rows", [])
    table_name = out.get("queried_name") or (out.get("table") or {}).get("name")
    columns = []
    for row in rows:
        item = dict(zip(fields, row, strict=False))
        if table_name and "table_name" not in item:
            item["table_name"] = table_name
        columns.append(item)
    out["columns"] = columns
    return out


def _expand_column_lookup(compact: dict) -> dict:
    out = dict(compact)
    fields = out.pop("column_fields", None)
    row = out.pop("column_rows", None)
    if fields and row is not None:
        out["column"] = dict(zip(fields, row, strict=False))
    return out


def _expand_relation_lookup(compact: dict) -> dict:
    out = dict(compact)
    fields = out.pop("relation_fields", [])
    rows = out.pop("relation_rows", [])
    out["relations"] = [dict(zip(fields, row, strict=False)) for row in rows]
    return out


def _expand_search(compact: dict) -> dict:
    out = dict(compact)
    hit_fields = out.pop("hit_fields", [])
    hit_rows = out.pop("hit_rows", [])
    hits = [dict(zip(hit_fields, row, strict=False)) for row in hit_rows]
    out["column_hits"] = hits

    expanded_tables = []
    for table_ctx in out.get("tables") or []:
        ctx = dict(table_ctx)
        indexes = ctx.pop("matched_hit_indexes", [])
        ctx["matched_columns"] = [hits[i] for i in indexes if i < len(hits)]
        lookup = ctx.get("lookup")
        if lookup:
            ctx["lookup"] = _expand_table_lookup(lookup)
        expanded_tables.append(ctx)
    out["tables"] = expanded_tables
    return out


def test_passthrough_unknown_tool():
    raw = '{"hello": "world"}'
    assert format_llm_tool_result("some_other_tool", raw) == raw
    assert format_ui_tool_result("some_other_tool", raw) == raw


def test_compact_table_lookup_lossless():
    original = CatalogTableLookupResult(
        found=True,
        queried_name="cell_lte",
        table=CatalogTableInfo(
            name="cell_lte",
            description="LTE cells",
            primary_key_columns=["id"],
            important_columns=["azimuth"],
            notes=["note"],
        ),
        related_table_names=["site"],
        columns=[
            CatalogColumnSummary(
                table_name="cell_lte",
                column_name="azimuth",
                data_type="float",
                description="bearing",
                example_use_cases="map",
            )
        ],
        total_column_count=1,
    )
    raw = original.model_dump_json()
    llm = format_llm_tool_result(TOOL_GET_DATABASE_TABLE, raw)
    compact = json.loads(llm)
    expanded = _expand_table_lookup(compact)
    assert expanded["columns"] == [c.model_dump() for c in original.columns]
    assert compact["table"] == original.table.model_dump()
    assert "created_at" not in json.dumps(compact)


def test_compact_column_lookup_lossless():
    original = CatalogColumnLookupResult(
        found=True,
        queried_table_name="cell_lte",
        queried_column_name="azimuth",
        column=CatalogColumnInfo(
            table_name="cell_lte",
            column_name="azimuth",
            data_type="float",
            description="bearing",
            example_use_cases="map",
        ),
    )
    raw = original.model_dump_json()
    compact = json.loads(format_llm_tool_result(TOOL_GET_DATABASE_COLUMN, raw))
    expanded = _expand_column_lookup(compact)
    assert expanded["column"] == original.column.model_dump()


def test_compact_relation_lookup_lossless():
    original = CatalogRelationLookupResult(
        found=True,
        queried_table_a="a",
        queried_table_b="b",
        relations=[
            CatalogRelationInfo(
                source_table="a",
                source_column="a_id",
                target_table="b",
                target_column="b_id",
                relationship_type="fk",
                semantic_meaning="join",
                related_tables=["c"],
                columns_attached=["x"],
                notes=["n"],
            )
        ],
    )
    raw = original.model_dump_json()
    compact = json.loads(format_llm_tool_result(TOOL_GET_DATABASE_RELATION, raw))
    expanded = _expand_relation_lookup(compact)
    assert expanded["relations"] == [r.model_dump() for r in original.relations]


def test_compact_search_matched_indexes_recover_hits():
    hit_a = CatalogRetrievalColumnHit(
        column_id="1",
        table_name="t1",
        column_name="c1",
        data_type="text",
        description="d1",
        example_use_cases="e1",
        value=0.9,
    )
    hit_b = CatalogRetrievalColumnHit(
        column_id="2",
        table_name="t2",
        column_name="c2",
        data_type="text",
        description="d2",
        example_use_cases="e2",
        value=0.5,
    )
    original = CatalogContextSearchResult(
        query="q",
        column_hits=[hit_a, hit_b],
        tables=[
            CatalogTableEnrichedContext(
                table_name="t1",
                retrieval_score=0.9,
                matched_columns=[hit_a],
                lookup=CatalogTableLookupResult(found=True, queried_name="t1"),
            )
        ],
    )
    raw = original.model_dump_json()
    compact = json.loads(format_llm_tool_result(TOOL_SEARCH_DATABASE_CONTEXT, raw))
    expanded = _expand_search(compact)
    assert expanded["column_hits"] == [h.model_dump() for h in original.column_hits]
    assert expanded["tables"][0]["matched_columns"] == [hit_a.model_dump()]


def test_run_db_query_llm_includes_sql():
    result = QueryResult(
        success=True,
        columns=["name", "roll"],
        rows=[["Biman", 45], ["Biman2", 41]],
        row_count=2,
    )
    raw = result.model_dump_json()
    llm = format_llm_tool_result(
        TOOL_RUN_DB_QUERY,
        raw,
        tool_args={"query": "SELECT name, roll FROM students", "params": {"limit": 10}},
    )
    assert "SELECT name, roll FROM students" in llm
    assert '"limit": 10' in llm or "limit" in llm
    assert "Biman" in llm


def test_run_db_query_ui_markdown_table():
    result = QueryResult(
        success=True,
        columns=["name", "roll"],
        rows=[["Biman", 45], ["Biman2", 41]],
        row_count=2,
    )
    ui = format_ui_tool_result(
        TOOL_RUN_DB_QUERY,
        result.model_dump_json(),
        tool_args={"query": "SELECT 1"},
    )
    assert "| name | roll |" in ui
    assert "| Biman | 45 |" in ui
    assert "```sql" in ui


@pytest.mark.parametrize(
    "tool_name",
    [
        TOOL_GET_DATABASE_TABLE,
        TOOL_GET_DATABASE_COLUMN,
        TOOL_GET_DATABASE_RELATION,
        TOOL_SEARCH_DATABASE_CONTEXT,
    ],
)
def test_catalog_ui_results_are_json_fenced(tool_name):
    raw = json.dumps({"found": True, "queried_name": "cell_lte"})
    ui = format_ui_tool_result(tool_name, raw)
    assert ui.startswith("```json\n")
    assert ui.endswith("\n```")
    assert json.loads(ui[len("```json\n") : -len("\n```")]) == json.loads(raw)


def test_truncate_leaves_small_results_untouched():
    content = "x" * MAX_TOOL_RESULT_SIZE_CHAR
    assert truncate_tool_result_for_llm(content) == content


def test_truncate_cuts_oversized_results():
    content = "x" * (MAX_TOOL_RESULT_SIZE_CHAR + 500)
    truncated = truncate_tool_result_for_llm(content)
    assert truncated == "x" * MAX_TOOL_RESULT_SIZE_CHAR + TRUNCATION_MARKER


def test_truncate_passes_through_non_string_content():
    content = [{"type": "text", "text": "hi"}]
    assert truncate_tool_result_for_llm(content) is content


def test_failure_payload_preserved():
    original = CatalogTableLookupResult.failure("x", "boom")
    raw = original.model_dump_json()
    compact = json.loads(format_llm_tool_result(TOOL_GET_DATABASE_TABLE, raw))
    assert compact["success"] is False
    assert compact["error"] == "boom"
