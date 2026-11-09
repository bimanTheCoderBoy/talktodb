import { z } from "zod";
import { BaseFrontendTool } from "./BaseFrontendTool.js";
import { getConnectorBaseUrl } from "../useConnectorPort.js";

/** Mirrors agent_server RunDbQueryInput (Pydantic). */
export const runDbQueryInputSchema = z.object({
  query: z.string().trim().min(1),
  params: z.record(z.string(), z.unknown()).nullable().optional(),
  output_file_path: z.string().nullable().optional(),
});

/** Mirrors agent_server RunDbQueryOutput (Pydantic). */
export const runDbQueryOutputSchema = z.object({
  success: z.boolean(),
  error: z.string().nullable().optional(),
  columns: z.array(z.string()).nullable().optional(),
  rows: z.array(z.array(z.unknown())).nullable().optional(),
  row_count: z.number().nullable().optional(),
});





const TOOL_NAME = "run_db_query";
export class RunDbQueryTool extends BaseFrontendTool {
  constructor() {
    super(TOOL_NAME, runDbQueryOutputSchema, runDbQueryInputSchema);
  }

  async _postConnectorQuery({ query, params, signal }) {
    const url = `${getConnectorBaseUrl()}/query`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        params: params ?? null,
      }),
      signal,
    });
  
    let body;
    const text = await response.text();
    try {
      body = text ? JSON.parse(text) : {};
    } catch {
      throw new Error(
        response.ok
          ? "Connector returned non-JSON."
          : `Connector error (${response.status}): ${text || response.statusText}`,
      );
    }
  
    if (!response.ok) {
      const detail =
        (typeof body?.error === "string" && body.error) ||
        (typeof body?.detail === "string" && body.detail) ||
        text ||
        response.statusText;
      throw new Error(`Connector error (${response.status}): ${detail}`);
    }
  
    return body;
  }

  async execute(toolArgs, signal) {
    const query = toolArgs?.query;

    if (typeof query !== "string" || !query.trim()) {
      return {
        success: false,
        error: "run_db_query requires a non-empty query string.",
        columns: null,
        rows: null,
        row_count: null,
      };
    }

    const params = toolArgs?.params ?? null;

    try {
      const res = await this._postConnectorQuery({
        query: query.trim(),
        params,
        signal,
      });
      return res;
    } catch (err) {
      if (signal?.aborted || (err instanceof Error && err.name === "AbortError")) {
        throw err;
      }
      const message = err instanceof Error ? err.message : String(err);
      return {
        success: false,
        error: message,
        columns: null,
        rows: null,
        row_count: null,
      };
    }
  }
}
