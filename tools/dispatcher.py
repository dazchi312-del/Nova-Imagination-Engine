"""
tools/dispatcher.py
L2 Tool — Detects and routes tool calls embedded in Nova responses.

Tool call syntax Nova must use:
    <<TOOL:tool_name>>{"arg1": "value1", "arg2": "value2"}<<END_TOOL>>

Example:
    <<TOOL:file_read>>{"path": "vault/identity.md"}<<END_TOOL>>
    <<TOOL:file_write>>{"path": "output/notes.md", "content": "hello"}<<END_TOOL>>
    <<TOOL:run_python>>{"code": "print(2 + 2)"}<<END_TOOL>>
    <<TOOL:web_search>>{"query": "Python asyncio tutorial"}<<END_TOOL>>
"""

import re
import json

from .file_read  import file_read
from .file_write import file_write
from .run_python import run_python
from .web_search import web_search

# ── Tool registry ────────────────────────────────────────────────────
TOOL_REGISTRY = {
    "file_read":  file_read,
    "file_write": file_write,
    "run_python": run_python,
    "web_search": web_search,
}

# Regex to detect tool calls in Nova output
_TOOL_PATTERN = re.compile(
    r"<<TOOL:(\w+)>>(.*?)<<END_TOOL>>",
    re.DOTALL
)


def extract_tool_call(text: str) -> tuple[str, dict] | None:
    """
    Find the first tool call in a text string.

    Returns:
        (tool_name, args_dict) if found, else None.
    """
    match = _TOOL_PATTERN.search(text)
    if not match:
        return None

    tool_name = match.group(1).strip()
    raw_args  = match.group(2).strip()

    try:
        args = json.loads(raw_args)
    except json.JSONDecodeError as e:
        return (tool_name, {"_parse_error": str(e), "_raw": raw_args})

    return (tool_name, args)


def dispatch_tool(tool_name: str, args: dict) -> dict:
    """
    Execute a named tool with the given arguments.

    Returns:
        Tool result dict. Always contains at minimum:
            ok    (bool)
            error (str)
    """
    if tool_name not in TOOL_REGISTRY:
        return {
            "ok":    False,
            "error": f"Unknown tool '{tool_name}'. Available: {list(TOOL_REGISTRY.keys())}",
        }

    if "_parse_error" in args:
        return {
            "ok":    False,
            "error": f"Failed to parse tool args: {args['_parse_error']} | raw: {args.get('_raw')}",
        }

    try:
        tool_fn = TOOL_REGISTRY[tool_name]
        return tool_fn(**args)
    except TypeError as e:
        return {
            "ok":    False,
            "error": f"Tool '{tool_name}' called with wrong arguments: {e}",
        }
    except Exception as e:
        return {
            "ok":    False,
            "error": f"Tool '{tool_name}' raised an exception: {e}",
        }


def format_tool_result(tool_name: str, result: dict) -> str:
    """
    Format a tool result as a system message to inject back into Nova context.

    Returns:
        Human-readable string Nova can reason over.
    """
    if not result.get("ok"):
        return f"[Tool: {tool_name}] FAILED — {result.get('error', 'unknown error')}"

    # Tool-specific formatting
    if tool_name == "file_read":
        return (
            f"[Tool: file_read] SUCCESS — {result['path']} ({result['size']} bytes)\n"
            f"--- FILE CONTENT ---\n{result['content']}\n--- END ---"
        )

    if tool_name == "file_write":
        return (
            f"[Tool: file_write] SUCCESS — wrote {result['bytes']} bytes to {result['path']}"
        )

    if tool_name == "run_python":
        parts = [f"[Tool: run_python] exit_code={result['exit_code']}"]
        if result["stdout"]:
            parts.append(f"STDOUT:\n{result['stdout']}")
        if result["stderr"]:
            parts.append(f"STDERR:\n{result['stderr']}")
        return "\n".join(parts)

    if tool_name == "web_search":
        if not result["results"]:
            return f"[Tool: web_search] No results."
        lines = [f"[Tool: web_search] {len(result['results'])} results:"]
        for r in result["results"]:
            lines.append(f"  • {r.get('title','?')} — {r.get('url','?')}")
            if r.get("snippet"):
                lines.append(f"    {r['snippet']}")
        return "\n".join(lines)

    # Generic fallback
    return f"[Tool: {tool_name}] Result: {result}"
