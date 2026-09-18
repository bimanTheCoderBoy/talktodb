"""
Pydantic schemas for EDS Management Unit entities (LTE and NR).

Each model inherits shared fields from mixins and defines only the
technology-specific fields locally.
"""

from typing import Optional

from pydantic import Field

from pipeline_app.schemas._mixins import (
    BaseEntityFieldsMixin,
    CarriedTrafficFieldsMixin,
    LocationRefFieldsMixin,
    MuBaseFieldsMixin,
    SecurityFieldsMixin,
)


class MuLTEModel(
    BaseEntityFieldsMixin,
    MuBaseFieldsMixin,
    CarriedTrafficFieldsMixin,
    LocationRefFieldsMixin,
    SecurityFieldsMixin,
):
    # LTE-specific fields
    lte_signallingoverhead: Optional[float] = Field(None, json_schema_extra={"json_path": "lte.signallingOverhead"})
    lte_capacity: Optional[float] = Field(None, json_schema_extra={"json_path": "lte.capacity"})
    lte_enabled: Optional[bool] = Field(None, json_schema_extra={"json_path": "lte.enabled"})
    lte_carriers_iid: Optional[str] = Field(None, json_schema_extra={"json_path": "lte.carriers[0].iid"})
    lte_carriers_eid: Optional[float] = Field(None, json_schema_extra={"json_path": "lte.carriers[0].eid"})
    lte_carriedtraffictotal_pscarriedtraffictotal_protected: Optional[bool] = Field(None, json_schema_extra={"json_path": "lte.carriedTrafficTotal.psCarriedTrafficTotal.protected"})
    lte_carriedtraffictotal_pscarriedtraffictotal_throughputdl: Optional[float] = Field(None, json_schema_extra={"json_path": "lte.carriedTrafficTotal.psCarriedTrafficTotal.throughputDL"})
    lte_carriedtraffictotal_pscarriedtraffictotal_throughputul: Optional[float] = Field(None, json_schema_extra={"json_path": "lte.carriedTrafficTotal.psCarriedTrafficTotal.throughputUL"})
    lte_carriedtraffictotal_pscarriedtraffictotal_numberofterminals: Optional[float] = Field(None, json_schema_extra={"json_path": "lte.carriedTrafficTotal.psCarriedTrafficTotal.numberOfTerminals"})
    lte_carriedtraffictotal_pscarriedtraffictotal_autoaggregated: Optional[bool] = Field(None, json_schema_extra={"json_path": "lte.carriedTrafficTotal.psCarriedTrafficTotal.autoAggregated"})


class MuNRModel(
    BaseEntityFieldsMixin,
    MuBaseFieldsMixin,
    CarriedTrafficFieldsMixin,
    LocationRefFieldsMixin,
    SecurityFieldsMixin,
):
    # NR-specific fields
    nrt_signallingoverhead: Optional[float] = Field(None, json_schema_extra={"json_path": "nrt.signallingOverhead"})
    nrt_capacity: Optional[float] = Field(None, json_schema_extra={"json_path": "nrt.capacity"})
    nrt_enabled: Optional[bool] = Field(None, json_schema_extra={"json_path": "nrt.enabled"})
    nrt_carriers_iid: Optional[str] = Field(None, json_schema_extra={"json_path": "nrt.carriers[0].iid"})
    nrt_carriers_eid: Optional[float] = Field(None, json_schema_extra={"json_path": "nrt.carriers[0].eid"})
    nrt_carriedtraffictotal_pscarriedtraffictotal_protected: Optional[bool] = Field(None, json_schema_extra={"json_path": "nrt.carriedTrafficTotal.psCarriedTrafficTotal.protected"})
    nrt_carriedtraffictotal_pscarriedtraffictotal_throughputdl: Optional[float] = Field(None, json_schema_extra={"json_path": "nrt.carriedTrafficTotal.psCarriedTrafficTotal.throughputDL"})
    nrt_carriedtraffictotal_pscarriedtraffictotal_throughputul: Optional[float] = Field(None, json_schema_extra={"json_path": "nrt.carriedTrafficTotal.psCarriedTrafficTotal.throughputUL"})
    nrt_carriedtraffictotal_pscarriedtraffictotal_numberofterminals: Optional[float] = Field(None, json_schema_extra={"json_path": "nrt.carriedTrafficTotal.psCarriedTrafficTotal.numberOfTerminals"})
    nrt_carriedtraffictotal_pscarriedtraffictotal_autoaggregated: Optional[bool] = Field(None, json_schema_extra={"json_path": "nrt.carriedTrafficTotal.psCarriedTrafficTotal.autoAggregated"})
