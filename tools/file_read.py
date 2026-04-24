"""
tools/file_read.py
L2 Tool — Read a file from the workspace safely.
"""

from pathlib import Path

WORKSPACE_ROOT = Path("C:/Users/dazch/nova")
MAX_BYTES = 50_000  # 50KB hard cap per read


def file_read(path: str) -> dict:
    """
    Read a file relative to the Nova workspace.

    Args:
        path: Relative or absolute path to the file.

    Returns:
        dict with keys:
            ok      (bool)   — success flag
            content (str)    — file content or empty string
            error   (str)    — error message or empty string
            path    (str)    — resolved absolute path
            size    (int)    — bytes read
    """
    try:
        target = Path(path)

        # Resolve relative paths against workspace root
        if not target.is_absolute():
            target = WORKSPACE_ROOT / target

        target = target.resolve()

        # Security: must stay inside workspace
        if not str(target).startswith(str(WORKSPACE_ROOT.resolve())):
            return _err(path, "Access denied: path is outside Nova workspace.")

        if not target.exists():
            return _err(path, f"File not found: {target}")

        if not target.is_file():
            return _err(path, f"Path is not a file: {target}")

        raw = target.read_bytes()

        # Truncate if over cap
        truncated = False
        if len(raw) > MAX_BYTES:
            raw = raw[:MAX_BYTES]
            truncated = True

        content = raw.decode("utf-8", errors="replace")

        if truncated:
            content += f"\n\n[file_read] WARNING: Output truncated at {MAX_BYTES} bytes."

        return {
            "ok":      True,
            "content": content,
            "error":   "",
            "path":    str(target),
            "size":    len(raw),
        }

    except PermissionError:
        return _err(path, "Permission denied.")
    except Exception as e:
        return _err(path, f"Unexpected error: {e}")


def _err(path: str, msg: str) -> dict:
    return {"ok": False, "content": "", "error": msg, "path": str(path), "size": 0}
