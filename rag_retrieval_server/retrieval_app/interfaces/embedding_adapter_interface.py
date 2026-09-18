from abc import ABC, abstractmethod 
from typing import List

class EmbeddingAdapterInterface(ABC):

    @abstractmethod
    async def embed_text(self, text: str)->List[float]:
        pass

   