from __future__ import annotations

import json
from typing import Any, Callable

from pydantic import BaseModel

TOOL_GET_DATABASE_TABLE = "get_database_table"
TOOL_GET_DATABASE_COLUMN = "get_database_column"
TOOL_GET_DATABASE_RELATION = "get_database_relation"
TOOL_SEARCH_DATABASE_CONTEXT = "search_database_context"
TOOL_RUN_DB_QUERY = "run_db_query"

MAX_TOOL_RESULT_SIZE_CHAR = 10000
TRUNCATION_MARKER = "...TRUNCATED_DUE_TO_HUGE_SIZE"

_TABLE_COLUMN_FIELDS = ["column_name", "data_type", "description", "example_use_cases"]
_COLUMN_INFO_FIELDS = [
    "table_name",
    "column_name",
    "data_type",
    "description",
    "example_use_cases",
]
_RELATION_FIELDS = [
    "source_table",
    "source_column",
    "target_table",
    "target_column",
    "relationship_type",
    "semantic_meaning",
    "related_tables",
    "columns_attached",
    "notes",
]
_HIT_FIELDS = [
    "column_id",
    "table_name",
    "column_name",
    "data_type",
    "description",
    "example_use_cases",
    "value",
]


def _serialize_passthrough(result: BaseModel | dict[str, Any] | str) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, BaseModel):
        return result.model_dump_json()
    return json.dumps(result, default=str)


def _coerce_dict(result: BaseModel | dict[str, Any] | str) -> dict[str, Any] | None:
    if isinstance(result, dict):
        return result
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


def _object_list_to_columnar(
    items: list[dict[str, Any]],
    fields: list[str],
) -> tuple[list[str], list[list[Any]]]:
    rows: list[list[Any]] = []
    for item in items:
        rows.append([item.get(field) for field in fields])
    return fields, rows


def _compact_table_lookup_payload(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    columns = out.pop("columns", None)
    if columns:
        column_fields, column_rows = _object_list_to_columnar(columns, _TABLE_COLUMN_FIELDS)
        out["column_fields"] = column_fields
        out["column_rows"] = column_rows
    else:
        out["column_fields"] = list(_TABLE_COLUMN_FIELDS)
        out["column_rows"] = []
    return out


def _compact_llm_get_database_table(data: dict[str, Any]) -> dict[str, Any]:
    return _compact_table_lookup_payload(data)


def _compact_llm_get_database_column(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    column = out.pop("column", None)
    if column:
        column_fields, column_rows = _object_list_to_columnar([column], _COLUMN_INFO_FIELDS)
        out["column_fields"] = column_fields
        out["column_rows"] = column_rows[0] if column_rows else []
    return out


def _compact_llm_get_database_relation(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    relations = out.pop("relations", None)
    if relations:
        relation_fields, relation_rows = _object_list_to_columnar(relations, _RELATION_FIELDS)
        out["relation_fields"] = relation_fields
        out["relation_rows"] = relation_rows
    else:
        out["relation_fields"] = list(_RELATION_FIELDS)
        out["relation_rows"] = []
    return out


def _compact_llm_search_database_context(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "success": data.get("success", True),
        "error": data.get("error"),
        "query": data.get("query", ""),
    }
    hits = data.get("column_hits") or []
    if hits:
        hit_fields, hit_rows = _object_list_to_columnar(hits, _HIT_FIELDS)
        out["hit_fields"] = hit_fields
        out["hit_rows"] = hit_rows
    else:
        out["hit_fields"] = list(_HIT_FIELDS)
        out["hit_rows"] = []

    hit_index_by_id: dict[str, int] = {}
    for idx, hit in enumerate(hits):
        hit_id = hit.get("column_id")
        if hit_id is not None:
            hit_index_by_id[str(hit_id)] = idx

    compact_tables: list[dict[str, Any]] = []
    for table_ctx in data.get("tables") or []:
        matched = table_ctx.get("matched_columns") or []
        indexes: list[int] = []
        for col in matched:
            col_id = col.get("column_id")
            if col_id is not None and str(col_id) in hit_index_by_id:
                indexes.append(hit_index_by_id[str(col_id)])
            else:
                for idx, hit in enumerate(hits):
                    if (
                        hit.get("table_name") == col.get("table_name")
                        and hit.get("column_name") == col.get("column_name")
                        and idx not in indexes
                    ):
                        indexes.append(idx)
                        break
        lookup = table_ctx.get("lookup")
        compact_tables.append(
            {
                "table_name": table_ctx.get("table_name"),
                "retrieval_score": table_ctx.get("retrieval_score"),
                "matched_hit_indexes": indexes,
                "lookup": _compact_table_lookup_payload(lookup) if lookup else None,
            }
        )
    out["tables"] = compact_tables
    return out


def _compact_llm_run_db_query(
    data: dict[str, Any],
    *,
    tool_args: dict[str, Any] | None,
) -> str:
    body = json.dumps(data, separators=(",", ":"), default=str)
    parts = [body]
    args = tool_args or {}
    query = args.get("query")
    if query:
        parts.append(f"\n\n**SQL executed:**\n```sql\n{query}\n```")
    params = args.get("params")
    if params:
        parts.append(f"\n**Parameters:** `{json.dumps(params, default=str)}`")
    return "".join(parts)


def _format_ui_json_block(data: dict[str, Any], *, tool_args: dict[str, Any] | None) -> str:
    return "```json\n" + json.dumps(data, indent=2, default=str) + "\n```"


def _escape_md_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("|", "\\|").replace("\n", " ")
    return text


def _format_ui_run_db_query(data: dict[str, Any], *, tool_args: dict[str, Any] | None) -> str:
    args = tool_args or {}
    query = args.get("query")
    params = args.get("params")
    sections: list[str] = []

    if query:
        sections.append(f"**SQL executed:**\n```sql\n{query}\n```")
    if params:
        sections.append(f"**Parameters:** `{json.dumps(params, default=str)}`")

    if not data.get("success", False):
        error = data.get("error") or "Unknown error"
        sections.append(f"**Error executing query**\n\n{error}")
        return "\n\n".join(sections)

    columns = data.get("columns") or []
    rows = data.get("rows") or []
    row_count = data.get("row_count", len(rows))

    if row_count == 0 or not rows:
        sections.append("**Query result**\n\nNo data found.")
        return "\n\n".join(sections)

    if not columns:
        sections.append("**Query result**\n\nNo columns returned.")
        return "\n\n".join(sections)

    header = "| " + " | ".join(_escape_md_cell(c) for c in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body_rows = []
    for row in rows:
        cells = [_escape_md_cell(cell) for cell in row]
        body_rows.append("| " + " | ".join(cells) + " |")
    sections.append(
        "**Query result**\n\n"
        + header
        + "\n"
        + separator
        + "\n"
        + "\n".join(body_rows)
        + f"\n\n*{row_count} row(s)*"
    )
    return "\n\n".join(sections)


_LLM_FORMATTERS: dict[str, Callable[..., str | dict[str, Any]]] = {
    TOOL_GET_DATABASE_TABLE: _compact_llm_get_database_table,
    TOOL_GET_DATABASE_COLUMN: _compact_llm_get_database_column,
    TOOL_GET_DATABASE_RELATION: _compact_llm_get_database_relation,
    TOOL_SEARCH_DATABASE_CONTEXT: _compact_llm_search_database_context,
}

_UI_FORMATTERS: dict[str, Callable[..., str]] = {
    TOOL_GET_DATABASE_TABLE: _format_ui_json_block,
    TOOL_GET_DATABASE_COLUMN: _format_ui_json_block,
    TOOL_GET_DATABASE_RELATION: _format_ui_json_block,
    TOOL_SEARCH_DATABASE_CONTEXT: _format_ui_json_block,
    TOOL_RUN_DB_QUERY: _format_ui_run_db_query,
}


def format_llm_tool_result(
    tool_name: str,
    result: BaseModel | dict[str, Any] | str,
    *,
    tool_args: dict[str, Any] | None = None,
) -> str:
    formatter = _LLM_FORMATTERS.get(tool_name)
    if formatter is None and tool_name == TOOL_RUN_DB_QUERY:
        data = _coerce_dict(result)
        if data is None:
            return _serialize_passthrough(result)
        return _compact_llm_run_db_query(data, tool_args=tool_args)

    if formatter is None:
        return _serialize_passthrough(result)

    data = _coerce_dict(result)
    if data is None:
        return _serialize_passthrough(result)

    compact = formatter(data)
    if isinstance(compact, str):
        return compact
    return json.dumps(compact, separators=(",", ":"), default=str)


def truncate_tool_result_for_llm(
    content: Any,
    max_chars: int = MAX_TOOL_RESULT_SIZE_CHAR,
) -> Any:
    if not isinstance(content, str) or len(content) <= max_chars:
        return content
    return content[:max_chars] + TRUNCATION_MARKER


def format_ui_tool_result(
    tool_name: str,
    result: BaseModel | dict[str, Any] | str,
    *,
    tool_args: dict[str, Any] | None = None,
) -> str:
    formatter = _UI_FORMATTERS.get(tool_name)
    if formatter is None:
        return _serialize_passthrough(result)

    data = _coerce_dict(result)
    if data is None:
        return _serialize_passthrough(result)

    return formatter(data, tool_args=tool_args)

