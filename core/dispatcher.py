from __future__ import annotations

import json
import re
from typing import Any

from core.tools import read_file, write_file, list_directory, run_shell, ToolError


TOOL_SCHEMA = """
When you need to use a tool, respond with ONLY a JSON block in this exact format:
[TOOL]
{
  "tool": "<tool_name>",
  "args": { <arguments> }
}
[/TOOL]

Available tools:
- read_file:       {"tool": "read_file",       "args": {"path": "<filepath>"}}
- write_file:      {"tool": "write_file",       "args": {"path": "<filepath>", "content": "<text>"}}
- list_directory:  {"tool": "list_directory",   "args": {"path": "<dirpath>"}}
- run_shell:       {"tool": "run_shell",         "args": {"command": "<powershell command>"}}

After a tool result is returned, continue your response normally.
If no tool is needed, respond normally without any JSON block.
"""


class DispatchError(Exception):
    """Raised when dispatch parsing or execution fails."""


def extract_tool_call(text: str) -> dict | None:
    pattern = r"\[TOOL\]\s*(.*?)\s*\[/TOOL\]"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    raw = match.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DispatchError(f"Invalid JSON in tool call: {exc}\nRaw: {raw}") from exc


def execute_tool(call: dict) -> str:
    tool_name = call.get("tool", "").strip()
    args = call.get("args", {})

    if not tool_name:
        raise DispatchError("Tool call missing 'tool' field.")

    try:
        if tool_name == "read_file":
            return read_file(args["path"])
        elif tool_name == "write_file":
            return write_file(args["path"], args["content"])
        elif tool_name == "list_directory":
            return list_directory(args.get("path", "."))
        elif tool_name == "run_shell":
            return run_shell(args["command"])
        else:
            raise DispatchError(f"Unknown tool: '{tool_name}'")
    except ToolError as exc:
        raise DispatchError(f"Tool '{tool_name}' failed: {exc}") from exc
    except KeyError as exc:
        raise DispatchError(f"Tool '{tool_name}' missing required arg: {exc}") from exc


def dispatch(nova_output: str) -> tuple[bool, str]:
    """
    Parse Nova output and execute tool if present.
    Returns (tool_was_called: bool, result: str)
    """
    try:
        call = extract_tool_call(nova_output)
    except DispatchError as exc:
        return (True, f"[DISPATCH ERROR] {exc}")

    if call is None:
        return (False, nova_output)

    try:
        result = execute_tool(call)
        return (True, result)
    except DispatchError as exc:
        return (True, f"[TOOL ERROR] {exc}")
