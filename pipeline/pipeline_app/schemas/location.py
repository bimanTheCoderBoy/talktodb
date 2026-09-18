"""
Pydantic schema for EDS Location entities.

Location does NOT use BaseEntityFieldsMixin because its iid/eid/bvid fields
have the same flat json_paths but are semantically distinct (site-level, not
cell/MU-level). Keeping them local avoids confusion.
"""

from typing import Optional

from pydantic import Field

from pipeline_app.schemas._mixins import SecurityFieldsMixin


class LocationModel(SecurityFieldsMixin):
    type: Optional[str] = Field(None, json_schema_extra={"json_path": "$type"})
    address1: Optional[str] = Field(None, json_schema_extra={"json_path": "address1"})
    town: Optional[str] = Field(None, json_schema_extra={"json_path": "town"})
    postcode: Optional[str] = Field(None, json_schema_extra={"json_path": "postCode"})
    propertycode: Optional[str] = Field(None, json_schema_extra={"json_path": "propertyCode"})
    state: Optional[str] = Field(None, json_schema_extra={"json_path": "state"})
    longitude: Optional[float] = Field(None, json_schema_extra={"json_path": "longitude"})
    latitude: Optional[float] = Field(None, json_schema_extra={"json_path": "latitude"})
    groundhgt: Optional[float] = Field(None, json_schema_extra={"json_path": "groundHgt"})
    searchrad: Optional[float] = Field(None, json_schema_extra={"json_path": "searchRad"})
    mastspace: Optional[float] = Field(None, json_schema_extra={"json_path": "mastSpace"})
    mttr: Optional[float] = Field(None, json_schema_extra={"json_path": "mttr"})
    buildingheight: Optional[int] = Field(None, json_schema_extra={"json_path": "buildingHeight"})
    mounting: Optional[str] = Field(None, json_schema_extra={"json_path": "mounting"})
    epsg: Optional[int] = Field(None, json_schema_extra={"json_path": "epsg"})
    allowedoperations: Optional[str] = Field(None, json_schema_extra={"json_path": "allowedOperations"})
    iid: Optional[str] = Field(None, json_schema_extra={"json_path": "iid"})
    bvid: Optional[str] = Field(None, json_schema_extra={"json_path": "bvid"})
    eid: Optional[int] = Field(None, json_schema_extra={"json_path": "eid"})
    tower_iid: Optional[str] = Field(None, json_schema_extra={"json_path": "tower.iid"})
    tower_eid: Optional[int] = Field(None, json_schema_extra={"json_path": "tower.eid"})
    carriedtraffictotal_pscarriedtraffictotal_autoaggregated: Optional[bool] = Field(None, json_schema_extra={"json_path": "carriedTrafficTotal.psCarriedTrafficTotal.autoAggregated"})
    carriedtraffictotal_cscarriedtraffictotal_autoaggregated: Optional[bool] = Field(None, json_schema_extra={"json_path": "carriedTrafficTotal.csCarriedTrafficTotal.autoAggregated"})
