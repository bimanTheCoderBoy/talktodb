from __future__ import annotations


class CatalogContextSearchError(Exception):
    """Base error for catalog context search (RAG + table enrichment)."""


class CatalogContextSearchValidationError(CatalogContextSearchError):
    """Invalid arguments for catalog context search."""


class CatalogRetrievalRequestFailedError(CatalogContextSearchError):
    """Catalog column retrieval HTTP request failed."""

    def __init__(self, query: str, message: str) -> None:
        self.query = query
        super().__init__(message)
