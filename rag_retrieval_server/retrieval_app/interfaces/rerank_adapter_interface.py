from abc import ABC, abstractmethod
from typing import List, Tuple
from ..schemas.chunk_schemas import ChildChunk


class RerankAdapterInterface(ABC):
    @abstractmethod
    async def rerank(self, query: str, chunks: List[ChildChunk]) -> List[Tuple[int, float]]:
        ...