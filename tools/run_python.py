"""
tools/run_python.py
L2 Tool — Execute a Python code snippet in a sandboxed subprocess.
"""

import subprocess
import sys
import tempfile
import os
from pathlib import Path

TIMEOUT_SECONDS = 15
MAX_OUTPUT_BYTES = 20_000

# Blocked patterns — hard stops before execution
BLOCKED_PATTERNS = [
    "import os",
    "import sys",
    "import subprocess",
    "import shutil",
    "__import__",
    "open(",
    "exec(",
    "eval(",
    "compile(",
    "importlib",
    "ctypes",
    "socket",
]


def run_python(code: str) -> dict:
    """
    Execute a Python snippet safely via subprocess with timeout.

    Args:
        code: Python source string to execute.

    Returns:
        dict with keys:
            ok      (bool)  — True if exit code 0
            stdout  (str)   — captured stdout
            stderr  (str)   — captured stderr
            error   (str)   — tool-level error message
            exit_code (int) — process exit code
    """
    # Pre-execution safety scan
    for pattern in BLOCKED_PATTERNS:
        if pattern in code:
            return _err(f"Blocked: code contains disallowed pattern '{pattern}'.")

    try:
        # Write code to a temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            text=True,
            encoding="utf-8",
        )

        stdout = result.stdout[:MAX_OUTPUT_BYTES]
        stderr = result.stderr[:MAX_OUTPUT_BYTES]

        return {
            "ok":        result.returncode == 0,
            "stdout":    stdout,
            "stderr":    stderr,
            "error":     "",
            "exit_code": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return _err(f"Execution timed out after {TIMEOUT_SECONDS}s.")
    except Exception as e:
        return _err(f"Unexpected error: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _err(msg: str) -> dict:
    return {"ok": False, "stdout": "", "stderr": "", "error": msg, "exit_code": -1}
