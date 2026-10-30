export const TOOL_DISPLAY_NAME_BY_NAME = {
  get_database_table: "Database Table",
  get_database_column: "Database Column",
  get_database_relation: "Database Relation",
  search_database_context: "Database Context Search",
  run_db_query: "Database Query",
  activate_skill: "Activate Skill",
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
