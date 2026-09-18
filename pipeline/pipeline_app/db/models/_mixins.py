from sqlalchemy import Boolean, Column, Float, ForeignKey, Text, Integer

class BaseEntityColumns:
    """Common columns for all iid-keyed entities."""
    iid = Column(Text, primary_key=True, comment="EDS business identifier")
    eid = Column(Integer, unique=True)
    type = Column(Text)
    allowedoperations = Column(Text)
    bvid = Column(Text)

class LocationRefColumns:
    """FK + eid to location -- used by MuLTE, MuNR, CellLTE, CellNR, antennas."""
    location_iid = Column(Text, ForeignKey("location.iid", ondelete="CASCADE"), index=True)
    location_eid = Column(Integer)


class CellContextColumns:
    """App-level parent references injected during feeder extraction."""
    mu_iid = Column(Text)
    mu_eid = Column(Integer)
    cell_iid = Column(Text)
    cell_eid = Column(Integer)

class CarriedTrafficColumns:
    """PS + CS carried traffic totals -- shared by MuLTE, MuNR, Location (partially)."""
    carriedtraffictotal_pscarriedtraffictotal_protected = Column(Boolean)
    carriedtraffictotal_pscarriedtraffictotal_throughputdl = Column(Float)
    carriedtraffictotal_pscarriedtraffictotal_throughputul = Column(Float)
    carriedtraffictotal_pscarriedtraffictotal_numberofterminals = Column(Float)
    carriedtraffictotal_pscarriedtraffictotal_autoaggregated = Column(Boolean)
    carriedtraffictotal_cscarriedtraffictotal_protected = Column(Boolean)
    carriedtraffictotal_cscarriedtraffictotal_throughputdl = Column(Float)
    carriedtraffictotal_cscarriedtraffictotal_throughputul = Column(Float)
    carriedtraffictotal_cscarriedtraffictotal_numberofterminals = Column(Float)
    carriedtraffictotal_cscarriedtraffictotal_autoaggregated = Column(Boolean)

class MuBaseColumns:
    """Columns shared identically between MuLTE and MuNR."""
    lteemode = Column(Boolean)
    nodeid = Column(Integer)
    lteenodebid = Column(Integer)
    nrgnodebid = Column(Integer)
    aggregatecapacity = Column(Boolean)
    capacity = Column(Float)
    signallingoverhead = Column(Float)
    supportendc = Column(Boolean)
    supportnedc = Column(Boolean)
    supportnrdc = Column(Boolean)
    supportltedc = Column(Boolean)
    supportinternodedc = Column(Boolean)
    backhaullatencyenabled = Column(Boolean)
    fixednetworkdelayms = Column(Float)
    transmissioncapacitygbps = Column(Float)
    totalservedtrafficgbps = Column(Float)
    plmn_iid = Column(Text)
    plmn_eid = Column(Integer)
    technology_fixedtechnology = Column(Text)
    schedulerlatency_iid = Column(Text)
    schedulerlatency_eid = Column(Integer)
    nfv_enabled = Column(Boolean)