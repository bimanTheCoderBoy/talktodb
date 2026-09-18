from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# --- Shared Helpers ---

class IidEid(BaseModel):
    iid: str
    eid: int
class AbsLocation(BaseModel):
    latitude: float
    longitude: float
    epsg: int

# --- Cell Components ---

class CellTechnology(BaseModel):
    active: Optional[str] = "LTE"
    fixed: Optional[bool] = False

# LTE SU-MIMO configuration
class SuMimo(BaseModel):
    rxElements: Optional[int] = None
    txElements: Optional[int] = None
    dlEnabled: Optional[bool] = None
    ulEnabled: Optional[bool] = None

# LTE Power configuration
class LtePower(BaseModel):
    autoCalculatedMethod: Optional[str] = None
    referenceSignalPPRE: Optional[float] = None
    maxTxPower: Optional[float] = None


class CarrierParameters(BaseModel):
    iid: Optional[str] = None
    autoCalculatedMethod: Optional[str] = None
    referenceSignalPPRE: Optional[float] = None
    maxTxPower: Optional[float] = None
    physicalCellID: Optional[int] = None

# Main LTE configuration for Cell
class LteConfig(BaseModel):
    carrier: Optional[Dict[str, Any]] = None
    carrierParameters: Optional[CarrierParameters] = None
    supported: Optional[bool] = None
    enabled: Optional[bool] = None
    tac: Optional[int] = None
    pci: Optional[int] = None
    firstAssignedRSI: Optional[int] = None
    suMimo: Optional[SuMimo] = None
    power: Optional[LtePower] = None


class PredictionModel(BaseModel):
    modelType: Optional[Dict[str, Any]] = None
    radiusKM: Optional[float] = None
    resolutionMetres: Optional[float] = None

class PassiveAntenna(BaseModel):
    antennaPatternType: Optional[Dict[str, Any]] = None
    phyindex: Optional[int] = None

class LogicalAntenna(BaseModel):
    primaryModel: Optional[Dict[str, Any]] = None
    phyindex: Optional[int] = None
    usePredInnerOuter: Optional[bool] = None
    passive: Optional[Dict[str, Any]] = None

class PhysicalAntenna(BaseModel):
    antennaDevice: Optional[Dict[str, Any]] = None
    masterPattern1: Optional[IidEid] = None
    absLocation: Optional[AbsLocation] = None
    azimuth: Optional[float] = None
    tilt: Optional[float] = None
    height: Optional[float] = None
    index: Optional[int] = None

class Feeder(BaseModel):
    logicalAntenna: Optional[Dict[str, Any]] = None
    physicalAntenna: Optional[Dict[str, Any]] = None
    lte: Optional[Dict[str, Any]] = None
    nrt: Optional[Dict[str, Any]] = None
    logicalindex: Optional[int] = None
    location: Optional[str] = None  # String, not object


# --- Main Models ---

class PhysicalAntennaInLocation(BaseModel):
    antennaDevice: Optional[Dict[str, Any]] = None
    masterPattern1: Optional[Dict[str, Any]] = None
    absLocation: Optional[AbsLocation] = None
    azimuth: Optional[float] = None
    tilt: Optional[float] = None
    height: Optional[float] = None
    antennaType_RO: Optional[str] = None
    index: Optional[int] = None

class LogicalAntennaInLocation(BaseModel):
    index: Optional[int] = None
    phyindex: Optional[int] = None
    primaryModel: Optional[Dict[str, Any]] = None
    antennaType_RO: Optional[str] = None
    passive: Optional[Dict[str, Any]] = None
    beamSet: Optional[Dict[str, Any]] = None
    beamSwitching: Optional[Dict[str, Any]] = None

class LocationEDSModel(BaseModel):
    type_field: str = Field(..., alias="$type")
    allowedOperations: Optional[str] = None
    iid: str
    bvid: str
    propertyCode: Optional[str] = None
    
    # Address fields
    address1: Optional[str] = None
    town: Optional[str] = None
    state: Optional[str] = None
    
    # Root-level coordinates
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    epsg: Optional[int] = None
    
    # Legacy absLocation for backward compatibility
    absLocation: Optional[AbsLocation] = None
    
    # Antenna arrays
    physicalAntennas: Optional[List[PhysicalAntennaInLocation]] = None
    logicalAntennas: Optional[List[LogicalAntennaInLocation]] = None

    class Config:
        populate_by_name = True

class NrtConfig(BaseModel):
    carrier: Optional[Dict[str, Any]] = None
    carrierParameters: Optional[CarrierParameters] = None
    supported: Optional[bool] = None
    enabled: Optional[bool] = None
    tac: Optional[int] = None
    pci: Optional[int] = None
    firstAssignedRSI: Optional[int] = None
    suMimo: Optional[SuMimo] = None

class CellEDSModel(BaseModel):
    type_field: str = Field(..., alias="$type")
    allowedOperations: Optional[str] = None
    iid: str
    bvid: str
    technology: Optional[CellTechnology] = None
    parent: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None
    lte: Optional[LteConfig] = None
    nrt: Optional[NrtConfig] = None
    feeders: Optional[List[Feeder]] = None

    class Config:
        populate_by_name = True

# --- MU Node Components ---

class Plmn(BaseModel):
    iid: Optional[str] = None

class MuTechnology(BaseModel):
    fixedtechnology: Optional[str] = None

class MuCarrier(BaseModel):
    iid: Optional[str] = None

class MuLteConfig(BaseModel):
    carriers: Optional[List[MuCarrier]] = None
    enabled: Optional[bool] = None

class MuNrtConfig(BaseModel):
    carriers: Optional[List[MuCarrier]] = None
    enabled: Optional[bool] = None

class MUNodeEDSModel(BaseModel):
    type_field: str = Field(..., alias="$type")
    allowedOperations: Optional[str] = None
    iid: str
    bvid: str
    parent: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None
    plmn: Optional[Plmn] = None
    technology: Optional[MuTechnology] = None
    lte: Optional[MuLteConfig] = None
    nrt: Optional[MuNrtConfig] = None

    class Config:
        populate_by_name = True

