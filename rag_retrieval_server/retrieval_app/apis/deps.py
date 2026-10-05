from ..adapters.catalog.lancedb_keyword_search_adapter import CatalogLanceDBKeywordSearchAdapter
from ..adapters.catalog.lancedb_vector_search_adapter import CatalogLanceDBVectorSearchAdapter
from ..adapters.embedding_adapter import EmbeddingAdapter
from ..adapters.lancedb_keyword_search_adapter import LanceDBKeywordSearchAdapter
from ..adapters.lancedb_vector_search_adapter import LanceDBVectorSearchAdapter
from ..adapters.reranker_adapter import RerankerAdapter
from ..services.catalog_hybrid_search_service import CatalogHybridSearchService
from ..services.direct_chunk_retrieval import DirectChunkRetrievalService
from ..services.hybrid_search_service import HybridSearchService


def get_hybrid_search_service():
    return HybridSearchService(
        LanceDBVectorSearchAdapter(),
        LanceDBKeywordSearchAdapter(),
        EmbeddingAdapter.get_instance(),
        RerankerAdapter.get_instance(),
    )


def get_catalog_hybrid_search_service():
    return CatalogHybridSearchService(
        CatalogLanceDBVectorSearchAdapter(),
        CatalogLanceDBKeywordSearchAdapter(),
        EmbeddingAdapter.get_instance(),
        RerankerAdapter.get_instance(),
    )


def get_direct_chunk_retrieval_service():
    return DirectChunkRetrievalService(LanceDBVectorSearchAdapter())