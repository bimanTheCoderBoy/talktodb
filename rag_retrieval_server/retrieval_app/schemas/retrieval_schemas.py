from pydantic import BaseModel, Field
from typing import List, Optional


class RetrievalFilter(BaseModel):
    source_files: Optional[List[str]] = Field(default=None, description="The source files to filter the retrieval.")
    page_start: Optional[int] = Field(default=None, description="The start page of the document to filter the retrieval.")
    page_end: Optional[int] = Field(default=None, description="The end page of the document to filter the retrieval.")


class RetrievalRequest(BaseModel):
    query: str = Field(description="The query to retrieve the relevant chunks from the RAG system.")
    filter: Optional[RetrievalFilter] = Field(default=None, description="The filter to apply to the retrieval.")


class DirectChunkRetrievalRequest(BaseModel):
    ids: List[int] = Field(description="The ids to retrieve the direct chunks from the RAG system.")
    filter: Optional[RetrievalFilter] = Field(default=None, description="The filter to apply to the retrieval.")
