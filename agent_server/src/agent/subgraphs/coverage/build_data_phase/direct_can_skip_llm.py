from langchain_core.messages import HumanMessage, AIMessage
from langgraph.runtime import Runtime
from agent.utils.state import State, ctx_schema_State
from langgraph.types import Command
from agent.subgraphs.coverage.build_data_phase.tools import AssetDBRAGTool
import logging
logger = logging.getLogger(__name__)
import re
SKIP_PATTERN = r"`<cell_iids>`\[(.*?)\]`<\\cell_iids>`"
_tool = AssetDBRAGTool()


async def direct_can_skip_llm(state: State, runtime: Runtime[ctx_schema_State]):
    coverage_message_context=state.coverage_message_context
    logger.info(f"Coverage message context: {coverage_message_context[-1].content}")
    match = re.search(SKIP_PATTERN, coverage_message_context[-1].content)
    iids:list[str]=state.coverage_state.iids or []

    project_name = state.project_name or runtime.context.project_name
    user_email   = state.user_email   or runtime.context.user_email
    if match:
        raw_list_string = match.group(1)
        iids = [item.strip() for item in raw_list_string.split(',') if item.strip()]
        logger.info(f"Found {len(iids) } {raw_list_string} iids in the skip pattern")
    
    can_skip:bool=False
    if len(coverage_message_context)>0 and isinstance(coverage_message_context[-1], HumanMessage) and len(iids) > 0:
        logger.info(f"Validating the exist cells only for the iids: {iids}")
        query, exist_iids = await _tool.validate_and_get_exist_cells_only(iids, project_name, user_email)
        if len(exist_iids) > 0:
            logger.info(f"Found {len(exist_iids)} exist cells directly, Not going to LLM for coverage")
            iids = exist_iids
            can_skip=True
    else:
        logger.info(f"No Cells found directly, Going to LLM for coverage")


    if can_skip and iids:
        #Building fake AI Message with the query
        ai_message = AIMessage(content=f"```sql\n{query}\n```")
        return Command(
            update={
                "coverage_state": {**state.coverage_state.model_dump(), "iids": iids},
                "coverage_message_context": coverage_message_context + [ai_message]
            },
           
            goto="coverage_iids_map_payload_interrupt",
        )
    else:

        return Command(
            update={},
            goto="coverage_get_cell_iids_node"
        )