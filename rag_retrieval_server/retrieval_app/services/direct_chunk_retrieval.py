from ..interfaces.vector_search_interface import VectorSearchInterface
from ..schemas.chunk_schemas import ParentChunk
from ..core.exceptions import DirectChunkRetrievalError
from ..core.logger import CustomLogger
import logging
from typing import List

from ..schemas.retrieval_schemas import RetrievalFilter


class DirectChunkRetrievalService:
    def __init__(self, vector_search_adapter: VectorSearchInterface):
        self.vector_search_adapter = vector_search_adapter

    @property
    def logger(self) -> logging.Logger:
        return CustomLogger.get_instance()

    async def retrieve_direct_chunk(self, parent_ids: List[int], filter: RetrievalFilter = None) -> List[ParentChunk]:
        try:
            self.logger.info(f"Retrieving direct chunk for parent ids: '{parent_ids[:5] if parent_ids else []}...'")
            parent_chunks = await self.vector_search_adapter.get_parent_chunks(parent_ids, filter)
            self.logger.info(f"Parent chunks count: {len(parent_chunks)}")
            return parent_chunks
        except Exception as e:
            raise DirectChunkRetrievalError(
                message=f"Error retrieving direct chunk for parent ids: {parent_ids[:5] if parent_ids else []}... with error: {e}",
                status_code=500,
            ) from e
