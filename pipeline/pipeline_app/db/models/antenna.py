from sqlalchemy import Column, Text, Integer, Float, Boolean, Index
from sqlalchemy.orm import relationship

from pipeline_app.db.models._base import Base, ImportedAtMixin
from pipeline_app.db.models._mixins import LocationRefColumns, CellContextColumns


class CellPhysicalAntenna(LocationRefColumns, CellContextColumns, ImportedAtMixin, Base):
    __tablename__ = "cell_physical_antenna"
    __table_args__ = (
        Index("ix_cpa_imported_at", "imported_at"),
        Index("ix_cpa_cell_iid", "cell_iid"),
        Index("ix_cpa_antennadevice_iid", "antennadevice_iid"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    spatialdiversity = Column(Boolean)
    azimuth = Column(Float)
    tilt = Column(Float)
    twist = Column(Float)
    height = Column(Float)
    heightpredoffset = Column(Float)
    heightpred = Column(Float)
    antennatype_ro = Column(Text)
    antennadevice_iid = Column(Text)
    antennadevice_eid = Column(Integer)
    masterpattern1_iid = Column(Text)
    masterpattern1_eid = Column(Float)
    masterpattern2_iid = Column(Text)
    masterpattern2_eid = Column(Float)
    masterpattern3_iid = Column(Text)
    masterpattern3_eid = Column(Float)
    masterpattern4_iid = Column(Text)
    masterpattern4_eid = Column(Float)
    masterpattern5_iid = Column(Text)
    masterpattern5_eid = Column(Float)
    masterpattern6_iid = Column(Text)
    masterpattern6_eid = Column(Float)
    masterpattern7_iid = Column(Text)
    masterpattern7_eid = Column(Float)
    masterpattern8_iid = Column(Text)
    masterpattern8_eid = Column(Float)
    abslocation_longitude = Column(Float)
    abslocation_latitude = Column(Float)
    abslocation_epsg = Column(Integer)
    abslocation_dtmovr = Column(Float)
    abslocation_dtmovrprop = Column(Float)
    location_x = Column(Float)
    location_y = Column(Float)
    location_z = Column(Float)
    location_relative = Column(Text)
    location_epsg = Column(Integer)
    constraints_antennadevicefixed = Column(Boolean)
    constraints_azimuthfixed = Column(Boolean)
    constraints_heightfixed = Column(Boolean)
    constraints_mechanicaltiltfixed = Column(Boolean)
    constraints_useforbiddenazimuth = Column(Boolean)
    constraints_forbiddenazimuthfrom = Column(Integer)
    constraints_forbiddenazimuthto = Column(Integer)
    constraints_minmechanicaltilt_constrained = Column(Boolean)
    constraints_minmechanicaltilt_value = Column(Integer)
    constraints_maxmechanicaltilt_constrained = Column(Boolean)
    constraints_maxmechanicaltilt_value = Column(Integer)
    constraints_mechanicaltiltstep_constrained = Column(Boolean)
    constraints_mechanicaltiltstep_value = Column(Integer)
    availsyncretgrps = Column(Text)

    # Relationships
    location = relationship("Location", back_populates="physical_antennas")


class CellLogicalAntenna(LocationRefColumns, CellContextColumns, ImportedAtMixin, Base):
    __tablename__ = "cell_logical_antenna"
    __table_args__ = (
        Index("ix_cla_imported_at", "imported_at"),
        Index("ix_cla_cell_iid", "cell_iid"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    eid = Column(Integer, name="logical_eid")
    repeaterantenna = Column(Boolean)
    correctionfactor = Column(Float)
    ulcorrectionfactor = Column(Float)
    syncretgroupindex = Column(Text)
    usepredinnerouter = Column(Boolean)
    antennatype_ro = Column(Text)
    singlebeamenabled = Column(Boolean)
    phyindex = Column(Integer)
    primarymodel_radiuskm = Column(Float)
    primarymodel_resolutionmetres = Column(Float)
    primarymodel_modeltype_iid = Column(Text)
    primarymodel_modeltype_eid = Column(Integer)
    secondarymodel_radiuskm = Column(Float)
    secondarymodel_resolutionmetres = Column(Float)
    secondarymodel_modeltype_iid = Column(Text)
    secondarymodel_modeltype_eid = Column(Integer)
    constraints_antennapatternfixed = Column(Boolean)
    constraints_totalminimumdowntilt_constrained = Column(Boolean)
    constraints_totalminimumdowntilt_value = Column(Integer)
    constraints_totalmaximumdowntilt_constrained = Column(Boolean)
    constraints_totalmaximumdowntilt_value = Column(Integer)
    constraints_electricalminimumdowntilt_constrained = Column(Boolean)
    constraints_electricalminimumdowntilt_value = Column(Integer)
    constraints_electricalmaximumdowntilt_constrained = Column(Boolean)
    constraints_electricalmaximumdowntilt_value = Column(Integer)
    constraints_electricaldowntiltstep_constrained = Column(Boolean)
    constraints_electricaldowntiltstep_value = Column(Integer)
    beamset_iid = Column(Text)
    beamset_eid = Column(Float)
    passive_patternfrequency_ro = Column(Float)
    passive_inheritmasterpattern = Column(Float)
    passive_electricaldowntilt_ro = Column(Float)
    passive_totaldowntilt_ro = Column(Float)
    passive_antennapatternangle_ro = Column(Float)
    passive_antennapatterntype_iid = Column(Text)
    passive_antennapatterntype_eid = Column(Float)
    beamswitching_patternfrequency = Column(Float)
    beamswitching_dbpatternref = Column(Text)
    beamswitching_dbpatternhash = Column(Float)
    beamswitching_sbactrlpatterns_ro_patternindex = Column(Float)
    beamswitching_sbactrlpatterns_ro_controlindex = Column(Float)
    beamswitching_sbactrlpatterns_ro_patterns_name = Column(Text)
    beamswitching_sbactrlpatterns_ro_patterns_eid = Column(Float)
    beamswitching_sbactrlpatterns_ro_patterns_gain = Column(Float)
    beamswitching_sbactrlpatterns_ro_patterns_electricaltilt = Column(Float)
    beamswitching_sbactrlpatterns_ro_patterns_antennapatternangle = Column(Float)

    # Relationships
    location = relationship("Location", back_populates="logical_antennas")
