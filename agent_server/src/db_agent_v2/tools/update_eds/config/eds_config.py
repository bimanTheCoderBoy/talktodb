import os
from pydantic import BaseModel, Field
from functools import lru_cache
from typing import Annotated, Dict
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

Base_DIR = Path(__file__).parent

class EDSMappingConfig(BaseModel):
    """Configuration for EDS column-to-EDS mapping file."""
    
    mapping_db_eds_path: Annotated[
        str,
        Field(default=str(Base_DIR / "mapping_db_eds.json"))
    ]
    saved_data_payload_dir: Annotated[
        str,
        Field(default=str(os.getenv("EDS_JSON_EXPORT_FOLDER","eds_update_payload")))
    ]
    
    


class EDSAPIConfig(BaseModel):
    """Configuration for EDS API endpoints."""
    
    eds_update_url: Annotated[
        str,
        Field(default=os.getenv("EDS_API_BASE_URL"))
    ]
    
    api_key: Annotated[
        str,
        Field(default=os.getenv("TEOCO_API_KEY","teoco"))
    ]
    
    timeout: Annotated[
        int,
        Field(default=int(os.getenv("EDS_UPDATE_API_TIMEOUT", "60")))
    ]
    
    max_retries: Annotated[
        int,
        Field(default=int(os.getenv("EDS_UPDATE_API_MAX_RETRIES", "2")))
    ]


class EDSToolConfig(BaseModel):
    """Main configuration for EDS Update Tool."""
    
    # Maximum number of cells to update in a single batch
    max_batch_size: Annotated[
        int,
        Field(default=int(os.getenv("MAX_BATCH_SIZE", 100)))
    ]
    


DB_TO_OSS_COLUMN_MAP: Dict[str, Dict[str, str]] = {
    "LTE": {
        "lte_carrierparameters_iid":            "EARFCN DL",
        "lte_tac":                              "TAC",
        "lte_carrierparameters_maxtxpower":     "Max Tx Power",
        "lte_carrierparameters_maxscheduledusers": "Max Scheduled Users",
        "lte_sumimotxelems":                    "# of Tx Elements",
        "lte_sumimorxelems":                    "# of Rx Elements",
        "lte_carrierparameters_physicalcellid": "Physical Cell ID",
        "lte_carrierparameters_ttibundlingenabled": "actTTIbundling",
        "lte_highspeedflag":                    "High Speed Flag",
        "lte_carrierparameters_pcigroup_ro":    "rootSeqIndex",
    },
    "NR": {
        "nrt_tac":                              "TAC",
        "nrt_carrierparameters_maxtxpower":     "Max Tx Power",
        "nrt_carrierparameters_cellbandwidthparts_maxscheduledusers": "Max Scheduled Users",
        "nrt_sumimotxelems":                    "# of Tx Elements",
        "nrt_sumimorxelems":                    "# of Rx Elements",
        "nrt_carrierparameters_physicalcellid": "Physical Cell ID",
        "nrt_carrierparameters_cellbandwidthparts_downlink_prbs": "Bandwidth (MHz)",
        "nrt_sumimosupportdl":                  "SU-MIMO Downlink",
        "nrt_sumimosupportul":                  "SU-MIMO Uplink",
    },
}



@lru_cache()
def get_eds_mapping_config() -> EDSMappingConfig:
    """Get cached instance of EDS mapping configuration."""
    return EDSMappingConfig()


@lru_cache()
def get_eds_api_config() -> EDSAPIConfig:
    """Get cached instance of EDS API configuration."""
    return EDSAPIConfig()


@lru_cache()
def get_eds_tool_config() -> EDSToolConfig:
    """Get cached instance of EDS tool configuration."""
    return EDSToolConfig()


