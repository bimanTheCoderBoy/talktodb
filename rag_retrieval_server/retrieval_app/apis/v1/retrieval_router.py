from fastapi import APIRouter, Depends, HTTPException
from typing import List
from ...schemas.chunk_schemas import ParentChunk
from ...schemas.retrieval_schemas import RetrievalRequest, DirectChunkRetrievalRequest
from ...services.hybrid_search_service import HybridSearchService
from ...apis.deps import get_hybrid_search_service
from ...services.direct_chunk_retrieval import DirectChunkRetrievalService
from ...apis.deps import get_direct_chunk_retrieval_service

retrieval_router = APIRouter(
    prefix="/retrieval",
    tags=["retrieval"]
)


@retrieval_router.post("/", response_model=List[ParentChunk], status_code=200)
async def get_relevent_chunks(request: RetrievalRequest, hybrid_search_service: HybridSearchService = Depends(get_hybrid_search_service)):

    if request.filter and (request.filter.page_start and request.filter.page_end) and request.filter.page_start > request.filter.page_end:
        raise HTTPException(status_code=400, detail="Page start must be less than or equal to page end")

    return await hybrid_search_service.search(request.query, request.filter)


@retrieval_router.post("/direct_chunk_retrieval", response_model=List[ParentChunk], status_code=200)
async def get_direct_chunk_retrieval(request: DirectChunkRetrievalRequest, direct_chunk_retrieval_service: DirectChunkRetrievalService = Depends(get_direct_chunk_retrieval_service)):

    if request.filter and (request.filter.page_start and request.filter.page_end) and request.filter.page_start > request.filter.page_end:
        raise HTTPException(status_code=400, detail="Page start must be less than or equal to page end")

    return await direct_chunk_retrieval_service.retrieve_direct_chunk(request.ids, request.filter)
