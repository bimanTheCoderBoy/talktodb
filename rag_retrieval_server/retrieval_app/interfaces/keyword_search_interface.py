from abc import ABC, abstractmethod
from typing import List, Optional
from ..schemas.chunk_schemas import ChildChunk


class KeywordSearchInterface(ABC):

    @abstractmethod
    async def search(self, query: str, filter: Optional[dict] = None) -> List[ChildChunk]:
        ...
