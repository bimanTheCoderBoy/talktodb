import logging
from typing import List, Optional

from ...config.catalog_store_config import get_catalog_store_config
from ...core.catalog_lancedb_client import CatalogLanceDBClient
from ...core.exceptions import LanceDBVectorSearchError
from ...core.logger import CustomLogger
from ...interfaces.catalog.vector_search_interface import CatalogVectorSearchInterface
from ...models.catalog_column_model import CatalogColumnVectorResult
from ...schemas.catalog import CatalogColumn


class CatalogLanceDBVectorSearchAdapter(CatalogVectorSearchInterface):

    @property
    def logger(self) -> logging.Logger:
        return CustomLogger.get_instance()

    def __init__(self):
        self.lancedb_client = CatalogLanceDBClient.get_connection()
        self.config = get_catalog_store_config()

    async def search(
        self,
        query_vector: List[float],
        filter: Optional[dict] = None,
    ) -> List[CatalogColumn]:
        try:
            if filter:
                self.logger.warning(
                    "Catalog vector search filter=%s is not supported yet; ignoring.",
                    filter,
                )

            table = await self.lancedb_client.open_table(self.config.columns_table)
            results = await (
                await table.search(
                    query_vector,
                    query_type="vector",
                    vector_column_name=self.config.vector_column,
                )
            ).limit(self.config.max_num_results).to_pydantic(CatalogColumnVectorResult)

            return [
                CatalogColumn(
                    column_id=row.column_id,
                    table_name=row.table_name,
                    column_name=row.column_name,
                    data_type=row.data_type,
                    description=row.description,
                    example_use_cases=row.example_use_cases,
                    value=row.distance,
                )
                for row in results
            ]
        except Exception as e:
            raise LanceDBVectorSearchError(
                message=f"Error searching catalog lancedb (vector): {e}",
                status_code=500,
            ) from e
