def format_tool_error_ui(tool_name: str, error_content: str, *, maximum_size: int | None = None) -> str:
    """
    Format tool errors for UI display.

    `maximum_size` is used to prevent huge payloads (stack traces, SQL dumps, etc.)
    from making the UI sluggish. If omitted, a reasonable default is used.
    """
    safe_tool_name = tool_name or "tool"
    text = (error_content or "Tool execution failed").strip()

    # Avoid enormous payloads in the UI.
    if maximum_size is None:
        max_len = 20000
    else:
        max_len = max(5000, min(int(maximum_size), 20000))

    truncated = False
    if len(text) > max_len:
        text = text[:max_len]
        truncated = True

    msg = (
        f"### **Calling `{safe_tool_name}` failed**\n\n"
        f"```text\n{text}\n```\n"
    )
    if truncated:
        msg += "\n_(Error details truncated due to length.)_\n"
    return msg

