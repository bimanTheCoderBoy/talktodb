"""Catalog ORM metadata smoke tests."""

from sqlalchemy import inspect

from api.db.models import Base
import database_context_retrieval.domain.entity  # noqa: F401


def test_catalog_tables_registered_on_shared_metadata():
    names = set(Base.metadata.tables.keys())
    assert "catalog_table" in names
    assert "catalog_column" in names
    assert "catalog_relation" in names


def test_catalog_table_columns():
    cols = {c.name for c in inspect(Base.metadata.tables["catalog_table"]).columns}
    assert cols >= {
        "id",
        "name",
        "description",
        "primary_key_columns",
        "important_columns",
        "notes",
        "created_at",
        "updated_at",
    }


def test_catalog_column_columns():
    cols = {c.name for c in inspect(Base.metadata.tables["catalog_column"]).columns}
    assert cols >= {
        "id",
        "table_name",
        "column_name",
        "data_type",
        "description",
        "example_use_cases",
        "created_at",
        "updated_at",
    }


def test_catalog_relation_columns():
    cols = {c.name for c in inspect(Base.metadata.tables["catalog_relation"]).columns}
    assert cols >= {
        "id",
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
