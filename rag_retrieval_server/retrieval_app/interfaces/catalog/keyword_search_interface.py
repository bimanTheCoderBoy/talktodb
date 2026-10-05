from abc import ABC, abstractmethod
from typing import List, Optional

from ...schemas.catalog import CatalogColumn


class CatalogKeywordSearchInterface(ABC):

    @abstractmethod
    async def search(
        self,
        query: str,
        filter: Optional[dict] = None,
    ) -> List[CatalogColumn]:
        ...
