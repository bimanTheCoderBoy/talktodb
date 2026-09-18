from pipeline_app.db.models._base import Base, SecurityColumnsMixin, ImportedAtMixin
from pipeline_app.db.models._mixins import BaseEntityColumns, MuBaseColumns, CarriedTrafficColumns, LocationRefColumns
from sqlalchemy import Column, Text, Integer, Float, Boolean, Index
from sqlalchemy.orm import relationship


class MuLTE(BaseEntityColumns, MuBaseColumns, CarriedTrafficColumns, LocationRefColumns,
            SecurityColumnsMixin, ImportedAtMixin, Base):
    __tablename__ = "mu_lte"
    __table_args__ = (Index("ix_mu_lte_imported_at", "imported_at"),)

    # LTE-specific columns only
    lte_signallingoverhead = Column(Float)
    lte_capacity = Column(Float)
    lte_enabled = Column(Boolean)
    lte_carriers_iid = Column(Text)
    lte_carriers_eid = Column(Float)
    lte_carriedtraffictotal_pscarriedtraffictotal_protected = Column(Boolean)
    lte_carriedtraffictotal_pscarriedtraffictotal_throughputdl = Column(Float)
    lte_carriedtraffictotal_pscarriedtraffictotal_throughputul = Column(Float)
    lte_carriedtraffictotal_pscarriedtraffictotal_numberofterminals = Column(Float)
    lte_carriedtraffictotal_pscarriedtraffictotal_autoaggregated = Column(Boolean)

    # Relationships
    location = relationship("Location", back_populates="mu_ltes")
    cells = relationship("CellLTE", back_populates="mu", cascade="all, delete-orphan")

class MuNR(BaseEntityColumns, MuBaseColumns, CarriedTrafficColumns, LocationRefColumns, SecurityColumnsMixin, ImportedAtMixin, Base):
    __tablename__ = "mu_nr"
    __table_args__ = (Index("ix_mu_nr_imported_at", "imported_at"),)

    # NR-specific columns only
    nrt_signallingoverhead = Column(Float)
    nrt_capacity = Column(Float)
    nrt_enabled = Column(Boolean)
    nrt_carriers_iid = Column(Text)
    nrt_carriers_eid = Column(Float)
    nrt_carriedtraffictotal_pscarriedtraffictotal_protected = Column(Boolean)
    nrt_carriedtraffictotal_pscarriedtraffictotal_throughputdl = Column(Float)
    nrt_carriedtraffictotal_pscarriedtraffictotal_throughputul = Column(Float)
    nrt_carriedtraffictotal_pscarriedtraffictotal_numberofterminals = Column(Float)
    nrt_carriedtraffictotal_pscarriedtraffictotal_autoaggregated = Column(Boolean)

    # Relationships
    location = relationship("Location", back_populates="mu_nrs")
    cells = relationship("CellNR", back_populates="mu", cascade="all, delete-orphan")