import { z } from "zod";
import { FrontendConnectorError } from "./errors.js";
import { validateWithZodSchema } from "./tools/BaseFrontendTool.js";

function isJsonObject(value) {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    value.constructor === Object
  );
}

/** Agent server `build_interrupt_payload` content (snake_case). */
export const toolCallInterruptContentSchema = z.object({
  tool_call_id: z.coerce.string().trim().min(1),
  tool_name: z.string().trim().min(1),
  tool_args: z.record(z.string(), z.unknown()).optional(),
});

function validateToolCallInterruptParts(parsed) {
  const result = validateWithZodSchema(toolCallInterruptContentSchema, parsed);
  if (!result.ok) {
    throw new FrontendConnectorError(result.error);
  }
  return result.value;
}

/**
 * @returns {{ tool_call_id: string, tool_name: string, tool_args?: Record<string, unknown> }}
 */
export function parseToolCallInterruptContent(content) {
  if (content === undefined || content === null) {
    throw new FrontendConnectorError("Frontend tool interrupt had no content.");
  }

  let parsed = content;

  if (typeof content === "string") {
    const trimmed = content.trim();
    if (!trimmed) {
      throw new FrontendConnectorError("Frontend tool interrupt had no content.");
    }
    try {
      parsed = JSON.parse(trimmed);
    } catch {
      throw new FrontendConnectorError("Frontend tool interrupt content is not valid JSON.");
    }
  } else if (!isJsonObject(content)) {
    throw new FrontendConnectorError("Frontend tool interrupt content must be a JSON object.");
  }

  if (!isJsonObject(parsed)) {
    throw new FrontendConnectorError("Frontend tool interrupt content must be a JSON object.");
  }

  return validateToolCallInterruptParts(parsed);
}
