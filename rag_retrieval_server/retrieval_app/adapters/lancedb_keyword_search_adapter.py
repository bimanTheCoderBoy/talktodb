import logging
from ..core.logger import CustomLogger
from ..core.lancedb_client import LanceDBClient
from typing import Optional, List
from ..config.store_config import get_lancedb_store_config
from ..models.child_chunk_model import ChildChunkKeywordResult
from ..schemas.chunk_schemas import ChildChunk
from ..core.exceptions import LanceDBKeywordSearchError
from ..interfaces.keyword_search_interface import KeywordSearchInterface
from ..schemas.retrieval_schemas import RetrievalFilter


class LanceDBKeywordSearchAdapter(KeywordSearchInterface):

    @property
    def logger(self) -> logging.Logger:
        return CustomLogger.get_instance()

    def __init__(self):
        self.lancedb_client = LanceDBClient.get_connection()
        self.config = get_lancedb_store_config()

    async def search(self, query: str, filter: RetrievalFilter = None) -> List[ChildChunk]:
        try:
            child_table = await self.lancedb_client.open_table(self.config.child_table)
            if not filter or (not filter.source_files and not filter.page_start and not filter.page_end):
                children_table_results = await (
                    await child_table.search(query, query_type="fts", fts_columns="text")
                ).limit(self.config.max_num_results).to_pydantic(ChildChunkKeywordResult)
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
                    await child_table.search(query, query_type="fts", fts_columns="text")
                ).where(filter_str).limit(self.config.max_num_results).to_pydantic(ChildChunkKeywordResult)

            children_table_results_dto = [
                ChildChunk(
                    child_id=result.child_id,
                    parent_id=result.parent_id,
                    text=result.text,
                    enriched_text=result.enriched_text,
                    metadata=result.metadata,
                    value=result.score,
                )
                for result in children_table_results
            ]
            return children_table_results_dto

        except Exception as e:
            raise LanceDBKeywordSearchError(
                message=f"Error searching lancedb for keyword: '{query}' with error: {e}",
                status_code=500,
            )
