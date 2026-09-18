from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SQLQueryValidationResult(BaseModel):
    is_valid: bool = Field(description="Whether the SQL query is valid")
    errors: List[str] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")

class SQLQueryResult(BaseModel):
    query: str = Field(description="The generated SQL query")
    success: bool = Field(default=True, description="Whether the SQL query generation is successful or not")
    error_reason: Optional[str] = Field(default=None, description="why the SQL query generation is not successful from the given *database context*. If successful then None")

class SQLQueryExecutionResult(BaseModel):
    status: bool = Field(description="Whether the SQL query execution is successful or not")
    columns: Optional[List[str]] = Field(default=None, description="The columns returned from the SQL query execution")
    data: Optional[List[Dict[str, Any]]] = Field(default=None, description="The data returned from the SQL query execution")
    count: Optional[int] = Field(default=None, description="The count of the data returned from the SQL query execution")
    error: Optional[str] = Field(default=None, description="The error returned from the SQL query execution")
    fuzzy_flag: Optional[bool] = Field(default=False, description="Whether the SQL query is generated using fuzzy matching or not")

class ToolOutput(BaseModel):
    status: bool = Field(description="Success status of the tool execution")
    data: Optional[str] = Field(default=None, description="The data returned from the tool execution")
    is_summary_available: bool = Field(default=False, description="Flag indicating if the UI data is richer/different from llm_data")
    md_data: str = Field(default="Tool returned no MD data", description="Markdown formatted data for UI presentation")
    errors: Optional[str] = Field(default=None, description="Error message if execution failed")