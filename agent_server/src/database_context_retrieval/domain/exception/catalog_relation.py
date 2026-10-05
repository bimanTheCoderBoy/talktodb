from __future__ import annotations


class CatalogRelationError(Exception):
    """Base error for semantic catalog relation lookup."""


class CatalogRelationValidationError(CatalogRelationError):
    """Invalid arguments for a catalog relation lookup."""


class CatalogRelationLookupFailedError(CatalogRelationError):
    """Catalog relation lookup failed due to infrastructure or database errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
