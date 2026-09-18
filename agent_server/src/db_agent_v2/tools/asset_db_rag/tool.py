import asyncio
from typing import Any, Dict, Optional, Tuple

from annotated_types import IsDigit
from db_agent_v2.tools.asset_db_rag.tool_state import SQLQueryExecutionResult, SQLQueryValidationResult, SQLQueryResult
from langchain_core.tools import InjectedToolArg, tool
import re
from db_agent_v2.db.DatabaseManager import DynamicAsyncDatabaseManager, global_db_manager
from db_agent_v2.config.tool_config import AssetDBRagToolConfig
from db_agent_v2.config.agent_config import LLM_CALL_TIMEOUT
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.messages import HumanMessage
from db_agent_v2.tools.asset_db_rag.DBRagPromptTemplate import FUZZY_IDENTIFIER, FUZZY_PROMPT, SYSTEM_PROMPT
from db_agent_v2.tools.base import ToolOutput
from langgraph.prebuilt import InjectedState
from langgraph.config import get_stream_writer
from security.encryption.iid_hash_utils import (
    HASHING_ENABLED as IID_HASHING_ENABLED,
    IID_COLUMN_NAMES,
    reverse_map_hashes,
    collect_hashes_from_rows,
    apply_reverse_map,
)
from typing import Annotated
import json
from datetime import datetime, date
import logging
from decimal import Decimal
from pydantic import BaseModel, Field

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
        self.db_manager = db_manager or global_db_manager
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
    


    async def _search_db_for_column(self, error_reason: str, task: str, project_name: str, user_email: str) -> Optional[str]:
        """When LLM refuses because column isn't in prompt, search the actual DB for it using
        fragments from the user task + any column-ish term quoted in the error."""
        bad_col = ""
        quoted = re.findall(r'[`\'"]([\w]+)[`\'"]', error_reason)
        if quoted:
            bad_col = quoted[0]

        fragments = self._extract_search_fragments(task, bad_col)
        if not fragments:
            return None

        try:
            similar = await self._find_similar_columns(fragments, project_name, user_email)
            if similar:
                found = [f"{t}.{c}" for t, c, _ in similar[:10]]
                logger.info(f"[SQL Gen] DB column search found: {found}")
                return (
                    f"The column DOES exist in the database but is not in your table_context. "
                    f"Matching columns found in DB (ranked by relevance): {', '.join(found)}. "
                    f"Use these exact column names to generate the query. "
                    f"They ARE valid — generate the SQL using them."
                )
        except Exception as e:
            logger.warning(f"[SQL Gen] DB column search failed: {e}")
        return None

    # JOIN guidance for cross-table column resolution
    _TABLE_JOIN_HINTS = {
        "cell_physical_antenna": "JOIN cell_physical_antenna ON cell_physical_antenna.cell_iid = {cell_table}.cell_iid",
        "cell_logical_antenna": "JOIN cell_logical_antenna ON cell_logical_antenna.cell_iid = {cell_table}.cell_iid",
        "location": "JOIN location ON location.iid = {cell_table}.location_iid",
        "cell_lte": "JOIN cell_lte ON cell_lte.cell_iid = {antenna_table}.cell_iid",
        "cell_nr": "JOIN cell_nr ON cell_nr.cell_iid = {antenna_table}.cell_iid",
        "mu_lte": "JOIN mu_lte ON mu_lte.iid = cell_lte.parent_iid",
        "mu_nr": "JOIN mu_nr ON mu_nr.iid = cell_nr.parent_iid",
    }
    _KNOWN_TABLES = ["cell_lte", "cell_nr", "cell_physical_antenna", "cell_logical_antenna", "location", "mu_lte", "mu_nr"]

    # Generic words to exclude from column-name searches (too common, noisy)
    _GENERIC_TOKENS = frozenset({
        'lte', 'nr', 'cell', 'cells', 'site', 'sites', 'location', 'locations',
        'carrier', 'parameters', 'parameter', 'param', 'config',
        'actual', 'value', 'values', 'data', 'table', 'column', 'name',
        'what', 'show', 'give', 'find', 'list', 'tell', 'know', 'need',
        'want', 'from', 'with', 'that', 'have', 'this', 'which', 'where',
        'many', 'much', 'does', 'will', 'please', 'about', 'into', 'some',
        'each', 'every', 'their', 'there', 'would', 'should', 'could',
        'when', 'them', 'they', 'your', 'just', 'only', 'over', 'than',
        'then', 'been', 'were', 'will', 'here', 'mean', 'means',
        'natural', 'language', 'request', 'generate', 'query', 'select',
        'update', 'change', 'modify', 'enable', 'disable', 'check',
        'power', 'technology', 'both',
    })

    def _extract_search_fragments(self, task: str = "", bad_col: str = "") -> list:
        """Extract lowercase search fragments for DB column lookup via LIKE.

        - Task: alpha tokens >=4 chars, not generic
        - Bad column: underscore-split parts >=3 chars
        - Long tokens (>=8 chars) also contribute first-5 and last-5 substrings
          so matches survive underscore variations once column names are normalized.
        - Sanitized to [a-z0-9] only; capped at 10 fragments.
        """
        raw = []

        if bad_col:
            for part in bad_col.lower().split('_'):
                if len(part) >= 3:
                    raw.append(part)

        if task:
            for word in re.findall(r'[a-zA-Z]{4,}', task):
                wl = word.lower()
                if wl not in self._GENERIC_TOKENS:
                    raw.append(wl)

        augmented = list(raw)
        for t in raw:
            if len(t) >= 8:
                augmented.append(t[:5])
                augmented.append(t[-5:])

        seen = set()
        out = []
        for t in augmented:
            clean = re.sub(r'[^a-z0-9]', '', t.lower())
            if len(clean) < 3 or clean in self._GENERIC_TOKENS or clean in seen:
                continue
            seen.add(clean)
            out.append(clean)
        return out[:10]

    async def _prefetch_column_hint(self, task: str, project_name: str, user_email: str) -> str:
        """Pre-search DB schema BEFORE first LLM attempt for columns matching the user's task.

        Only fires when the task contains a distinctive alpha token (>=6 chars, not generic)
        — this catches asks for parameters like 'TTIbundling' or 'adaptivemimothreshold' that
        the prompt template may not enumerate. Short/common asks (tilt, pci, azimuth) are
        already covered by the prompt, so we skip them to avoid noise.

        Returns a hint string to append to the user prompt, or '' if nothing to add.
        """
        distinctive = [
            w.lower() for w in re.findall(r'[a-zA-Z]{6,}', task)
            if w.lower() not in self._GENERIC_TOKENS
        ]
        if not distinctive:
            return ""

        fragments = self._extract_search_fragments(task)
        if not fragments:
            return ""

        try:
            similar = await self._find_similar_columns(fragments, project_name, user_email)
            if similar:
                suggestions = [f"{t}.{c}" for t, c, _ in similar[:8]]
                logger.info(f"[SQL Gen] Upfront column prefetch found: {suggestions}")
                return (
                    f"\n\nIMPORTANT DATABASE HINT: Based on your task, these columns exist "
                    f"in the database and may be what the user is asking about: "
                    f"{', '.join(suggestions)}. "
                    f"If one of these matches the user's intent, use its EXACT column name "
                    f"in the SQL query. Do NOT refuse the task or claim the column is missing "
                    f"if a match is listed here."
                )
        except Exception as e:
            logger.warning(f"[SQL Gen] Upfront column prefetch failed: {e}")
        return ""

    async def _find_similar_columns(self, fragments: list, project_name: str, user_email: str) -> list:
        """Search information_schema for columns matching any fragment.
        Matches against LOWER(REPLACE(column_name, '_', '')) so fragments like
        'ttibundling' hit columns like 'act_tti_bundling'. Returns
        [(table_name, column_name, score), ...] sorted by score desc."""
        if not fragments:
            return []
        norm = "LOWER(REPLACE(column_name, '_', ''))"
        like_clauses = " OR ".join(f"{norm} LIKE '%{f}%'" for f in fragments)
        score_expr = " + ".join(f"(CASE WHEN {norm} LIKE '%{f}%' THEN 1 ELSE 0 END)" for f in fragments)
        query = (
            f"SELECT table_name, column_name, ({score_expr}) AS score "
            f"FROM information_schema.columns "
            f"WHERE table_name IN ({','.join(repr(t) for t in self._KNOWN_TABLES)}) "
            f"AND column_name NOT LIKE 'security_%' "
            f"AND ({like_clauses}) "
            f"ORDER BY score DESC, table_name, column_name "
            f"LIMIT 15"
        )
        result = await self.db_manager.execute_query(project_name, query, user_email=user_email)
        if result['status'] and result['data']:
            return [(row[0], row[1], int(row[2])) for row in result['data']]
        return []

    async def _get_column_hints(self, query: str, errors: list, task: str, project_name: str, user_email: str) -> str:
        """When EXPLAIN fails with 'column X does not exist', find which table actually has it and provide JOIN guidance."""
        error_str = " ".join(errors)
        col_error = re.search(r'column\s+(\w+)\.(\w+)\s+does not exist', error_str, re.IGNORECASE)
        if not col_error:
            return ""
        alias = col_error.group(1)
        bad_col = col_error.group(2)

        # Resolve alias to table name
        target_table = None
        for tbl in self._KNOWN_TABLES:
            pattern = rf'\b{re.escape(tbl)}\b(?:\s+(?:AS\s+)?{re.escape(alias)}\b|\s+WHERE|\s+ON|\s*$)'
            if re.search(pattern, query, re.IGNORECASE) or alias.lower() == tbl.lower():
                target_table = tbl
                break

        try:
            # Step 1: Search ALL tables for the exact column name
            find_col_query = (
                f"SELECT table_name, column_name FROM information_schema.columns "
                f"WHERE table_name IN ({','.join(repr(t) for t in self._KNOWN_TABLES)}) "
                f"AND column_name = '{bad_col}'"
            )
            result = await self.db_manager.execute_query(project_name, find_col_query, user_email=user_email)
            if result['status'] and result['data'] and len(result['data']) > 0:
                found_table = result['data'][0][0]
                # Build JOIN hint
                join_hint = self._TABLE_JOIN_HINTS.get(found_table, "")
                if "{cell_table}" in join_hint:
                    # Detect which cell table is in the query
                    cell_tbl = "cell_lte" if "cell_lte" in query.lower() else "cell_nr" if "cell_nr" in query.lower() else "cell_lte"
                    join_hint = join_hint.replace("{cell_table}", cell_tbl)
                if "{antenna_table}" in join_hint:
                    ant_tbl = "cell_physical_antenna" if "cell_physical_antenna" in query.lower() else "cell_logical_antenna"
                    join_hint = join_hint.replace("{antenna_table}", ant_tbl)
                return (
                    f"\nHint: Column '{bad_col}' does NOT exist in table '{target_table or alias}'. "
                    f"It exists in table '{found_table}'. Use: {join_hint}. "
                    f"Then reference it as {found_table}.{bad_col}"
                )

            # Step 2: Column not found anywhere — multi-fragment fuzzy search using
            # the user's original task + the bad column name.
            fragments = self._extract_search_fragments(task, bad_col)
            similar = await self._find_similar_columns(fragments, project_name, user_email)
            if similar:
                suggestions = [f"{t}.{c}" for t, c, _ in similar[:10]]
                return (
                    f"\nHint: Column '{bad_col}' does not exist in any table. "
                    f"Closest matches in DB (ranked by relevance to your task): {', '.join(suggestions)}. "
                    f"Pick the column that matches the user's intent and use its exact name."
                )

            # Step 3: Nothing similar — show all columns of the target table
            if target_table:
                all_cols_query = (
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name = '{target_table}' AND column_name NOT LIKE 'security_%' "
                    f"ORDER BY ordinal_position"
                )
                result = await self.db_manager.execute_query(project_name, all_cols_query, user_email=user_email)
                if result['status'] and result['data']:
                    cols = [row[0] for row in result['data'][:30]]
                    return f"\nHint: Column '{bad_col}' does not exist in '{target_table}'. Available columns: {', '.join(cols)}"

        except Exception as e:
            logger.warning(f"[SQL Gen] Column hint lookup failed: {e}")
        return f"\nHint: Column '{alias}.{bad_col}' does not exist. Check the table_context for correct column and table names."

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

    #Generate the SQL query With Validation Loop
    async def _generate_sql_query_with_validation_loop(self, task: str, need_latest_data:bool, project_name: str, user_email: str, fuzzy_flag:bool = False, stream_writer=None) -> Tuple[int,SQLQueryResult]:
        if fuzzy_flag:
            system_prompt=SystemMessage(content=FUZZY_PROMPT)
        else:
            system_prompt=SystemMessage(content=self.system_prompt)
        llm=self.llm

        # Upfront column prefetch: if the task names a distinctive parameter not in the prompt,
        # search information_schema and inject matches so the LLM uses real column names.
        upfront_hint = ""
        if not fuzzy_flag:
            upfront_hint = await self._prefetch_column_hint(task, project_name, user_email)
        

        user_prompt=HumanMessage(content=task + f" and for this task your `need_latest_data` parameter is {need_latest_data}" + upfront_hint)
        chat_history=[system_prompt,user_prompt]
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
                    if retry_count == 0:
                        db_hint = await self._search_db_for_column(
                            response.error_reason or "", task, project_name, user_email
                        )
                        if db_hint:
                            logger.info(f"[SQL Gen] Found columns in DB, retrying with hint")
                            chat_history.extend([
                                AIMessage(content=raw_content),
                                HumanMessage(content=f"{db_hint}")
                            ])
                            retry_count += 1
                            continue
                    return (retry_count,response)
                logger.info(f"[SQL Gen] Generated query: {response.query}")
                validation_result=await self._validate_sql_query(response.query, project_name, user_email)
                if not validation_result.is_valid:
                    logger.warning(f"[SQL Gen] Validation failed. Errors: {validation_result.errors}")
                    column_hints = await self._get_column_hints(response.query, validation_result.errors, task, project_name, user_email)
                    retry_msg = f"Error: {validation_result.errors}. {column_hints} Please generate the SQL query again resolving the errors."
                    chat_history.extend([
                        AIMessage(content=raw_content),
                        HumanMessage(content=retry_msg)
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



    async def generate_and_execute_sql_query(self, task: str, need_latest_data: bool, project_name: str, user_email: str, fuzzy_flag: bool = False, stream_writer=None) -> Tuple[SQLQueryExecutionResult, str]:
        # 1. Generate and Run the query
        retry_count, response = await self._generate_sql_query_with_validation_loop(task, need_latest_data, project_name, user_email, fuzzy_flag, stream_writer)
        
        if not response.success:
            return SQLQueryExecutionResult(status=False, data=None, error=response.error_reason, columns=None, count=0, fuzzy_flag=fuzzy_flag), response.query

        result = await self._execute_sql_query(response.query, project_name, user_email, fuzzy_flag)

        logger.info(f"[EDS-DEBUG] Query execution result: count={result.count}, status={result.status}, fuzzy_flag={fuzzy_flag}, error={result.error}")

        # 2. Logic Gate: Should we trigger Fuzzy Search?
        if (result.count == 0 and result.status and not fuzzy_flag):
            logger.info(f"[EDS-DEBUG] 0 rows returned. Checking fuzzy trigger conditions...")
            query_lower = response.query.lower()
            if "where" in query_lower:
                where_clause = query_lower.split("where")[-1]

                string_literal_filter = r"(?:lower\s*\(.*?\)\s*=\s*lower\s*\(\s*'[^']+'\s*\))|(?:=\s*'[^']+')"

                if re.search(string_literal_filter, where_clause):
                    logger.info("[EDS-DEBUG] String literal found in WHERE -> TRIGGERING fuzzy search")
                    fuzzy_task = f"User Question: {task}\nOriginal SQL Query: {response.query}"
                    return await self.generate_and_execute_sql_query(fuzzy_task, need_latest_data, project_name, user_email, fuzzy_flag=True, stream_writer=stream_writer)
                else:
                    logger.info("[EDS-DEBUG] No string literal in WHERE -> NOT triggering fuzzy")
            else:
                logger.info("[EDS-DEBUG] No WHERE clause found -> NOT triggering fuzzy")
        elif result.count == 0 and not result.status:
            logger.info(f"[EDS-DEBUG] Query FAILED (status=False): {result.error}")
        elif result.count == 0 and fuzzy_flag:
            logger.info("[EDS-DEBUG] 0 rows returned but already in fuzzy mode -> returning empty")
        else:
            logger.info(f"[EDS-DEBUG] Query returned {result.count} rows -> proceeding normally")

        return result, response.query
       



#factory method to create the tool
def create_asset_db_rag_tool(db_manager:Optional[DynamicAsyncDatabaseManager] = None):
    asset_db_rag_tool_instance=AssetDBRAGTool(db_manager)

    class AssetDbRagArgs(BaseModel):
        task: str = Field(...,description="Natural language description of the data to retrieve. Be specific about entity types (cells, sites), filters, and which columns to include. When querying for a downstream tool (audit/discrepancy/fixer), explicitly request the identifier column (e.g. cell iid, site iid).")
        need_latest_data: bool = Field(
            ...,
            description="True: query only the most recent import batch (use for current state questions — this is the common case). False: query historical data across all imports (use only when user explicitly asks for 'previous', 'historical', or 'old' data).",
        )


    # **Strict Rules:**
        #-   always pass single, specific task to it that can be resolved by one sql query, not huge composite task that cannot be resolved by one sql query.
        #-   if there is a huge task that cannot be resolved by one sql query then break it down into smaller tasks and pass them to the tool one after another.
    #  @tool(name="asset_db_rag_tool", return_direct=True, parse_docstring=True)
    #  return_direct=True is a important parameter to return result directly without going to the LLM for reasonning
    @tool("asset_db_rag_tool", args_schema=AssetDbRagArgs, parse_docstring=False)
    async def asset_db_rag_tool(task: str, need_latest_data:bool, project_name: Annotated[str, InjectedState("project_name")], user_email: Annotated[str, InjectedToolArg]) -> ToolOutput:
        """
        Generate and execute SQL queries to retrieve network data from the Asset Database.
        This tool is strictly READ-ONLY.
        
        ## How the tool works [Summary]
        This tool converts natural language requests into executable SQL queries.
        1.  It uses an internal LLM to translate the user's `task` into a SQL `SELECT` statement.
        2.  It validates the SQL for safety (read-only) and syntax using `EXPLAIN` and regex checks.
        3.  It returns the results in a structured format (rows/columns) and a Markdown table.
        4.  If task is not successful or out of scope for the tool, it returns the error message.
        -  detailed information about the tool and how it works is available at [Asset DB RAG Documentation](https://www.notion.so/bimandas/What-Next-AANA-2c3bb91a7a9780bd837fe70264ebf791)

        ## Data this tool can fetch
        - Cell parameters
        - Site parameters
        - Antenna configurations parameters
        - Location parameters
        - MU parameters
        - Cell logical antenna parameters
        - Cell physical antenna parameters
        - metadata about the asset database (when it is last updated, ...)
        
        ## Capabilities
        -   **Querying**: Retrieve cell parameters, site locations, antenna configurations, and other network entities.
        -   **Filtering**: Supports complex filtering (e.g., "Find 5G cells in London with azimuth > 100").
        -   **Joins**: Can join related tables (e.g., Cell -> Location -> Site) to answer cross-domain questions.

        ## When to use
        -   When the user asks for specific data points (e.g., "What is the tilt of cell X?").
        -   When the user wants a list of entities matching criteria (e.g., "List all sites in region Y").
        -   Some times it is used to resolve arguments for the downstream tools (e.g., `audit_engine_tool`, `discrepancy_engine_tool`, `run_eds_fixer_tool`) if needed.
        -   **NOT** for modification. This tool is strictly READ-ONLY.
        -   **NOT** for complex audits (use `audit_engine_tool`).
        -   **NOT** for discrepancy analysis (use `discrepancy_engine_tool`).
        """
        logger.info(f"[ASSET DB RAG TOOL] user email: {user_email}")
        stream_writer = get_stream_writer()
        result, query_executed = await asset_db_rag_tool_instance.generate_and_execute_sql_query(task, need_latest_data, project_name, user_email=user_email, stream_writer=stream_writer)

        logger.info(f"Asset DB RAG Tool data count: {result.count}")

        # Transform SQLQueryExecutionResult to ToolOutput
        result_dict = result.model_dump()

        # Reverse-map hashed IIDs back to originals for both LLM and UI
        # Security goal (data at rest hashed in DB) is already achieved;
        # LLM needs real names at runtime to generate meaningful responses.
        if IID_HASHING_ENABLED and result_dict.get("data"):
            hashes = collect_hashes_from_rows(result_dict["data"])
            if hashes:
                async with global_db_manager.connection(project_name) as conn:
                    rmap = await reverse_map_hashes(conn, hashes)
                if rmap:
                    apply_reverse_map(result_dict["data"], rmap)

        columns, rows, markdown_data = await DynamicAsyncDatabaseManager.get_formatted_result(result_dict)
        data={
            "columns": columns,
            "rows": rows,
            }


        if result.fuzzy_flag:
            data["fuzzy_notice"]=FUZZY_IDENTIFIER
        # Convert datetime objects to strings before JSON serialization
        data = _convert_datetime_to_str(data)
        data=json.dumps(data)
        data=f"**Total rows returned: {result.count}**\n\n**Query Executed:**\n```sql\n{query_executed}\n```\n\n **Data returned:**\n{data}"

        #logger.info(f"Asset DB RAG Tool data: {data}")
        markdown_data=f"**Query Result:**\n{markdown_data}\n\n**Query Executed:**\n```sql\n{query_executed}\n```\n"

        # logger.info(f"Asset DB RAG Tool markdown data: {markdown_data}")
        # logger.info(f"Asset DB RAG Tool result: {result.model_dump()}")
        logger.info(f"Asset DB RAG Tool fuzzy flag: {result.fuzzy_flag}")
        # logger.info(f"Asset DB RAG Tool query executed: {query_executed}")

        return ToolOutput(
            status=result.status,
            data=data,
            is_summary_available=False,
            md_data=markdown_data,
            errors=result.error,
        )

    #return the tool
    return asset_db_rag_tool