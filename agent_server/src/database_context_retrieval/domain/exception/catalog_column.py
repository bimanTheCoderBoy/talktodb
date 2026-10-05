from __future__ import annotations


class CatalogColumnError(Exception):
    """Base error for semantic catalog column lookup."""


class CatalogColumnValidationError(CatalogColumnError):
    """Invalid arguments for a catalog column lookup."""


class CatalogColumnLookupFailedError(CatalogColumnError):
    """Catalog column lookup failed due to infrastructure or database errors."""

    def __init__(
        self,
        queried_table_name: str,
        queried_column_name: str,
        message: str,
    ) -> None:
        self.queried_table_name = queried_table_name
        self.queried_column_name = queried_column_name
        super().__init__(message)
