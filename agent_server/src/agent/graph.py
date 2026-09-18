from langgraph.graph import StateGraph, END
from langgraph.prebuilt import tools_condition
from agent.utils.state import State, ctx_schema_State
from agent.nodes.main_nodes import master_node, tool_node, input_handler_node

# ── Phase 1: Data Building imports ────────────────────────────────────
from agent.subgraphs.coverage.build_data_phase.input_handler_node import (
    input_handler_node as coverage_input_handler_node,
)
from agent.subgraphs.coverage.build_data_phase.get_cell_iids_node import (
    get_cell_iids_node as coverage_get_cell_iids_node,
)
from agent.subgraphs.coverage.build_data_phase.iids_map_payload_interrupt_node import (
    iids_map_payload_interrupt as coverage_iids_map_payload_interrupt,
)
from agent.subgraphs.coverage.build_data_phase.direct_can_skip_llm import (
    direct_can_skip_llm as coverage_direct_can_skip_llm,
)

# ── Phase 2: Tech Pipeline Execution imports ──────────────────────────
from agent.subgraphs.coverage.execution_phase.prep_tech_execution_node import (
    coverage_prep_tech_execution,
)
from agent.subgraphs.coverage.execution_phase.fan_out_nodes import (
    coverage_fan_out_passthrough,
    coverage_fan_out_by_tech,
)
from agent.subgraphs.coverage.execution_phase.run_tech_pipeline_node import (
    coverage_run_tech_pipeline,
)
from agent.subgraphs.coverage.execution_phase.tech_aggregation_node import (
    coverage_tech_aggregation,
)

# ── Phase 3: Results Building imports ─────────────────────────────────
from agent.subgraphs.coverage.results_phase.map_viewer_node import (
    coverage_map_viewer_node,
)
from agent.subgraphs.coverage.results_phase.report_generator_node import (
    coverage_generate_reports_node,
)
from agent.subgraphs.coverage.results_phase.results_join_node import (
    coverage_results_join_node,
)


def tool_condition_wrapper(state: State):
    return tools_condition(state, messages_key="main_message_context")


graph = (
    StateGraph(State, context_schema=ctx_schema_State)

    # ── Master graph nodes ────────────────────────────────────────────
    .add_node("master_agent_node", master_node)
    .add_node("tool_node", tool_node)
    .add_node("input_handler_node", input_handler_node)

    # ── Phase 1: Data Building nodes ─────────────────────────────────
    .add_node("coverage_input_handler_node", coverage_input_handler_node)
    .add_node("coverage_iids_map_payload_interrupt", coverage_iids_map_payload_interrupt)
    .add_node("coverage_get_cell_iids_node", coverage_get_cell_iids_node)
    .add_node("coverage_direct_can_skip_llm", coverage_direct_can_skip_llm)

    # ── Phase 2: Tech Pipeline Execution nodes ────────────────────────
    .add_node("coverage_prep_tech_execution", coverage_prep_tech_execution)
    .add_node("coverage_fan_out_passthrough", coverage_fan_out_passthrough)
    .add_node("coverage_run_tech_pipeline", coverage_run_tech_pipeline)
    .add_node("coverage_tech_aggregation", coverage_tech_aggregation)

    # ── Phase 3: Results Building nodes ───────────────────────────────
    .add_node("coverage_map_viewer_node", coverage_map_viewer_node)
    .add_node("coverage_generate_reports_node", coverage_generate_reports_node)
    .add_node("coverage_results_join_node", coverage_results_join_node)

    # ══════════════════════════════════════════════════════════════════
    # EDGES
    # ══════════════════════════════════════════════════════════════════

    # ── Master graph edges ────────────────────────────────────────────
    .add_edge("__start__", "input_handler_node")
    .add_edge("input_handler_node", "master_agent_node")
    .add_conditional_edges(
        "master_agent_node",
        tool_condition_wrapper,
        {"tools": "tool_node", "__end__": END},
    )

    # ── Phase 1 edges ─────────────────────────────────────────────────
    .add_edge("coverage_input_handler_node", "coverage_direct_can_skip_llm")

    # ── Phase 2 edges ─────────────────────────────────────────────────
    # interrupt → prep (prep routes via Command to fan_out or master)
    .add_edge("coverage_iids_map_payload_interrupt", "coverage_prep_tech_execution")
    # fan_out passthrough → conditional Send per tech
    .add_conditional_edges(
        "coverage_fan_out_passthrough",
        coverage_fan_out_by_tech,
        ["coverage_run_tech_pipeline", "master_agent_node"],
    )
    # all Send branches → aggregation
    .add_edge("coverage_run_tech_pipeline", "coverage_tech_aggregation")
    # aggregation routes via Command to Phase 3 nodes or master

    # ── Phase 3 edges ─────────────────────────────────────────────────
    # map + reports fan-in to join node
    .add_edge("coverage_map_viewer_node", "coverage_results_join_node")
    .add_edge("coverage_generate_reports_node", "coverage_results_join_node")
    # join routes via Command to master_agent_node

    .compile(name="Coverage Agent Graph")
)
