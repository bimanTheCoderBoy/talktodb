from sqlalchemy import Column, Integer, Float, Text, Boolean, Index
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography

from pipeline_app.db.models._base import Base, SecurityColumnsMixin, ImportedAtMixin


class Location(SecurityColumnsMixin, ImportedAtMixin, Base):
    __tablename__ = "location"
    __table_args__ = (
        Index("ix_location_imported_at", "imported_at"),
    )

    iid = Column(Text, primary_key=True, comment="EDS business identifier")
    eid = Column(Integer, unique=True, comment="EDS numeric entity ID")

    # Location-specific data
    address1 = Column(Text)
    town = Column(Text)
    postcode = Column(Text)
    propertycode = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    geom = Column(Geography(geometry_type="POINT", srid=4326), index=True)
    state = Column(Text)
    type = Column(Text)
    groundhgt = Column(Float)
    searchrad = Column(Float)
    mastspace = Column(Float)
    mttr = Column(Float)
    buildingheight = Column(Integer)
    mounting = Column(Text)
    epsg = Column(Integer)
    allowedoperations = Column(Text)
    bvid = Column(Text)
    tower_iid = Column(Text)
    tower_eid = Column(Integer)
    carriedtraffictotal_pscarriedtraffictotal_autoaggregated = Column(Boolean)
    carriedtraffictotal_cscarriedtraffictotal_autoaggregated = Column(Boolean)

    # Relationships
    mu_ltes = relationship("MuLTE", back_populates="location", cascade="all, delete-orphan")
    mu_nrs = relationship("MuNR", back_populates="location", cascade="all, delete-orphan")
    cell_ltes = relationship("CellLTE", back_populates="location", cascade="all, delete-orphan",
                             foreign_keys="CellLTE.location_iid")
    cell_nrs = relationship("CellNR", back_populates="location", cascade="all, delete-orphan",
                            foreign_keys="CellNR.location_iid")
    logical_antennas = relationship("CellLogicalAntenna", back_populates="location", cascade="all, delete-orphan")
    physical_antennas = relationship("CellPhysicalAntenna", back_populates="location", cascade="all, delete-orphan")