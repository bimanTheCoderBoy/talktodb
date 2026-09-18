import logging
import re
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from langgraph.types import Command, StreamWriter, interrupt

from agent.utils.state import State, ctx_schema_State
from agent.subgraphs.coverage.build_data_phase.tools import AssetDBRAGTool
from agent.subgraphs.coverage.utils.utils import update_last_tool_message_of_master_graph

logger = logging.getLogger(__name__)

_tool = AssetDBRAGTool()

FAILURE_MESSAGE = "Could not find matching cells for the given conditions. Please try again with different parameters."


def _failure_return(state: State, error_message:str=FAILURE_MESSAGE) -> Command:
    return Command(
        update={
            "coverage_state": {**state.coverage_state.model_dump(), "iids": []},
            "messages": [AIMessage(content=error_message, name="master_agent")],
            "coverage_message_context": state.coverage_message_context + [AIMessage(content=error_message, name="coverage_sql_agent")],
            "main_message_context": update_last_tool_message_of_master_graph(state.main_message_context, error_message) +[AIMessage(content=error_message, name="coverage_sql_agent")]
        },
        goto="__end__",
    )


# def _detect_tech_preference(text: str) -> Optional[str]:
#     """Return 'nr', 'lte', 'both', or None if no clear preference found."""
#     t = text.lower()
#     has_nr   = bool(re.search(r'\b(nr|5g|new.?radio|fiveg)\b', t))
#     has_lte  = bool(re.search(r'\b(lte|4g)\b', t))
#     has_both = bool(re.search(r'\b(both|all)\b', t))

#     if has_both or (has_nr and has_lte):
#         return 'both'
#     if has_nr:
#         return 'nr'
#     if has_lte:
#         return 'lte'
#     return None

async def get_cell_iids_node(state: State, runtime: Runtime[ctx_schema_State]):
    cov = state.coverage_state
    stream_writer: StreamWriter = get_stream_writer()

    if cov.iids is not None and len(cov.iids) > 0:
        ai_message = AIMessage(content=f"Successfully retrieved {len(cov.iids)} cells")
        return {"coverage_message_context": state.coverage_message_context + [ai_message]}

  

    if not state.coverage_message_context or not state.coverage_message_context[-1].content.strip():
        stream_writer({"step": "1/1", "status": "failed", "message": "No task provided for cell IID discovery."})
        return _failure_return(state, "No task provided for cell IID discovery.")

    project_name = state.project_name or runtime.context.project_name
    user_email   = state.user_email   or runtime.context.user_email

    # ── Phase 1: resolve IIDs (all DB work in one try/except) ─────────────────
    iids: List[str] = []
    query: str = ""
    try:
        stream_writer({"step": "1/1", "status": "in_progress", "message": "Querying database for matching cells..."})

        result, query = await _tool.generate_and_execute_sql_query(
            task=state.coverage_message_context,
            need_latest_data=True,
            project_name=project_name,
            user_email=user_email,
            stream_writer=stream_writer,
        )

        if result.status and result.data:
            for row in result.data:
                iid_value = row.get("iid") or row.get("IID") or row.get("cell_iid")
                if iid_value:
                    iids.append(str(iid_value))
        if not result.status:
            return _failure_return(state, result.error)

        # # Fallback: fetch all project cells when the LLM query returned nothing
        # if not iids:
        #     stream_writer({"step": "1/1", "status": "in_progress",
        #                    "message": "No specific cells matched — fetching all cells for the project..."})
        #     iids = await get_all_cell_ids(project_name, user_email)

        # if not iids:
        #     return _failure_return(state)

        # Segregate by technology to know what's available
        # by_tech  = await segregate_iids_by_technology(project_name, iids, user_email)
        # lte_iids = by_tech.get("lte", [])
        # nr_iids  = by_tech.get("nr",  [])

    except Exception as e:
        error_msg = f"Cell IID resolution error: {str(e)}"
        logger.error(f"[COVERAGE CELL IIDS] {error_msg}", exc_info=True)
        stream_writer({"step": "1/1", "status": "failed", "message": error_msg})
        return _failure_return(state, error_msg)

    # ── Phase 2: technology selection (OUTSIDE try/except — interrupt must propagate) ──
    # tech_pref = _detect_tech_preference(task)

    # if lte_iids and nr_iids and not tech_pref:
    #     # Both technologies present and user hasn't specified — ask via chat interrupt
    #     stream_writer({"step": "1/1", "status": "in_progress",
    #                    "message": f"Found {len(lte_iids)} LTE and {len(nr_iids)} NR cells — asking user for technology preference."})
    #     response = interrupt({
    #         "type": "ASK_HUMAN",
    #         "content": (
    #             f"I found **{len(lte_iids)} LTE (4G)** cells and **{len(nr_iids)} NR (5G)** cells "
    #             f"for project **{project_name}**.\n\n"
    #             "Which technology would you like to run coverage for?\n"
    #             "- Reply **NR** or **5G** → NR only\n"
    #             "- Reply **LTE** or **4G** → LTE only\n"
    #             "- Reply **both** → run both"
    #         ),
    #     })
    #     tech_pref = _detect_tech_preference(str(response))
    #     if not tech_pref:
    #         tech_pref = 'both'  # unclear reply → default to both

    # # Apply technology filter
    # if tech_pref == 'nr':
    #     iids = nr_iids
    # elif tech_pref == 'lte':
    #     iids = lte_iids
    # # 'both' or single-technology: keep iids as-is

    if not iids:
        return _failure_return(state, "No cells found for the given task.")

    logger.info(f"[COVERAGE CELL IIDS] Resolved {len(iids)} cell IIDs ")
    stream_writer({"step": "1/1", "status": "in_progress",
                   "message": f"Resolved {len(iids)} cell IIDs via query: {query}"})

    return Command(
        update={"coverage_state": {**cov.model_dump(), "iids": iids}},
        goto="coverage_iids_map_payload_interrupt",
    )
