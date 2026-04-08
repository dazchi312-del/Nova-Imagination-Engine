"""
Nova App Builder - Layer 1 Tools
File I/O and Code Execution for autonomous building
"""

import subprocess
import sys
from pathlib import Path
from core.errors import NovaToolError
from core.logger import session_logger, LogLevel


def read_file(path: str) -> str:
    """
    Read any file Nova needs to inspect.
    Returns file contents as string.
    """
    session_logger.log(f"Reading file: {path}", LogLevel.CODE)
    
    file_path = Path(path)
    
    if not file_path.exists():
        raise NovaToolError(f"File not found: {path}")
    
    if not file_path.is_file():
        raise NovaToolError(f"Path is not a file: {path}")
    
    try:
        content = file_path.read_text(encoding="utf-8")
        session_logger.log(
            f"Read success: {path}",
            LogLevel.CODE,
            {"path": path, "size_bytes": len(content), "lines": content.count('\n')}
        )
        return content
    
    except PermissionError:
        raise NovaToolError(f"Permission denied reading: {path}")
    except Exception as e:
        raise NovaToolError(f"Unexpected read error on {path}: {e}")


def write_file(path: str, content: str, overwrite: bool = True) -> str:
    """
    Write code files to disk.
    Creates parent directories automatically.
    Returns confirmation string.
    """
    session_logger.log(f"Writing file: {path}", LogLevel.CODE)
    
    file_path = Path(path)
    
    if file_path.exists() and not overwrite:
        raise NovaToolError(f"File exists and overwrite=False: {path}")
    
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        
        session_logger.log(
            f"Write success: {path}",
            LogLevel.CODE,
            {"path": path, "size_bytes": len(content), "lines": content.count('\n')}
        )
        return f"Written: {path} ({len(content)} bytes)"
    
    except PermissionError:
        raise NovaToolError(f"Permission denied writing: {path}")
    except Exception as e:
        raise NovaToolError(f"Unexpected write error on {path}: {e}")


def run_code(code: str, timeout: int = 30) -> dict:
    """
    Execute Python and capture output.
    Returns dict with stdout, stderr, exit_code.
    Nova uses this to self-test what it builds.
    """
    session_logger.log("Executing code block", LogLevel.CODE)
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path.cwd()
        )
        
        outcome = {
            "stdout":    result.stdout.strip(),
            "stderr":    result.stderr.strip(),
            "exit_code": result.returncode,
            "success":   result.returncode == 0
        }
        
        if outcome["success"]:
            session_logger.log(
                "Code execution success",
                LogLevel.CODE,
                {"exit_code": 0, "stdout_preview": outcome["stdout"][:200]}
            )
        else:
            session_logger.log(
                "Code execution failed",
                LogLevel.CODE,
                {"exit_code": result.returncode, "stderr": outcome["stderr"][:200]}
            )
        
        return outcome
    
    except subprocess.TimeoutExpired:
        raise NovaToolError(f"Code execution timed out after {timeout}s")
    except Exception as e:
        raise NovaToolError(f"Unexpected execution error: {e}")


def list_files(directory: str = ".") -> list:
    """
    List all files in a directory recursively.
    Nova uses this to understand project structure.
    """
    session_logger.log(f"Listing files in: {directory}", LogLevel.STRUCTURE)
    
    dir_path = Path(directory)
    
    if not dir_path.exists():
        raise NovaToolError(f"Directory not found: {directory}")
    
    try:
        files = []
        for item in sorted(dir_path.rglob("*")):
            if item.is_file():
                # Skip hidden and cache directories
                parts = item.parts
                if any(p.startswith('.') or p == '__pycache__' for p in parts):
                    continue
                files.append(str(item))
        
        session_logger.log(
            f"Listed {len(files)} files",
            LogLevel.STRUCTURE,
            {"directory": directory, "count": len(files)}
        )
        return files
    
    except Exception as e:
        raise NovaToolError(f"Error listing directory {directory}: {e}")
