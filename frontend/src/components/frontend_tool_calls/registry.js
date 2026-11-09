import { RunDbQueryTool } from "./tools/run_db_query.js";

export const FRONTEND_TOOL_REGISTRY = {
  run_db_query: new RunDbQueryTool(),
};


export function getFrontendTool(toolName) {
  if (!toolName) {
    return null;
  }
  return FRONTEND_TOOL_REGISTRY[toolName.trim()] ?? null;
}
