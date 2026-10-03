"""SQLAlchemy models for the global schema catalog in ranora_config."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from api.db.models import Base


class CatalogTable(Base):
    __tablename__ = "catalog_table"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=False, default="")
    primary_key_columns = Column(ARRAY(String), nullable=False, default=list)
    important_columns = Column(ARRAY(String), nullable=True)
    notes = Column(ARRAY(Text), nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    columns = relationship(
        "CatalogColumn",
        back_populates="table",
        foreign_keys="CatalogColumn.table_name",
    )

    def __repr__(self) -> str:
        return f"<CatalogTable(id={self.id!r}, name={self.name!r})>"


class CatalogColumn(Base):
    __tablename__ = "catalog_column"

    id = Column(String, primary_key=True)
    table_name = Column(
        String,
        ForeignKey("catalog_table.name", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_name = Column(String, nullable=False)
    data_type = Column(String, nullable=False)
    description = Column(Text, nullable=False, default="")
    example_use_cases = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    table = relationship(
        "CatalogTable",
        back_populates="columns",
        foreign_keys=[table_name],
    )

    def __repr__(self) -> str:
        return f"<CatalogColumn(id={self.id!r})>"


class CatalogRelation(Base):
    __tablename__ = "catalog_relation"

    id = Column(String, primary_key=True)
    source_table = Column(
        String,
        ForeignKey("catalog_table.name", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_column = Column(String, nullable=False)
    target_table = Column(
        String,
        ForeignKey("catalog_table.name", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_column = Column(String, nullable=False)
    relationship_type = Column(String, nullable=False)
    semantic_meaning = Column(Text, nullable=False, default="")
    related_tables = Column(ARRAY(String), nullable=False, default=list)
    columns_attached = Column(ARRAY(String), nullable=False, default=list)
    notes = Column(ARRAY(Text), nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:
        return f"<CatalogRelation(id={self.id!r})>"
