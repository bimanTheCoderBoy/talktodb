"""
Shared Pydantic field groups for EDS API schemas.

Mirrors the ORM mixin strategy in db/models/_base.py and db/models/_mixins.py.
Each mixin defines fields common to multiple entity schemas, along with their
json_path metadata used by the JSON mapper to extract values from raw API records.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SecurityFieldsMixin(BaseModel):
    """EDS security/audit fields -- identical across Location, MU, and Cell schemas."""
    security_createdate: Optional[datetime] = Field(None, json_schema_extra={"json_path": "security.createDate"})
    security_modifydate: Optional[datetime] = Field(None, json_schema_extra={"json_path": "security.modifyDate"})
    security_createuser: Optional[str] = Field(None, json_schema_extra={"json_path": "security.createUser"})
    security_modifyuser: Optional[str] = Field(None, json_schema_extra={"json_path": "security.modifyUser"})
    security_usergroup: Optional[str] = Field(None, json_schema_extra={"json_path": "security.userGroup"})
    security_visibilityinfo_usergroup: Optional[str] = Field(None, json_schema_extra={"json_path": "security.visibilityInfo.userGroup"})
    security_visibilityinfo_visibility_owner: Optional[str] = Field(None, json_schema_extra={"json_path": "security.visibilityInfo.visibility.owner"})
    security_visibilityinfo_visibility_group: Optional[str] = Field(None, json_schema_extra={"json_path": "security.visibilityInfo.visibility.group"})
    security_visibilityinfo_visibility_all: Optional[str] = Field(None, json_schema_extra={"json_path": "security.visibilityInfo.visibility.all"})
    security_permissions_owner: Optional[str] = Field(None, json_schema_extra={"json_path": "security.permissions.owner"})
    security_permissions_group: Optional[str] = Field(None, json_schema_extra={"json_path": "security.permissions.group"})
    security_permissions_all: Optional[str] = Field(None, json_schema_extra={"json_path": "security.permissions.all"})


class BaseEntityFieldsMixin(BaseModel):
    """Core identity fields shared by Cell and MU entities."""
    type: Optional[str] = Field(None, json_schema_extra={"json_path": "$type"})
    allowedoperations: Optional[str] = Field(None, json_schema_extra={"json_path": "allowedOperations"})
    iid: Optional[str] = Field(None, json_schema_extra={"json_path": "iid"})
    bvid: Optional[str] = Field(None, json_schema_extra={"json_path": "bvid"})
    eid: Optional[int] = Field(None, json_schema_extra={"json_path": "eid"})


class LocationRefFieldsMixin(BaseModel):
    """Location foreign-key reference via nested JSON paths (location.iid)."""
    location_iid: Optional[str] = Field(None, json_schema_extra={"json_path": "location.iid"})
    location_eid: Optional[int] = Field(None, json_schema_extra={"json_path": "location.eid"})


class CellContextFieldsMixin(BaseModel):
    """Parent context fields injected by the payload loader at runtime.

    These use flat JSON paths (mu_iid, not mu.iid) because they are set
    programmatically, not extracted from the nested EDS API response.
    """
    mu_iid: Optional[str] = Field(None, json_schema_extra={"json_path": "mu_iid"})
    mu_eid: Optional[int] = Field(None, json_schema_extra={"json_path": "mu_eid"})
    cell_iid: Optional[str] = Field(None, json_schema_extra={"json_path": "cell_iid"})
    cell_eid: Optional[int] = Field(None, json_schema_extra={"json_path": "cell_eid"})


class CarriedTrafficFieldsMixin(BaseModel):
    """Node-level carried traffic totals (PS + CS)."""
    carriedtraffictotal_pscarriedtraffictotal_protected: Optional[bool] = Field(None, json_schema_extra={"json_path": "carriedTrafficTotal.psCarriedTrafficTotal.protected"})
    carriedtraffictotal_pscarriedtraffictotal_throughputdl: Optional[float] = Field(None, json_schema_extra={"json_path": "carriedTrafficTotal.psCarriedTrafficTotal.throughputDL"})
    carriedtraffictotal_pscarriedtraffictotal_throughputul: Optional[float] = Field(None, json_schema_extra={"json_path": "carriedTrafficTotal.psCarriedTrafficTotal.throughputUL"})
    carriedtraffictotal_pscarriedtraffictotal_numberofterminals: Optional[float] = Field(None, json_schema_extra={"json_path": "carriedTrafficTotal.psCarriedTrafficTotal.numberOfTerminals"})
    carriedtraffictotal_pscarriedtraffictotal_autoaggregated: Optional[bool] = Field(None, json_schema_extra={"json_path": "carriedTrafficTotal.psCarriedTrafficTotal.autoAggregated"})
    carriedtraffictotal_cscarriedtraffictotal_protected: Optional[bool] = Field(None, json_schema_extra={"json_path": "carriedTrafficTotal.csCarriedTrafficTotal.protected"})
    carriedtraffictotal_cscarriedtraffictotal_throughputdl: Optional[float] = Field(None, json_schema_extra={"json_path": "carriedTrafficTotal.csCarriedTrafficTotal.throughputDL"})
    carriedtraffictotal_cscarriedtraffictotal_throughputul: Optional[float] = Field(None, json_schema_extra={"json_path": "carriedTrafficTotal.csCarriedTrafficTotal.throughputUL"})
    carriedtraffictotal_cscarriedtraffictotal_numberofterminals: Optional[float] = Field(None, json_schema_extra={"json_path": "carriedTrafficTotal.csCarriedTrafficTotal.numberOfTerminals"})
    carriedtraffictotal_cscarriedtraffictotal_autoaggregated: Optional[bool] = Field(None, json_schema_extra={"json_path": "carriedTrafficTotal.csCarriedTrafficTotal.autoAggregated"})


class MuBaseFieldsMixin(BaseModel):
    """Fields shared between MuLTE and MuNR (node-level properties)."""
    lteemode: Optional[bool] = Field(None, json_schema_extra={"json_path": "ltEeMode"})
    nodeid: Optional[int] = Field(None, json_schema_extra={"json_path": "nodeID"})
    lteenodebid: Optional[int] = Field(None, json_schema_extra={"json_path": "ltEeNodeBID"})
    nrgnodebid: Optional[int] = Field(None, json_schema_extra={"json_path": "nRgNodeBID"})
    aggregatecapacity: Optional[bool] = Field(None, json_schema_extra={"json_path": "aggregateCapacity"})
    capacity: Optional[float] = Field(None, json_schema_extra={"json_path": "capacity"})
    signallingoverhead: Optional[float] = Field(None, json_schema_extra={"json_path": "signallingOverhead"})
    supportendc: Optional[bool] = Field(None, json_schema_extra={"json_path": "supportENDC"})
    supportnedc: Optional[bool] = Field(None, json_schema_extra={"json_path": "supportNEDC"})
    supportnrdc: Optional[bool] = Field(None, json_schema_extra={"json_path": "supportNRDC"})
    supportltedc: Optional[bool] = Field(None, json_schema_extra={"json_path": "supportLTEDC"})
    supportinternodedc: Optional[bool] = Field(None, json_schema_extra={"json_path": "supportInterNodeDC"})
    backhaullatencyenabled: Optional[bool] = Field(None, json_schema_extra={"json_path": "backhaulLatencyEnabled"})
    fixednetworkdelayms: Optional[float] = Field(None, json_schema_extra={"json_path": "fixedNetworkDelayMs"})
    transmissioncapacitygbps: Optional[float] = Field(None, json_schema_extra={"json_path": "transmissionCapacityGbps"})
    totalservedtrafficgbps: Optional[float] = Field(None, json_schema_extra={"json_path": "totalServedTrafficGbps"})
    plmn_iid: Optional[str] = Field(None, json_schema_extra={"json_path": "plmn.iid"})
    plmn_eid: Optional[int] = Field(None, json_schema_extra={"json_path": "plmn.eid"})
    technology_fixedtechnology: Optional[str] = Field(None, json_schema_extra={"json_path": "technology.fixedtechnology"})
    schedulerlatency_iid: Optional[str] = Field(None, json_schema_extra={"json_path": "schedulerLatency.iid"})
    schedulerlatency_eid: Optional[int] = Field(None, json_schema_extra={"json_path": "schedulerLatency.eid"})
    nfv_enabled: Optional[bool] = Field(None, json_schema_extra={"json_path": "nfv.enabled"})
