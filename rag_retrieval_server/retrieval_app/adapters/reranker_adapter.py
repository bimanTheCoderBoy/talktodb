from ..config.rerank_config import get_rerank_config
from fastembed.rerank.cross_encoder import TextCrossEncoder
import threading
from ..core.logger import CustomLogger
from typing import List, Tuple
import logging
from ..core.exceptions import RerankerError
from ..schemas.chunk_schemas import ChildChunk
from ..interfaces.rerank_adapter_interface import RerankAdapterInterface
from concurrent.futures import ThreadPoolExecutor
import asyncio

model_executor = ThreadPoolExecutor(max_workers=2)


class RerankerAdapter(RerankAdapterInterface):
    _instance = None
    _lock = threading.Lock()


    def __init__(self ):
        if RerankerAdapter._instance is not None:
            raise RuntimeError("Use RerankerAdapter.initialize() instead.")
        self.config = get_rerank_config()
   


    @property
    def logger(self) -> logging.Logger:
        return CustomLogger.get_instance()


    @classmethod
    def initialize(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance.model = TextCrossEncoder(model_name=cls._instance.config.name, cache_dir=cls._instance.config.local_path)
                    cls._instance.logger.info(f"Reranker model initialized: {cls._instance.config.name}")


    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise RuntimeError("RerankerAdapter not initialized. Call initialize() first.")
        return cls._instance
    


    
    async def rerank(self, query: str, chunks: List[ChildChunk]) -> List[Tuple[int, float]]:
        try:
            # query_doc_pairs = [(query, chunk.text) for chunk in chunks]
            chunk_ids = [chunk.child_id for chunk in chunks]
            chunk_texts = [chunk.text for chunk in chunks]
            #put the heavy task in a thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(model_executor, self.model.rerank, query, chunk_texts)
            scores = list(result)
            re_ranked_chunk_ids=list(zip(chunk_ids, scores))
            re_ranked_chunk_ids.sort(key=lambda x: x[1], reverse=True)
            return re_ranked_chunk_ids[:self.config.top_n]


        except Exception as e:
            raise RerankerError(message=f"Error reranking chunks: {e}", status_code=500) from e


    