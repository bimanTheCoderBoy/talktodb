import logging
from typing import Any, Dict, List, Optional

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field, model_validator

from shared_server_libs.doc_rag.schemas import ParentChunk

from db_agent_v2.tools.base import ToolOutput
from db_agent_v2.tools.doc_retrieval.config import (
    MAX_CHUNK_TEXT_FOR_LLM,
    MAX_TOTAL_LLM_DATA,
    RAG_SERVICE_BASE_URL,
    RAG_SERVICE_TIMEOUT,
)

logger = logging.getLogger(__name__)


class DocRetrievalTool:

    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _hybrid_search(
        self, query: str, filter_payload: Optional[Dict[str, Any]]
    ) -> List[ParentChunk]:
        body: Dict[str, Any] = {"query": query}
        if filter_payload:
            body["filter"] = filter_payload

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/retrieval/", json=body
            )
            response.raise_for_status()
            return [ParentChunk(**item) for item in response.json()]

    async def _direct_retrieval(
        self, ids: List[int], filter_payload: Optional[Dict[str, Any]]
    ) -> List[ParentChunk]:
        body: Dict[str, Any] = {"ids": ids}
        if filter_payload:
            body["filter"] = filter_payload

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/retrieval/direct_chunk_retrieval",
                json=body,
            )
            response.raise_for_status()
            return [ParentChunk(**item) for item in response.json()]

    def _build_filter(
        self,
        source_files: Optional[List[str]],
        page_start: Optional[int],
        page_end: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        f: Dict[str, Any] = {}
        if source_files:
            f["source_files"] = source_files
        if page_start is not None:
            f["page_start"] = page_start
        if page_end is not None:
            f["page_end"] = page_end
        return f if f else None

    def _format_chunks_for_llm(self, chunks: List[ParentChunk]) -> str:
        if not chunks:
            return "No relevant documentation found."

        num_chunks = len(chunks)
        per_chunk_limit = min(MAX_CHUNK_TEXT_FOR_LLM, MAX_TOTAL_LLM_DATA // num_chunks)

        parts: List[str] = []
        for i, chunk in enumerate(chunks):
            meta = chunk.metadata
            text = chunk.text

            truncated_note = ""
            if len(text) > per_chunk_limit:
                text = text[:per_chunk_limit]
                truncated_note = (
                    f"\n[Truncated. Call with ids=[{chunk.id}] for full text (only if needed)]"
                )

            children = meta.section_children or []
            children_str = ", ".join(
                f"({c.sec_id}, \"{c.title}\")" for c in children
            ) if children else "None"

            navigation = "#### Navigation\n"

            if meta.prev_chunk_id is not None:
                navigation += f"prev_chunk_id: {meta.prev_chunk_id}\n"

            if meta.next_chunk_id is not None:
                navigation += f"next_chunk_id: {meta.next_chunk_id}\n"

            if meta.section_parent_id is not None:
                navigation += f"parent_section_id: {meta.section_parent_id}\n"

            if children_str != "None":
                navigation += f"children_sections(id, title): [{children_str}]\n"

            part = (
                f"=== Chunk {i+1} of {num_chunks} [Cite ID: {chunk.id}] ===\n"
                f'=== "{meta.sec_title}" ===\n'
                f'Doc: {meta.doc_title} | '
                f'Pages: {meta.page_start}-{meta.page_end} | '
                f'Section: {meta.section_path}\n'
                f"---\n"
                f"{text}{truncated_note}\n"
                f"---\n"
                f"{navigation}"
            )
            parts.append(part)

        return "\n\n".join(parts)

    def _format_chunks_for_ui(self, chunks: List[ParentChunk]) -> str:
        if not chunks:
            return "No relevant documentation found."

        parts: List[str] = []
        for chunk in chunks:
            meta = chunk.metadata
            text = chunk.text

            part = (
                f"### {meta.sec_title}\n"
                f"**Document:** {meta.doc_title} | "
                f"**Pages:** {meta.page_start}-{meta.page_end}\n\n"
                f"{text}\n"
            )
            parts.append(part)

        return "\n---\n".join(parts)

    async def execute(
        self,
        query: Optional[str],
        ids: Optional[List[int]],
        source_files: Optional[List[str]],
        page_start: Optional[int],
        page_end: Optional[int],
    ) -> ToolOutput:
        filter_payload = self._build_filter(source_files, page_start, page_end)

        try:
            if query:
                logger.info(f"[DOC_RETRIEVAL] Hybrid search: query='{query}', filter={filter_payload}")
                chunks = await self._hybrid_search(query, filter_payload)
            else:
                logger.info(f"[DOC_RETRIEVAL] Direct retrieval: ids={ids}, filter={filter_payload}")
                chunks = await self._direct_retrieval(ids, filter_payload)

            logger.info(f"[DOC_RETRIEVAL] Retrieved {len(chunks)} chunks")

            if not chunks:
                return ToolOutput(
                    status=True,
                    data="No relevant documentation found for the given query/IDs.",
                    md_data="No relevant documentation found.",
                    errors=None,
                )

            llm_data = self._format_chunks_for_llm(chunks)
            ui_data = self._format_chunks_for_ui(chunks)

            citation_map = {}
            
            for chunk in chunks:
                meta = chunk.metadata
                citation_map[str(chunk.id)] = {
                    "doc_title": meta.doc_title,
                    "sec_title": meta.sec_title,
                    "page_start": meta.page_start,
                    "page_end": meta.page_end,
                    "section_path": meta.section_path,
                    "source_file": meta.source_file,
                    "image_urls": [image.url for image in meta.image_data if image.url],
                    "content": chunk.text[:300],
                }
               

            return ToolOutput(
                status=True,
                data=llm_data,
                is_summary_available=True,
                md_data=ui_data,
                errors=None,
                extra={"citation_map": citation_map} if citation_map else None,
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"RAG retrieval service returned HTTP {e.response.status_code}: {e.response.text[:500]}"
            logger.error(f"[DOC_RETRIEVAL] {error_msg}")
            return ToolOutput(status=False, data=None, md_data="", errors=error_msg)

        except httpx.ConnectError:
            error_msg = "Cannot connect to RAG retrieval service. Service may be down."
            logger.error(f"[DOC_RETRIEVAL] {error_msg}")
            return ToolOutput(status=False, data=None, md_data="", errors=error_msg)

        except Exception as e:
            error_msg = f"Document retrieval failed: {str(e)}"
            logger.error(f"[DOC_RETRIEVAL] {error_msg}")
            return ToolOutput(status=False, data=None, md_data="", errors=error_msg)


def create_doc_retrieval_tool():
    doc_retrieval_instance = DocRetrievalTool(
        base_url=RAG_SERVICE_BASE_URL,
        timeout=RAG_SERVICE_TIMEOUT,
    )

    class DocRetrievalArgs(BaseModel):
        query: Optional[str] = Field(
            default=None,
            description=(
                "Natural language question to search ASSET documentation. "
                "Use this when you need to find information from the docs. "
                "Do NOT provide this when using parent_ids."
            ),
        )
        ids: Optional[List[int]] = Field(
            default=None,
            description=(
                "Specific chunk IDs to retrieve directly. Use ONLY for drill-down: "
                "when a previous doc_retrieval_tool result showed context cutoff or "
                "you need adjacent/parent/child sections. Pass next_chunk_id, "
                "prev_chunk_id, section_parent_id, or section children IDs from "
                "prior results. Do NOT provide query when using this."
            ),
        )
        source_files: Optional[List[str]] = Field(
            default=None,
            description=(
                "Filter by document filename if you want to retrieve information from a specific document. Available documents:\n"
                "- 'ASSET User Reference Guide.pdf' (920 pages)\n"
                "- 'ASSET Technical Reference Guide.pdf' (228 pages)\n"
                "- 'ASSET Radio User Reference Guide.pdf' (514 pages)"
            ),
        )
        page_start: Optional[int] = Field(
            default=None, description="Start page filter."
        )
        page_end: Optional[int] = Field(
            default=None, description="End page filter."
        )

        @model_validator(mode="after")
        def validate_mutually_exclusive(self):
            if self.query and self.ids:
                raise ValueError(
                    "Provide either 'query' or 'ids', not both. "
                    "Use 'query' for searching docs, 'ids' for drill-down."
                )
            if not self.query and not self.ids:
                raise ValueError(
                    "Must provide either 'query' (for search) or 'ids' (for drill-down)."
                )
            return self

    @tool("doc_retrieval_tool", args_schema=DocRetrievalArgs, parse_docstring=False)
    async def doc_retrieval_tool(
        query: Optional[str] = None,
        ids: Optional[List[int]] = None,
        source_files: Optional[List[str]] = None,
        page_start: Optional[int] = None,
        page_end: Optional[int] = None,
    ) -> ToolOutput:
        """
        Search ASSET telecom planning tool documentation (product manuals only).

        This tool queries the ASSET product documentation library which contains ONLY these 3 documents:
        - "ASSET User Reference Guide.pdf" (920 pages) - UI workflows, features, menus
        - "ASSET Technical Reference Guide.pdf" (228 pages) - algorithms, propagation models, technical details
        - "ASSET Radio User Reference Guide.pdf" (514 pages) - radio planning, cell configuration, coverage

        ## When to use
        - When the user asks about ASSET tool features, workflows, or UI
        - When the user asks about propagation models, algorithms, or technical concepts used in ASSET
        - When the user asks about radio planning methodology in ASSET
        - When you need to explain "how to do X in ASSET" or "what does feature Y do in ASSET"

        ## When NOT to use
        - NOT for querying the network asset DATABASE (use asset_db_rag_tool for that)
        - NOT for raNora application questions (it only has ASSET product documentations)
        - NOT for live cell/site/antenna data (use asset_db_rag_tool)
        - NOT for discrepancy, audit, or EDS operations

        ## Drill-down mode
        If a result shows truncated text or you need more context from related sections:
        - Use next_chunk_id / prev_chunk_id from Nav metadata for continuation
        - Use section_parent_id for broader context
        - Use section_children IDs for sub-topics
        Call the tool again with ids (no query) to fetch those specific chunks.

        ## Filters
        You can filter the results by document filename with extension, page start, and page end.
        Note: You can use multiple filters at the same time.
        Example:
        ```
        doc_retrieval_tool(query="What is the default cell configuration in ASSET?", source_files=["ASSET Radio User Reference Guide.pdf"], page_start=1, page_end=500)
        ```
        This will return the first 500 pages of the ASSET Radio User Reference Guide.
        """
        return await doc_retrieval_instance.execute(
            query=query,
            ids=ids,
            source_files=source_files,
            page_start=page_start,
            page_end=page_end,
        )

    return doc_retrieval_tool
