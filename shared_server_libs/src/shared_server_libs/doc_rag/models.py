from lancedb.pydantic import LanceModel, Vector
from pydantic import Field

from .schemas import ChildChunkMetadata, ParentChunkMetadata


class ChildChunkLanceModel(LanceModel):
    """LanceDB table row for an embedded child chunk (ingestion schema)."""

    child_id: int
    parent_id: int
    text: str
    enriched_text: str
    metadata: ChildChunkMetadata
    vector: Vector(dim=768) 


class ParentChunkLanceModel(LanceModel):
    """LanceDB table row for a parent context chunk."""

    id: int
    text: str
    metadata: ParentChunkMetadata


class ChildChunkVectorResult(LanceModel):
    """Shape returned by LanceDB vector search on the child table."""

    child_id: int
    parent_id: int
    text: str
    enriched_text: str
    metadata: ChildChunkMetadata
    distance: float = Field(alias="_distance")


class ChildChunkKeywordResult(LanceModel):
    """Shape returned by LanceDB full-text search on the child table."""

    child_id: int
    parent_id: int
    text: str
    enriched_text: str
    metadata: ChildChunkMetadata
    score: float = Field(alias="_score")
