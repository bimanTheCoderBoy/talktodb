import logging
import math
import time
from typing import Dict, List

from ..core.exceptions import HybridSearchError
from ..core.logger import CustomLogger
from ..interfaces.catalog.keyword_search_interface import CatalogKeywordSearchInterface
from ..interfaces.catalog.vector_search_interface import CatalogVectorSearchInterface
from ..interfaces.embedding_adapter_interface import EmbeddingAdapterInterface
from ..interfaces.rerank_adapter_interface import RerankAdapterInterface
from ..schemas.catalog import CatalogColumn


class CatalogHybridSearchService:
    def __init__(
        self,
        vector_search_adapter: CatalogVectorSearchInterface,
        keyword_search_adapter: CatalogKeywordSearchInterface,
        embedding_adapter: EmbeddingAdapterInterface,
        reranker_adapter: RerankAdapterInterface,
    ):
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

    def _native_weighted_rrf(
        self,
        dense_results: Dict[str, float],
        sparse_results: Dict[str, float],
        k: int = 60,
        alpha: float = 0.5,
    ) -> Dict[str, float]:
        sorted_dense = sorted(dense_results.items(), key=lambda x: x[1], reverse=True)
        sorted_sparse = sorted(sparse_results.items(), key=lambda x: x[1], reverse=True)
        fused_scores: Dict[str, float] = {}
        for rank, (column_id, _score) in enumerate(sorted_dense, start=1):
            fused_scores[column_id] = fused_scores.get(column_id, 0.0) + (
                alpha * (1.0 / (k + rank))
            )
        for rank, (column_id, _score) in enumerate(sorted_sparse, start=1):
            fused_scores[column_id] = fused_scores.get(column_id, 0.0) + (
                (1.0 - alpha) * (1.0 / (k + rank))
            )
        return dict(sorted(fused_scores.items(), key=lambda x: x[1], reverse=True))

    async def search(self, query: str) -> List[CatalogColumn]:
        try:
            fst = time.time()
            self.logger.info(f"Catalog hybrid search for query: '{query}'")

            query_vector = await self.embedding_adapter.embed_text(query)
            vector_columns = await self.vector_search_adapter.search(query_vector)
            keyword_columns = await self.keyword_search_adapter.search(query)
            self.logger.info(
                f"Catalog vector hits: {len(vector_columns)}, keyword hits: {len(keyword_columns)}"
            )

            dense_results = {col.column_id: col.value for col in vector_columns}
            sparse_results = {col.column_id: col.value for col in keyword_columns}
            final_scores = self._native_weighted_rrf(dense_results, sparse_results)

            fused_columns: List[CatalogColumn] = []
            fused_columns.extend(
                col for col in vector_columns if final_scores.get(col.column_id) is not None
            )
            fused_columns.extend(
                col for col in keyword_columns if final_scores.get(col.column_id) is not None
            )

            seen_ids: set[str] = set()
            unique_fused: List[CatalogColumn] = []
            for col in fused_columns:
                if col.column_id not in seen_ids:
                    seen_ids.add(col.column_id)
                    unique_fused.append(col)

            by_id = {col.column_id: col for col in unique_fused}
            rerank_pool = unique_fused[: self.max_rerank_results]
            reranked = await self.reranker_adapter.rerank_catalog(query, rerank_pool)

            reranked = [(column_id, self._sigmoid(score)) for column_id, score in reranked]
            reranked = [pair for pair in reranked if pair[1] > self.min_rerank_threshold]
            if not reranked:
                self.logger.info("No catalog columns above rerank threshold.")
                return []

            results: List[CatalogColumn] = []
            for column_id, rerank_score in reranked:
                base = by_id.get(column_id)
                if base is None:
                    continue
                results.append(base.model_copy(update={"value": rerank_score}))

            self.logger.info(
                f"Catalog hybrid search completed in {time.time() - fst:.3f}s, "
                f"returning {len(results)} columns"
            )
            return results

        except Exception as e:
            raise HybridSearchError(
                message=f"Error in catalog hybrid search for query: {query} with error: {e}",
                status_code=500,
            ) from e
