import os
from pydantic import BaseModel, Field
from functools import lru_cache
from typing import Annotated


class PipelineConfig(BaseModel):
   
    output_dir: Annotated[
        str, 
        Field(default=os.getenv("OUTPUT_DIR_CANDIDATE_SERVICES", "final_output"))
    ]
    encoding: Annotated[
        str,
        Field(default=os.getenv("FILE_ENCODING", "utf-8"))
    ]


@lru_cache()
def get_pipeline_config() -> PipelineConfig:
    return PipelineConfig()
