from __future__ import annotations

from sqlalchemy import ForeignKey, PrimaryKeyConstraint, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared_server_libs.db_access.orm import DbBase, TimestampMixin


class CatalogTable(DbBase, TimestampMixin):
    __tablename__ = "catalog_table"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", insert_default="")
    primary_key_columns: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, insert_default=list
    )
    important_columns: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    notes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, insert_default=list
    )

    columns: Mapped[list[CatalogColumn]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
    )
    outgoing_relations: Mapped[list[CatalogRelation]] = relationship(
        back_populates="source_table_ref",
        foreign_keys="CatalogRelation.source_table",
        cascade="all, delete-orphan",
    )
    incoming_relations: Mapped[list[CatalogRelation]] = relationship(
        back_populates="target_table_ref",
        foreign_keys="CatalogRelation.target_table",
    )


class CatalogColumn(DbBase, TimestampMixin):
    __tablename__ = "catalog_column"
    __table_args__ = (PrimaryKeyConstraint("table_name", "column_name"),)

    table_name: Mapped[str] = mapped_column(
        ForeignKey("catalog_table.name", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_name: Mapped[str] = mapped_column(String, nullable=False)
    data_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", insert_default="")
    example_use_cases: Mapped[str] = mapped_column(Text, nullable=False, default="", insert_default="")

    table: Mapped[CatalogTable] = relationship(back_populates="columns")


class CatalogRelation(DbBase, TimestampMixin):
    __tablename__ = "catalog_relation"
    __table_args__ = (
        PrimaryKeyConstraint(
            "source_table",
            "source_column",
            "target_table",
            "target_column",
            "relationship_type",
        ),
    )

    source_table: Mapped[str] = mapped_column(
        ForeignKey("catalog_table.name", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_column: Mapped[str] = mapped_column(String, nullable=False)
    target_table: Mapped[str] = mapped_column(
        ForeignKey("catalog_table.name", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_column: Mapped[str] = mapped_column(String, nullable=False)
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)
    semantic_meaning: Mapped[str] = mapped_column(Text, nullable=False, default="", insert_default="")
    related_tables: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, insert_default=list
    )
    columns_attached: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, insert_default=list
    )
    notes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, insert_default=list
    )

    source_table_ref: Mapped[CatalogTable] = relationship(
        back_populates="outgoing_relations",
        foreign_keys=[source_table],
    )
    target_table_ref: Mapped[CatalogTable] = relationship(
        back_populates="incoming_relations",
        foreign_keys=[target_table],
    )
