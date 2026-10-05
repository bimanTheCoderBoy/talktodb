from __future__ import annotations


class CatalogTableError(Exception):
    """Base error for semantic catalog table lookup."""


class CatalogTableValidationError(CatalogTableError):
    """Invalid arguments for a catalog table lookup."""


class CatalogTableLookupFailedError(CatalogTableError):
    """Catalog lookup failed due to infrastructure or database errors."""

    def __init__(self, queried_name: str, message: str) -> None:
        self.queried_name = queried_name
        super().__init__(message)
