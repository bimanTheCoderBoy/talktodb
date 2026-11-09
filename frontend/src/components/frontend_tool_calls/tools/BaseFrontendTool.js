import { z } from "zod";


export function validateWithZodSchema(schema, data) {
  const result = schema.safeParse(data);
  if (result.success) {
    return { ok: true, value: result.data };
  }
  const message =
    result.error.issues.map((issue) => issue.message).join(" ") || "Tool output validation failed.";
  return { ok: false, error: message };
}

/**
 * Base client-side tool (Pydantic-style via Zod). Pass tool name and a Zod output schema;
 * validateOutput uses schema.safeParse like response_model validation on the agent server.
 */
export class BaseFrontendTool {
 
  constructor(toolName, outputSchema, inputSchema) {
    if (!toolName?.trim()) {
      throw new Error("BaseFrontendTool requires a tool name.");
    }
    if (!outputSchema || typeof outputSchema.safeParse !== "function") {
      throw new Error("BaseFrontendTool requires a Zod schema (outputSchema.safeParse).");
    }
    if (!inputSchema || typeof inputSchema.safeParse !== "function") {
      throw new Error("BaseFrontendTool requires a Zod schema (inputSchema.safeParse).");
    }
    this.toolName = toolName.trim();
    this.outputSchema = outputSchema;
    this.inputSchema = inputSchema;
  }


  async execute(_toolArgs, _signal) {
    throw new Error(`${this.toolName}: execute() is not implemented.`);
  }

  validateInput(data) {
    return validateWithZodSchema(this.inputSchema, data);
  }

  validateOutput(data) {
    return validateWithZodSchema(this.outputSchema, data);
  }
}
