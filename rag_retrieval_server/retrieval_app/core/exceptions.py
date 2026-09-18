

import logging
from ..core.logger import CustomLogger

class CustomBaseException(Exception):

    @property
    def logger(self) -> logging.Logger:
        return CustomLogger.get_instance()

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    def __str__(self):
        return f"Status Code: {self.status_code}, Message: {self.message}"


#----------------------------------------------------------------------------------
#----------------------------------------------------------------------------------
class EmbeddingError(CustomBaseException):
    def __init__(self, message: str="Embedding error", status_code: int = 500):
        super().__init__(message, status_code)


class LanceDBKeywordSearchError(CustomBaseException):
    def __init__(self, message: str="LanceDB keyword search error", status_code: int = 500):
        super().__init__(message, status_code)

class LanceDBVectorSearchError(CustomBaseException):
    def __init__(self, message: str="LanceDB vector search error", status_code: int = 500):
        super().__init__(message, status_code)


class HybridSearchError(CustomBaseException):
    def __init__(self, message: str="Hybrid search error", status_code: int = 500):
        super().__init__(message, status_code)

class RerankerError(CustomBaseException):
    def __init__(self, message: str="Reranker error", status_code: int = 500):
        super().__init__(message, status_code)

class DirectChunkRetrievalError(CustomBaseException):
    def __init__(self, message: str="Direct chunk retrieval error", status_code: int = 500):
        super().__init__(message, status_code)