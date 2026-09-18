import logging
from ..core.logger import CustomLogger
from ..core.lancedb_client import LanceDBClient
from typing import Optional, List
from ..core.exceptions import LanceDBVectorSearchError
from ..models.child_chunk_model import ChildChunkVectorResult
from ..models.parent_chunk_model import ParentChunkLanceModel
from ..schemas.chunk_schemas import ChildChunk, ParentChunk
from ..config.store_config import get_lancedb_store_config
from ..interfaces.vector_search_interface import VectorSearchInterface
from ..schemas.retrieval_schemas import RetrievalFilter


class LanceDBVectorSearchAdapter(VectorSearchInterface):

    @property
    def logger(self) -> logging.Logger:
        return CustomLogger.get_instance()

    def __init__(self):
        self.lancedb_client = LanceDBClient.get_connection()
        self.config = get_lancedb_store_config()

    async def search(self, query_vector: List[float], filter: RetrievalFilter = None) -> List[ChildChunk]:
        try:
            child_table = await self.lancedb_client.open_table(self.config.child_table)

            if not filter or (not filter.source_files and not filter.page_start and not filter.page_end):
                children_table_results = await (
                    await child_table.search(query_vector, query_type="vector", vector_column_name="vector")
                ).limit(self.config.max_num_results).to_pydantic(ChildChunkVectorResult)
            else:
                conditions = []
                if filter.source_files:
                    if len(filter.source_files) > 1:
                        conditions.append(f"`metadata`.`source_file` in {tuple(filter.source_files)}")
                    else:
                        conditions.append(f"`metadata`.`source_file` == '{filter.source_files[0]}'")
                if filter.page_start:
                    conditions.append(f"`metadata`.`page_start` >= {filter.page_start}")
                if filter.page_end:
                    conditions.append(f"`metadata`.`page_end` <= {filter.page_end}")

                filter_str = " AND ".join(conditions)
                children_table_results = await (
                    await child_table.search(query_vector, query_type="vector", vector_column_name="vector")
                ).where(filter_str).limit(self.config.max_num_results).to_pydantic(ChildChunkVectorResult)

            children_table_results_dto = [
                ChildChunk(
                    child_id=result.child_id,
                    parent_id=result.parent_id,
                    text=result.text,
                    enriched_text=result.enriched_text,
                    metadata=result.metadata,
                    value=result.distance,
                )
                for result in children_table_results
            ]
            return children_table_results_dto
        except Exception as e:
            filter_info = filter.model_dump_json() if filter and hasattr(filter, 'model_dump_json') else str(filter)
            raise LanceDBVectorSearchError(
                message=f"Error searching lancedb with filter: {filter_info} and error: {e}",
                status_code=500,
            )

    async def get_parent_chunks(self, ids: List[int], filter: RetrievalFilter = None) -> List[ParentChunk]:
        try:
            parent_table = await self.lancedb_client.open_table(self.config.parent_table)

            if len(ids) == 1:
                filter_str = f"id = { ids[0]} or `metadata`.`sec_id` = { ids[0]}"
            else:
                filter_str = f"id IN {tuple(ids)} or `metadata`.`sec_id` IN {tuple(ids)}"

            if filter and (filter.source_files or filter.page_start or filter.page_end):
                conditions = []
                if filter.source_files:
                    if len(filter.source_files) > 1:
                        conditions.append(f"`metadata`.`source_file` in {tuple(filter.source_files)}")
                    else:
                        conditions.append(f"`metadata`.`source_file` == '{filter.source_files[0]}'")
                if filter.page_start:
                    conditions.append(f"`metadata`.`page_start` >= {filter.page_start}")
                if filter.page_end:
                    conditions.append(f"`metadata`.`page_end` <= {filter.page_end}")

                if conditions:
                    filter_str += " AND " + " AND ".join(conditions)

            parent_table_results = await parent_table.query().where(filter_str).to_pydantic(ParentChunkLanceModel)

            parent_table_results_dto = [
                ParentChunk(
                    id=result.id,
                    text=result.text,
                    metadata=result.metadata,
                )
                for result in parent_table_results
            ]
            return parent_table_results_dto

        except Exception as e:
            raise LanceDBVectorSearchError(
                message=f"Error getting parent chunks with ids: {ids[:5] if ids else []}... and error: {e}",
                status_code=500,
            )
