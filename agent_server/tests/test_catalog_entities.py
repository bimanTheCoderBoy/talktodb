"""Catalog ORM metadata smoke tests."""

from sqlalchemy import inspect

import database_context_retrieval.domain.entity  # noqa: F401
from shared_server_libs.infra.ranora_config_orm import RanoraConfigBase


def test_catalog_tables_registered_on_ranora_config_metadata():
    names = set(RanoraConfigBase.metadata.tables.keys())
    assert "catalog_table" in names
    assert "catalog_column" in names
    assert "catalog_relation" in names


def test_catalog_table_columns():
    cols = {c.name for c in inspect(RanoraConfigBase.metadata.tables["catalog_table"]).columns}
    assert cols >= {
        "name",
        "description",
        "primary_key_columns",
        "important_columns",
        "notes",
        "created_at",
        "updated_at",
    }
    assert "id" not in cols


def test_catalog_column_columns():
    cols = {c.name for c in inspect(RanoraConfigBase.metadata.tables["catalog_column"]).columns}
    assert cols >= {
        "table_name",
        "column_name",
        "data_type",
        "description",
        "example_use_cases",
        "created_at",
        "updated_at",
    }
    assert "id" not in cols


def test_catalog_relation_columns():
    cols = {c.name for c in inspect(RanoraConfigBase.metadata.tables["catalog_relation"]).columns}
    assert cols >= {
        "source_table",
        "source_column",
        "target_table",
        "target_column",
        "relationship_type",
        "semantic_meaning",
        "related_tables",
        "columns_attached",
        "notes",
        "created_at",
        "updated_at",
    }
    assert "id" not in cols
