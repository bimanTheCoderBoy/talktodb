from ..config.embedding_config import get_embedding_model_config
from fastembed import TextEmbedding
import threading
from ..core.logger import CustomLogger
from typing import List
import logging
from ..core.exceptions import EmbeddingError
from ..interfaces.embedding_adapter_interface import EmbeddingAdapterInterface
from concurrent.futures import ThreadPoolExecutor
import asyncio

model_executor = ThreadPoolExecutor(max_workers=2)

class EmbeddingAdapter(EmbeddingAdapterInterface):
    _instance = None
    _lock = threading.Lock()


    def __init__(self ):
        if EmbeddingAdapter._instance is not None:
            raise RuntimeError("Use EmbeddingAdapter.initialize() instead.")
        self.config = get_embedding_model_config()
   


    @property
    def logger(self) -> logging.Logger:
        return CustomLogger.get_instance()


    @classmethod
    def initialize(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance.model = TextEmbedding(model_name=cls._instance.config.model_name,cache_dir=cls._instance.config.local_path)
                    cls._instance.logger.info(f"Embedding model initialized: {cls._instance.config.model_name}")


    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise RuntimeError("EmbeddingAdapter not initialized. Call initialize() first.")
        return cls._instance
    
    async def embed_text(self, text: str) -> List[float]:
        try:
            #put the heavy task in a thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(model_executor, self.model.embed, text)
            return list(result)[0]

        except Exception as e:
            raise EmbeddingError(message=f"Error embedding text: {e}", status_code=500) from e


    