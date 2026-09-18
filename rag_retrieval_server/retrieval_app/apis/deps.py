from ..interfaces.vector_search_interface import VectorSearchInterface
from ..interfaces.keyword_search_interface import KeywordSearchInterface
from ..interfaces.embedding_adapter_interface import EmbeddingAdapterInterface
from ..adapters.lancedb_vector_search_adapter import LanceDBVectorSearchAdapter
from ..adapters.lancedb_keyword_search_adapter import LanceDBKeywordSearchAdapter
from ..adapters.embedding_adapter import EmbeddingAdapter
from ..services.hybrid_search_service import HybridSearchService
from ..core.lancedb_client import LanceDBClient
from ..adapters.reranker_adapter import RerankerAdapter
from ..services.direct_chunk_retrieval import DirectChunkRetrievalService

def get_hybrid_search_service():
    return HybridSearchService(LanceDBVectorSearchAdapter(), LanceDBKeywordSearchAdapter(), EmbeddingAdapter.get_instance(), RerankerAdapter.get_instance())


def get_direct_chunk_retrieval_service():
    return DirectChunkRetrievalService(LanceDBVectorSearchAdapter())