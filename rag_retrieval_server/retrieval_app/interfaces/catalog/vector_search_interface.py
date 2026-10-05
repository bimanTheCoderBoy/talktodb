from abc import ABC, abstractmethod
from typing import List, Optional

from ...schemas.catalog import CatalogColumn


class CatalogVectorSearchInterface(ABC):

    @abstractmethod
    async def search(
        self,
        query_vector: List[float],
        filter: Optional[dict] = None,
    ) -> List[CatalogColumn]:
        ...
