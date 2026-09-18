export const TOOL_DISPLAY_NAME_BY_NAME = {
  // Coverage/report tools
  list_coverage_reports: "List of Coverage Reports",
  get_report_data: "Report Data",
  // query_report_data: "Query Report Data",
  get_cell_iids: "Cell IIDs",
  transfer_to_run_coverage_agent: "Coverage Running Agent",
  user_map_approval: "Map Approval",
  ask_human: "User Calrification",
  doc_retrieval_tool: "Document Retrieval",

  

  // DB agent tools
  asset_db_rag_tool: "Asset RAG Search",
  discrepancy_engine_tool: "Discrepancy List",
  audit_engine_tool: "Audit Results",
  update_eds_tool: "EDS Update Results",
  run_eds_fixer_tool: "EDS Fixer Info",
  ask_user_tool: "User Calrification",
};

const titleCaseFromUnderscore = (name) => {
  if (!name) return "";
  return String(name)
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

export const getToolDisplayName = (toolName) => {
  if (!toolName) return "";

  const name = String(toolName);
  if (TOOL_DISPLAY_NAME_BY_NAME[name]) return TOOL_DISPLAY_NAME_BY_NAME[name];

  if (name.startsWith("transfer_to_")) {
    return `Transfer to ${titleCaseFromUnderscore(name.replace("transfer_to_", ""))}`;
  }

  return titleCaseFromUnderscore(name);
};

const CSV_MD_TOOLS = new Set(["asset_db_rag_tool", "discrepancy_engine_tool"]);

export const getAllowedDownloadFiletypesForTool = (toolName) => {
  const name = String(toolName || "");
  return CSV_MD_TOOLS.has(name) ? ["csv", "md"] : ["pdf", "md"];
};

