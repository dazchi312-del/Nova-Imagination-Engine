"""
tools/file_write.py
L2 Tool — Write or append to a file in the workspace safely.
"""

from pathlib import Path

WORKSPACE_ROOT = Path("C:/Users/dazch/nova")
MAX_WRITE_BYTES = 100_000  # 100KB hard cap per write


def file_write(path: str, content: str, mode: str = "write") -> dict:
    """
    Write or append content to a file relative to the Nova workspace.

    Args:
        path:    Relative or absolute path to the target file.
        content: String content to write.
        mode:    "write" (overwrite) or "append".

    Returns:
        dict with keys:
            ok      (bool)  — success flag
            error   (str)   — error message or empty string
            path    (str)   — resolved absolute path
            bytes   (int)   — bytes written
    """
    try:
        if mode not in ("write", "append"):
            return _err(path, f"Invalid mode '{mode}'. Use 'write' or 'append'.")

        encoded = content.encode("utf-8")
        if len(encoded) > MAX_WRITE_BYTES:
            return _err(path, f"Content too large: {len(encoded)} bytes (max {MAX_WRITE_BYTES}).")

        target = Path(path)
        if not target.is_absolute():
            target = WORKSPACE_ROOT / target
        target = target.resolve()

        # Security: must stay inside workspace
        if not str(target).startswith(str(WORKSPACE_ROOT.resolve())):
            return _err(path, "Access denied: path is outside Nova workspace.")

        # Create parent directories if needed
        target.parent.mkdir(parents=True, exist_ok=True)

        write_mode = "a" if mode == "append" else "w"
        with open(target, write_mode, encoding="utf-8") as f:
            f.write(content)

        return {
            "ok":    True,
            "error": "",
            "path":  str(target),
            "bytes": len(encoded),
        }

    except PermissionError:
        return _err(path, "Permission denied.")
    except Exception as e:
        return _err(path, f"Unexpected error: {e}")


def _err(path: str, msg: str) -> dict:
    return {"ok": False, "error": msg, "path": str(path), "bytes": 0}
