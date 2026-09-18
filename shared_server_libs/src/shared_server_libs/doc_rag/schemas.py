from pydantic import BaseModel
from typing import List, Optional


class ChildSection(BaseModel):
    """Reference to a child section within a parent chunk's hierarchy."""

    sec_id: Optional[int] = None
    title: Optional[str] = None


class ParentMetadataImageData(BaseModel):
    """Image metadata embedded in a parent chunk."""

    ext: Optional[str] = None
    caption: Optional[str] = None
    url: Optional[str] = None
    page: Optional[int] = None


class ChildChunkMetadata(BaseModel):
    """Metadata carried by each child (embedded) chunk."""

    child_id: int
    parent_id: int
    chunk_type: str
    doc_title: str
    product_name: str
    version: str
    source_file: str
    section_path: str
    page_start: int
    page_end: int
    raw_text: str


class ParentChunkMetadata(BaseModel):
    """Full metadata for a parent context chunk."""

    id: int
    doc_title: str
    product_name: str
    version: str
    source_file: str
    sec_title: str
    sec_id: int
    path: str
    page_start: int
    page_end: int
    chunk_type: str
    section_parent_id: Optional[int] = None
    section_children: Optional[List[ChildSection]] = None
    section_path: str
    curr_chunk_indx: int
    next_chunk_id: Optional[int] = None
    prev_chunk_id: Optional[int] = None
    image_data: List[ParentMetadataImageData] = []

#---------------------------------------------------
class ChildChunk(BaseModel):
    """DTO representing a child chunk returned from retrieval."""

    child_id: int
    parent_id: int
    text: str
    enriched_text: str
    metadata: ChildChunkMetadata
    value: float = 0.0


class ParentChunk(BaseModel):
    """DTO representing a parent chunk returned from retrieval."""

    id: int
    text: str
    metadata: ParentChunkMetadata
