from __future__ import annotations

import json
import re
from typing import Any

from nova.core.tools import read_file, write_file, list_directory, run_shell, list_processes, kill_process, get_system_stats, ToolError


TOOL_SCHEMA = """
## TOOL USE INSTRUCTIONS — FOLLOW EXACTLY

To call a tool, output ONLY this format with no other text before the closing tag:

[TOOL]
{
  "tool": "<tool_name>",
  "args": { <arguments> }
}
[/TOOL]

CRITICAL RULES:
- Opening tag is exactly: [TOOL]
- Closing tag is exactly: [/TOOL]
- Do NOT use [list_directory] or any other tag variant
- Do NOT hallucinate tool results — wait for [TOOL RESULT] before continuing
- Do NOT wrap in markdown code blocks
- This system runs on WINDOWS. Use relative paths or Windows absolute paths ONLY.
- NEVER use Unix-style paths like /core or /home or /usr
- Correct path examples: "core", "data", "nova.py", "C:\\Users\\dazch\\nova\\core"
- Wrong path examples: "/core", "/data", "/nova.py"

Available tools:
- read_file:       {"tool": "read_file",       "args": {"path": "core\\tools.py"}}
- write_file:      {"tool": "write_file",       "args": {"path": "data\\output.txt", "content": "<text>"}}
- list_directory:  {"tool": "list_directory",   "args": {"path": "core"}}
- run_shell:       {"tool": "run_shell",         "args": {"command": "<powershell command>"}}

After receiving [TOOL RESULT], respond in plain text with the actual result.
If no tool is needed, respond normally.
"""


class DispatchError(Exception):
    """Raised when dispatch parsing or execution fails."""


def extract_tool_call(text: str) -> dict | None:
    # Primary: [TOOL]...[/TOOL]
    pattern = r"\[TOOL\]\s*(.*?)\s*\[/TOOL\]"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        raw = match.group(1).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DispatchError(f"Invalid JSON in tool call: {exc}\nRaw: {raw}") from exc

    # Fallback: bare JSON block containing "tool" key
    json_pattern = r"\{[\s\S]*?\"tool\"\s*:[\s\S]*?\}"
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        raw = match.group(0).strip()
        try:
            data = json.loads(raw)
            if "tool" in data and "args" in data:
                return data
        except json.JSONDecodeError:
            return None

    return None


def _print_dry_run_preview(call: dict) -> None:
    """Print a formatted preview of what would have been executed."""
    tool_name = call.get("tool", "unknown")
    args = call.get("args", {})
    args_formatted = json.dumps(args, indent=4)

    print("\n" + "━" * 45)
    print("[DRY RUN] Tool call intercepted")
    print("━" * 45)
    print(f"  Tool   : {tool_name}")
    print(f"  Args   : {args_formatted}")
    print(f"  Status : NOT executed — dry-run mode active")
    print("━" * 45 + "\n")


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
        elif tool_name == "list_processes":
            return list_processes(sort_by=args.get("sort_by", "cpu"), limit=int(args.get("limit", 20)))
        elif tool_name == "kill_process":
            return kill_process(pid=int(args["pid"]), force=bool(args.get("force", False)))
        elif tool_name == "get_system_stats":
            return get_system_stats()
        else:
            raise DispatchError(f"Unknown tool: '{tool_name}'")
    except ToolError as exc:
        raise DispatchError(f"Tool '{tool_name}' failed: {exc}") from exc
    except KeyError as exc:
        raise DispatchError(f"Tool '{tool_name}' missing required arg: {exc}") from exc


def dispatch(nova_output: str, dry_run: bool = False) -> tuple[bool, str]:
    """
    Parse Nova output and execute tool if present.

    Args:
        nova_output: Raw string output from Nova's model response.
        dry_run:     If True, intercept and preview tool calls without executing.

    Returns:
        (tool_was_called: bool, result: str)
    """
    try:
        call = extract_tool_call(nova_output)
    except DispatchError as exc:
        return (True, f"[DISPATCH ERROR] {exc}")

    if call is None:
        return (False, nova_output)

    # --- DRY RUN: preview and abort ---
    if dry_run:
        _print_dry_run_preview(call)
        return (True, "[DRY RUN] Tool intercepted — not executed.")

    # --- NORMAL: execute ---
    try:
        result = execute_tool(call)
        return (True, result)
    except DispatchError as exc:
        return (True, f"[TOOL ERROR] {exc}")
