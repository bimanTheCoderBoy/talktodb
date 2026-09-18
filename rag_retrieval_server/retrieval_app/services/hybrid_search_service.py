from ..interfaces.vector_search_interface import VectorSearchInterface
from ..interfaces.keyword_search_interface import KeywordSearchInterface
from ..interfaces.embedding_adapter_interface import EmbeddingAdapterInterface
from ..interfaces.rerank_adapter_interface import RerankAdapterInterface
from typing import List, Optional, Dict
from ..schemas.chunk_schemas import ParentChunk
from ..core.exceptions import HybridSearchError
from ..core.logger import CustomLogger
import logging
import time
from ..schemas.retrieval_schemas import RetrievalFilter
import math


class HybridSearchService:
    def __init__(self, vector_search_adapter: VectorSearchInterface, keyword_search_adapter: KeywordSearchInterface, embedding_adapter: EmbeddingAdapterInterface, reranker_adapter: RerankAdapterInterface):
        self.vector_search_adapter = vector_search_adapter
        self.keyword_search_adapter = keyword_search_adapter
        self.embedding_adapter = embedding_adapter
        self.reranker_adapter = reranker_adapter
        self.max_rerank_results = 15
        self.min_rerank_threshold = 0.35

    @property
    def logger(self) -> logging.Logger:
        return CustomLogger.get_instance()

    def _sigmoid(self, x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))

    def _native_weighted_rrf(self, dense_results: Dict[int, float], sparse_results: Dict[int, float], k: int = 60, alpha: float = 0.5) -> Dict[int, float]:
        sorted_dense_results = sorted(dense_results.items(), key=lambda x: x[1], reverse=True)
        sorted_sparse_results = sorted(sparse_results.items(), key=lambda x: x[1], reverse=True)
        fused_scores: Dict[int, float] = {}
        for rank, (child_id, score) in enumerate(sorted_dense_results, start=1):
            fused_scores[child_id] = fused_scores.get(child_id, 0.0) + (alpha * (1.0 / (k + rank)))
        for rank, (child_id, score) in enumerate(sorted_sparse_results, start=1):
            fused_scores[child_id] = fused_scores.get(child_id, 0.0) + ((1.0 - alpha) * (1.0 / (k + rank)))

        return dict(sorted(fused_scores.items(), key=lambda x: x[1], reverse=True))

    async def search(self, query: str, filter: RetrievalFilter = None) -> List[ParentChunk]:
        try:
            fst = time.time()
            self.logger.info(f"Searching for query: '{query}'")

            self.logger.info(f"Getting embedding for query: '{query}'")
            query_vector = await self.embedding_adapter.embed_text(query)

            vector_chunks = await self.vector_search_adapter.search(query_vector, filter)
            self.logger.info(f"Vector search top {len(vector_chunks)} for query: '{query}'")

            keyword_chunks = await self.keyword_search_adapter.search(query, filter)
            self.logger.info(f"Keyword search top {len(keyword_chunks)} for query: '{query}'")

            self.logger.info(f"Fusing the results for query: '{query}' with filter: '{filter.model_dump_json() if filter else None}'")
            dense_results = {vector_chunk.child_id: vector_chunk.value for vector_chunk in vector_chunks}
            sparse_results = {keyword_chunk.child_id: keyword_chunk.value for keyword_chunk in keyword_chunks}
            st = time.time()

            final_scores = self._native_weighted_rrf(dense_results, sparse_results)
            end = time.time()
            self.logger.info(f"Time taken to fuse the results: {end - st} seconds")
            self.logger.info(f"Reranking the results for query: '{query}'")

            fused_child_chunks = []
            fused_child_chunks.extend([vector_chunk for vector_chunk in vector_chunks if final_scores.get(vector_chunk.child_id) is not None])
            fused_child_chunks.extend([keyword_chunk for keyword_chunk in keyword_chunks if final_scores.get(keyword_chunk.child_id) is not None])

            visited_child_chunk_ids = set()
            unique_fused_child_chunks = []
            for child_chunk in fused_child_chunks:
                if child_chunk.child_id not in visited_child_chunk_ids:
                    visited_child_chunk_ids.add(child_chunk.child_id)
                    unique_fused_child_chunks.append(child_chunk)
            fused_child_chunks = unique_fused_child_chunks
            end = time.time()
            self.logger.info(f"Time taken till reranking starts: {end - st} seconds")

            st = time.time()
            self.logger.info(f"Fused child chunks count: {len(final_scores)}")
            re_ranked_child_chunks = await self.reranker_adapter.rerank(query, fused_child_chunks[:self.max_rerank_results])
            end = time.time()
            self.logger.info(f"Time taken to rerank the results: {end - st} seconds")
            self.logger.info(f"Reranked results count: {len(re_ranked_child_chunks)}")
            self.logger.info(f"Reranked child chunks: {re_ranked_child_chunks}")

            re_ranked_child_chunks = [(x[0], self._sigmoid(x[1])) for x in re_ranked_child_chunks]
            self.logger.info(f"Reranked child chunks: {re_ranked_child_chunks}")
            re_ranked_child_chunks = [c for c in re_ranked_child_chunks if c[1] > self.min_rerank_threshold]
            if not re_ranked_child_chunks:
                self.logger.info("No relevant results found above threshold.")
                return []
            re_ranked_child_chunk_ids = set([child_chunk[0] for child_chunk in re_ranked_child_chunks])
            parent_ids = []
            parent_ids.extend([vector_chunk.parent_id for vector_chunk in vector_chunks if vector_chunk.child_id in re_ranked_child_chunk_ids])
            parent_ids.extend([keyword_chunk.parent_id for keyword_chunk in keyword_chunks if keyword_chunk.child_id in re_ranked_child_chunk_ids])

            parent_ids = list(set(parent_ids))

            self.logger.info(f"Getting parent chunks for query: '{query}'")
            parent_chunks = await self.vector_search_adapter.get_parent_chunks(parent_ids)
            self.logger.info(f"Parent chunks count: {len(parent_chunks)}")

            final_end = time.time()
            self.logger.info(f"Time taken to complete the full hybrid search: {final_end - fst} seconds")
            return parent_chunks

        except Exception as e:
            raise HybridSearchError(message=f"Error searching for query: {query} with error: {e}", status_code=500) from e
