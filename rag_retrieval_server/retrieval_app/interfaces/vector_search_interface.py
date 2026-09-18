from abc import ABC, abstractmethod
from typing import List, Optional
from ..schemas.chunk_schemas import ChildChunk, ParentChunk


class VectorSearchInterface(ABC):

    @abstractmethod
    async def search(self, query_vector: List[float], filter: Optional[dict] = None) -> List[ChildChunk]:
        ...

    @abstractmethod
    async def get_parent_chunks(self, parent_ids: List[int], filter: Optional[dict] = None) -> List[ParentChunk]:
        ...
