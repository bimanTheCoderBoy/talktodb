from agent.utils.create_handoff import create_handoff_tool
from agent.constants.agent_details import agents_details

transfer_to_coverage_agent = create_handoff_tool(agents_details[1]["name"], agents_details[1]["description"], goto_node="coverage_input_handler_node")