import asyncio
from typing import Optional, Tuple

from agent.subgraphs.coverage.build_data_phase.tool_state import SQLQueryExecutionResult, SQLQueryValidationResult, SQLQueryResult
import re
from agent.db.DatabaseManager import DynamicAsyncDatabaseManager, get_global_db_manager, global_db_manager
from agent.subgraphs.coverage.build_data_phase.tool_config import AssetDBRagToolConfig
from db_agent_v2.config.agent_config import LLM_CALL_TIMEOUT
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage
from langchain_core.messages import HumanMessage
from agent.constants.prompt_registry.run_coverage_agent_prompt import SYSTEM_PROMPT
from datetime import datetime, date
import logging
from decimal import Decimal
from typing import List, Any

logger = logging.getLogger(__name__)


def _convert_datetime_to_str(obj):
    """
    Recursively convert datetime, date, and Decimal objects to JSON-serializable formats.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        # Convert to float for numeric JSON, or str(obj) if you need absolute precision
        return float(obj) 
    elif isinstance(obj, dict):
        return {key: _convert_datetime_to_str(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return type(obj)(_convert_datetime_to_str(item) for item in obj)
    else:
        return obj

class AssetDBRAGTool:

    # basic constructor to initialize the database manager
    def __init__(self, db_manager:Optional[DynamicAsyncDatabaseManager] = None, system_prompt:Optional[str] = None):

        cnf=AssetDBRagToolConfig()
        self.MAX_RETRIES = cnf.MAX_RETRIES or 3 # Maximum number of retries for the SQL query generation
        self.llm = ChatOpenAI(**cnf.llm)
        self.system_prompt = system_prompt or SYSTEM_PROMPT
        # self.fuzzy_flag = False
        self.db_manager = db_manager or get_global_db_manager()
        if self.db_manager is None:
            raise ValueError("Database manager is not initialized")
    

    #Validate the SQL query
    async def _validate_sql_query(self, query: str , project_name: str, user_email: str) -> SQLQueryValidationResult:
        """
        Advanced SQL query validation with context awareness
        """
        errors = []
        warnings = []
        
        # Basic syntax checks
        query_lower = query.lower().strip()
        
        # Must be SELECT
        if query_lower.startswith(('update', 'insert', 'delete', 'alter', 'drop', 'truncate', 'rename', 'grant', 'revoke', 'commit', 'rollback', 'savepoint', 'release savepoint')):
            errors.append("Query must not start with any of the following keywords: UPDATE, INSERT, DELETE, ALTER, DROP, TRUNCATE, RENAME, GRANT, REVOKE, COMMIT, ROLLBACK, SAVEPOINT, RELEASE SAVEPOINT")
        
        # Check for dangerous patterns
        dangerous_patterns = [
            (r'\bselect\s*\*\s*from\s+\w+\s*(?:;|\s*$)', "SELECT * without WHERE clause may return too many rows"),
            #(r'\bunion\s+all\b.*\bunion\s+all\b', "Multiple UNION ALL operations may produce large results")
        ]
        
        for pattern, message in dangerous_patterns:
            if re.search(pattern, query_lower):
                warnings.append(message)
        
        # Check for required WHERE clause on large tables (heuristic)
        large_table_indicators = ['cell', 'location', 'mu', 'cell_logical_antenna', 'cell_physical_antenna']
        has_where = 'where' in query_lower
        
        for indicator in large_table_indicators:
            if indicator in query_lower and not has_where:
                warnings.append(f"Query on '{indicator}' table without WHERE clause may return many rows")


        # validate against EXPLAIN command
        result = await self.db_manager.execute_query(project_name, f"EXPLAIN  {query}", user_email=user_email)
        if not result['status']:
            errors.append(f"Error executing EXPLAIN command: {result['error']}")
        
        
        is_valid = len(errors) == 0
        return SQLQueryValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
    


    def _parse_sql_query_result(self, raw_content: str) -> SQLQueryResult:
        """Parse raw LLM text output into SQLQueryResult.

        Handles multiple output shapes a model may produce:
        1. ```sql ... ```  — happy-path SQL
        2. ```error ... ``` — model reports it cannot generate
        3. Any other fenced code block containing a SELECT
        4. Raw SELECT without fencing
        5. Catch-all: treat entire response as an error reason
        """
        content = raw_content.strip()

        sql_match = re.search(r"```sql\s*\n?(.*?)```", content, re.DOTALL)
        if sql_match:
            query = sql_match.group(1).strip()
            if query:
                return SQLQueryResult(query=query, success=True, error_reason=None)

        err_match = re.search(r"```error\s*\n?(.*?)```", content, re.DOTALL)
        if err_match:
            return SQLQueryResult(query="", success=False, error_reason=err_match.group(1).strip())

        any_block = re.search(r"```\w*\s*\n?(.*?)```", content, re.DOTALL)
        if any_block:
            block_content = any_block.group(1).strip()
            if block_content.upper().startswith("SELECT"):
                return SQLQueryResult(query=block_content, success=True, error_reason=None)
            else:
                return SQLQueryResult(query="", success=False, error_reason=block_content)

        if content.upper().startswith("SELECT"):
            return SQLQueryResult(query=content, success=True, error_reason=None)

        logger.warning("[SQL Gen] Could not parse LLM response: %s", content[:200])
        return SQLQueryResult(query="", success=False, error_reason=content[:500])

    async def _generate_sql_query_with_validation_loop(self, task: List[AnyMessage], need_latest_data:bool, project_name: str, user_email: str, fuzzy_flag:bool = False, stream_writer=None) -> Tuple[int,SQLQueryResult]:
        # if fuzzy_flag:
        #     system_prompt=SystemMessage(content=FUZZY_PROMPT)
        # else:
        system_prompt=SystemMessage(content=self.system_prompt)
        llm=self.llm
        user_prompt=HumanMessage(content=task[-1].content + f" and for this task your `need_latest_data` parameter is {need_latest_data}")
        chat_history=[system_prompt] + task[:-1] + [user_prompt]
        error=None
        retry_count=0

        #Loop until the SQL query is generated successfully or the maximum retries are reached

        #There is 4 types of errors that can happen:
        #1. The SQL query is not generated successfully
        #2. The SQL query is generated successfully but the validation failed
        #3. The LLM execution failed
        #4. retry limit reached
        while retry_count < self.MAX_RETRIES:
            response:Optional[SQLQueryResult]=None
            raw_content: str = ""
            try:
                logger.info(f"[SQL Gen] Attempt {retry_count+1}/{self.MAX_RETRIES} for project '{project_name}'")
                try:
                    ai_message = await asyncio.wait_for(llm.ainvoke(chat_history), timeout=LLM_CALL_TIMEOUT)
                    raw_content = ai_message.content
                    response = self._parse_sql_query_result(raw_content)
                except asyncio.TimeoutError:
                    logger.error(f"[SQL Gen] LLM call TIMED OUT after {LLM_CALL_TIMEOUT}s on attempt {retry_count+1}")
                    if stream_writer:
                        stream_writer({"status": "retrying", "message": f"LLM timed out, retry {retry_count+1}/{self.MAX_RETRIES}..."})
                    retry_count += 1
                    continue

                if not response.success:
                    logger.warning(f"[SQL Gen] LLM returned success=False. Reason: {response.error_reason}")
                    return (retry_count,response)
                logger.info(f"[SQL Gen] Generated query: {response.query}")
                validation_result=await self._validate_sql_query(response.query, project_name, user_email)
                if not validation_result.is_valid:
                    logger.warning(f"[SQL Gen] Validation failed. Errors: {validation_result.errors}")
                    chat_history.extend([
                        AIMessage(content=raw_content),
                        HumanMessage(content=f"Error: {validation_result.errors}. Please generate the SQL query again resolving the errors.")
                    ])
                    retry_count+=1
                    continue
                else:
                    logger.info(f"[SQL Gen] Query validated successfully on attempt {retry_count+1}")
                    return (retry_count,response)

            except Exception as e:
                error=str(e)
                logger.error(f"[SQL Gen] Exception on attempt {retry_count+1}: {error}")
                if stream_writer:
                    stream_writer({"status": "retrying", "message": f"LLM error, retry {retry_count+1}/{self.MAX_RETRIES}..."})
                retry_count+=1
                continue
        #handling error case 4
        if error:
            return (retry_count,SQLQueryResult(query="",success=False,error_reason=error))
        else:
            return (retry_count,SQLQueryResult(query="",success=False,error_reason="Max retries reached But the SQL query is not generated successfully"))




    #Execute the SQL query
    async def _execute_sql_query(self, query: str , project_name: str, user_email: str, fuzzy_flag:bool = False) -> SQLQueryExecutionResult:
        """
        Execute the SQL query and return the result
        """
        result = await self.db_manager.execute_query(project_name, query, user_email=user_email)
        return SQLQueryExecutionResult(status=result['status'],data=result['data'],error=result['error'],columns=result['columns'],count=result['count'], fuzzy_flag=fuzzy_flag)
    
    
    async def validate_and_get_exist_cells_only(self, cell_iids: List[str], project_name: str, user_email: str) -> Tuple[str, List[str]]:
        """
            Validate the SQL query and get the exist cells only
        """

        if len(cell_iids) == 0:
            return []
        formatted_iids = ",".join(f"LOWER('{item}')" for item in cell_iids)
        query = f"""
        SELECT DISTINCT iid FROM cell_lte
        WHERE LOWER(iid) IN ({formatted_iids})
        AND imported_at = (SELECT MAX(imported_at) FROM cell_lte)

        UNION

        SELECT DISTINCT iid FROM cell_nr
        WHERE LOWER(iid) IN ({formatted_iids})
        AND imported_at = (SELECT MAX(imported_at) FROM cell_nr)
        """
        result = await self.db_manager.execute_query(project_name, query, user_email=user_email)
        if not result['status']:
            return query, []
        return query, [str(row.get("iid")) for row in result['data']]


    async def generate_and_execute_sql_query(self, task: List[AnyMessage], need_latest_data: bool, project_name: str, user_email: str, fuzzy_flag: bool = False, stream_writer=None) -> SQLQueryExecutionResult:
        # 1. Generate and Run the query
        retry_count, response = await self._generate_sql_query_with_validation_loop(task, need_latest_data, project_name, user_email, fuzzy_flag, stream_writer)
        
        if not response.success:
            return SQLQueryExecutionResult(status=False, data=None, error=response.error_reason, columns=None, count=0, fuzzy_flag=fuzzy_flag), response.query

        result = await self._execute_sql_query(response.query, project_name, user_email, fuzzy_flag)

        # 2. Logic Gate: Should we trigger Fuzzy Search?
        # if (result.count == 0 and result.status and not fuzzy_flag):
        #     # Only check the WHERE clause to avoid false positives from the SELECT list
        #     query_lower = response.query.lower()
        #     if "where" in query_lower:
        #         where_clause = query_lower.split("where")[-1]

        #         # Detect string literal comparisons against identifier columns.
        #         # Matches patterns like: LOWER(col) = LOWER('value') or col = 'value'
        #         # This avoids false positives from table/column names like c1.cell_iid
        #         # appearing in JOINs, self-joins, or numeric comparisons.
        #         string_literal_filter = r"(?:lower\s*\(.*?\)\s*=\s*lower\s*\(\s*'[^']+'\s*\))|(?:=\s*'[^']+')"

        #         if re.search(string_literal_filter, where_clause):
        #             logger.info("[ASSET DB RAG] Identifier mismatch detected. Triggering Fuzzy Search.")
        #             fuzzy_task = f"User Question: {task}\nOriginal SQL Query: {response.query}"
        #             # Recurse with fuzzy_flag=True
        #             return await self.generate_and_execute_sql_query(fuzzy_task, need_latest_data, project_name, user_email, fuzzy_flag=True)

        return result, response.query