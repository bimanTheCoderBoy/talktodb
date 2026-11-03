from typing import Any
import json


def build_interrupt_payload(name: str, args: dict[str, Any], tool_call_id: str) -> dict[str, Any]:
    return {
        "type": "tool_call",
        "content": json.dumps({
        "tool_name": name,
        "tool_args": args,
        "tool_call_id": tool_call_id,
    })}

def frontend_tool_error_json(message: str) -> str:
    return json.dumps({"success": False, "error": message})


def parse_interrupt_result(raw: object) -> tuple[dict[str, object] | None, str | None]:
    if raw is None:
        return None, "Got no result from frontend tool execution."
    if isinstance(raw, dict):
        return raw, None
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None, "Frontend tool returned invalid JSON."
        if not isinstance(parsed, dict):
            return None, "Tool response must be a JSON object."
        return parsed, None
    return None, f"Unexpected frontend tool result type: {type(raw).__name__}"