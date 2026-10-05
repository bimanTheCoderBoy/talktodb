from typing import List

from fastapi import APIRouter, Depends

from ...apis.deps import get_catalog_hybrid_search_service
from ...schemas.catalog import CatalogColumn, CatalogRetrievalRequest
from ...services.catalog_hybrid_search_service import CatalogHybridSearchService

catalog_retrieval_router = APIRouter(
    prefix="/catalog-retrieval",
    tags=["catalog-retrieval"],
)


@catalog_retrieval_router.post("/", response_model=List[CatalogColumn], status_code=200)
async def search_catalog_columns(
    request: CatalogRetrievalRequest,
    catalog_hybrid_search_service: CatalogHybridSearchService = Depends(
        get_catalog_hybrid_search_service
    ),
):
    return await catalog_hybrid_search_service.search(request.query)
