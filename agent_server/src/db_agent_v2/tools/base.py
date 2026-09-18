from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class DataRef(BaseModel):
    """Reference to a column from the most recent asset_db_rag_tool result.

    Used by dependent tools (audit, discrepancy, eds_fixer) so the tool_runner
    can resolve large list-type arguments (cells, sites) from the stored RAG
    result without passing them through the LLM context.
    """
    target_arg: str = Field(
        description="The argument name of THIS tool to fill with resolved data (e.g. 'cells', 'cell_names', 'site_names')"
    )
    source_tool_name: str = Field(
        description="Always 'asset_db_rag_tool'. References the most recent RAG result stored by the system."
    )
    source_column: str = Field(
        description="The column name or alias from the source tool's SQL output. Read the AS alias from the SQL query in the tool output and use it exactly (e.g. 'CELL_IID', 'Site IID')."
    )


class ToolOutput(BaseModel):
    status: bool = Field(description="Success status of the tool execution")
    data: Optional[str] = Field(default=None, description="The data returned from the tool execution")
    is_summary_available: bool = Field(default=False, description="Flag indicating if the UI data is richer/different from llm_data")
    md_data: str = Field(default="Tool returned no MD data", description="Markdown formatted data for UI presentation")
    errors: Optional[str] = Field(default=None, description="Error message if execution failed")
    extra: Optional[Dict[str, Any]] = Field(default=None, description="Structured data passed to the frontend via ToolMessage artifact (not sent to the LLM)")

