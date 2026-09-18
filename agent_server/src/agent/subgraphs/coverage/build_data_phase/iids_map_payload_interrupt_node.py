import json
import uuid
from datetime import datetime
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from agent.utils.state import (
    State, ctx_schema_State,
    CoverageUrlConfig, ArrayTypeOption, TechParameters, TechOutput,
)
from agent.utils.database import get_map_data_structure_from_iids
from agent.subgraphs.coverage.utils.utils import update_last_tool_message_of_master_graph
from agent.config.coverage_config import CoverageAPIConfig, join_paths


async def iids_map_payload_interrupt(state: State, runtime: Runtime[ctx_schema_State]):
    tool_call_id = str(uuid.uuid4())
    tool_calls = [{"id": tool_call_id, "name": "user_map_approval", "args": {"iids": "selected cells by Agent"}, "type": "tool_call"}]
    ai_message = AIMessage(content="", tool_calls=tool_calls, name="user_map_approval")

    project_name = state.project_name
    try:
        user_email = runtime.context.user_email
        map_data = await get_map_data_structure_from_iids(project_name, state.coverage_state.iids or [], user_email)
    except Exception as e:
        error_msg = str(e)
        updated_main_context = update_last_tool_message_of_master_graph(state.main_message_context, error_msg)
        return {
            "main_message_context": updated_main_context,
            "coverage_state": {"user_approved": False},
        }

    has_lte = any(
        cell.get("technology") in ("LTE", "lte")
        for site in map_data for cell in site.get("cells", [])
    )
    has_nr = any(
        cell.get("technology") in ("NR", "nr", "5G")
        for site in map_data for cell in site.get("cells", [])
    )

    parameters = {}
    if has_lte:
        parameters["lte"] = {
            "arrayTypes": [
                {"value": "LTE_Best_RSRP", "label": "Best RSRP LTE", "isSelected": True},
                # {"value": "LTE_BestServer_RSRP", "label": "Best Server RSRP LTE", "isSelected": False},
                # {"value": "LTE_DL_Loss", "label": "Downlink Path Loss LTE", "isSelected": False},
            ]
        }
    if has_nr:
        parameters["nr"] = {
            "arrayTypes": [
                {"value": "FiveG_Best_RSRP", "label": "Best SS-RSRP 5G", "isSelected": True},
                # {"value": "FiveG_BestServer_RSRP", "label": "Best SS-RSRP Server 5G", "isSelected": False},
                {"value": "FiveG_CSI_RSRP", "label": "CSI-RSRP 5G", "isSelected": False},
                # {"value": "FiveG_PDSCH_PPRE", "label": "PDSCH Power per RE 5G", "isSelected": False},
                # {"value": "FiveG_DL_Loss_Ctrl", "label": "DL Path Loss (Control) 5G", "isSelected": False},
                # {"value": "FiveG_DL_Loss_Traffic", "label": "DL Path Loss (Traffic) 5G", "isSelected": False},
                # {"value": "FiveG_SSB_Index", "label": "SSB Beam Index 5G", "isSelected": False},
                # {"value": "FiveG_DL_BeamIndex_Traffic", "label": "DL Beam Index (Traffic) 5G", "isSelected": False},
            ]
        }

    time_stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    config = CoverageAPIConfig()
    output_name = config.payload_output_name

    output = {}
    if has_lte:
        output["lte"] = {
            "path": join_paths(config.payload_default_output_location, f"{time_stamp}_lte"),
            "name": output_name,
        }
    if has_nr:
        output["nr"] = {
            "path": join_paths(config.payload_default_output_location, f"{time_stamp}_nr"),
            "name": output_name,
        }

    url_parameter_settings = {}
    if has_lte:
        url_parameter_settings["lte"] = {
            "technology": "LTE",
            "resolution": "50",
            "mode": "Composite",
            "terminal": "Multi-Tech Default",
        }
    if has_nr:
        url_parameter_settings["nr"] = {
            "technology": "FiveG",
            "resolution": "50",
            "mode": "Composite",
            "terminal": "Multi-Tech Default",
        }

    payload = {
        "map_data": map_data,
        "parameters": parameters,
        "output": output,
        "url_parameter_settings": url_parameter_settings,
    }

    result = interrupt({"type": "VIEW_MAP_DATA", "content": json.dumps(payload, indent=4)})
    result = json.loads(result)

    if result.get("success", True):
        cells = result.get("cells", [])
        boundaries = result.get("boundaries", [])
        params_raw = result.get("parameters", {})
        url_settings_raw = result.get("url_parameter_settings", {})
        output_raw = result.get("output", {})

        tool_message = ToolMessage(
            content=f"User has successfully approved {len(cells)} cells",
            tool_call_id=tool_call_id,
            name="user_map_approval",
        )

        built_params = {}
        for tech_key in ("lte", "nr"):
            tp = params_raw.get(tech_key)
            if tp and tp.get("arrayTypes"):
                built_params[tech_key] = TechParameters(
                    arrayTypes=[ArrayTypeOption(**at) for at in tp["arrayTypes"]]
                )

        built_output = {}
        for tech_key in ("lte", "nr"):
            to = output_raw.get(tech_key)
            if to:
                built_output[tech_key] = TechOutput(**to)

        built_url = {}
        for tech_key in ("lte", "nr"):
            us = url_settings_raw.get(tech_key)
            if us:
                built_url[tech_key] = CoverageUrlConfig(**{k: v for k, v in us.items() if k in CoverageUrlConfig.model_fields})

        return {
            "coverage_state": {
                "iids": cells,
                "boundaries": boundaries,
                "parameters": {k: v.model_dump() for k, v in built_params.items()},
                "output": {k: v.model_dump() for k, v in built_output.items()},
                "url_parameter_settings": {k: v.model_dump() for k, v in built_url.items()},
                "user_approved": True,
            },
            "messages": [ai_message, tool_message],
        }
    else:
        tool_message = ToolMessage(
            content="User has rejected the map data",
            tool_call_id=tool_call_id,
            name="user_map_approval",
        )
        main_message_update_text = "User has Terminated the Coverage Agent Workflow.So Coverage cannot be run. Notify the user about the termination."
        updated_main_context = update_last_tool_message_of_master_graph(state.main_message_context, main_message_update_text)
        return {
            "coverage_state": {"user_approved": False},
            "messages": [ai_message, tool_message],
            "main_message_context": updated_main_context,
            # "coverage_message_context_clean_flag": True,
        }
