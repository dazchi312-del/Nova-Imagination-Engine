"""
Nova App Builder - Layer 1 Tools
File I/O and Code Execution for autonomous building
"""

import subprocess
import sys
from pathlib import Path
from nova.core.errors import NovaToolError
from nova.core.logger import session_logger, LogLevel


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
    session_logger.log(f"Listing files in: {directory}", LogLevel.STRUCT)
    
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
            LogLevel.STRUCT,
            {"directory": directory, "count": len(files)}
        )
        return "\n".join(files) if files else "(empty directory)"
    
    except Exception as e:
        raise NovaToolError(f"Error listing directory {directory}: {e}")


# -- Aliases for dispatcher compatibility --
list_directory = list_files
ToolError = NovaToolError


def run_shell(command: str, timeout: int = 30) -> str:
    """Run a shell command and return combined output."""
    import subprocess
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = result.stdout.strip()
    err = result.stderr.strip()
    combined = (out + ("\n" + err if err else "")).strip()
    return combined if combined else "(no output)"


# ── Phase 10: Process Management ──────────────────────────────────────────────

import psutil
import os


def list_processes(sort_by: str = "cpu", limit: int = 20) -> str:
    """
    List running processes sorted by cpu or memory.
    Returns a formatted table string.
    """
    session_logger.log(f"Listing processes (sort={sort_by}, limit={limit})", LogLevel.STRUCT)

    valid_sort = {"cpu": "cpu_percent", "memory": "memory_percent", "pid": "pid", "name": "name"}
    sort_key = valid_sort.get(sort_by.lower(), "cpu_percent")

    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    import time
    time.sleep(0.3)
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            for p in procs:
                if p["pid"] == proc.pid:
                    p["cpu_percent"] = proc.cpu_percent()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(key=lambda x: x.get(sort_key, 0) or 0, reverse=(sort_key not in ("pid", "name")))
    procs = procs[:limit]

    lines = [f"{'PID':>7}  {'CPU%':>6}  {'MEM%':>6}  {'STATUS':<10}  NAME"]
    lines.append("─" * 60)
    for p in procs:
        lines.append(
            f"{p['pid']:>7}  {(p['cpu_percent'] or 0):>6.1f}  "
            f"{(p['memory_percent'] or 0):>6.2f}  {(p['status'] or '?'):<10}  {p['name'] or '?'}"
        )

    return "\n".join(lines)


def kill_process(pid: int, force: bool = False) -> str:
    """
    Kill a process by PID.
    force=False sends SIGTERM, force=True sends SIGKILL.
    Refuses to kill critical system PIDs (1, 4, os.getpid()).
    """
    session_logger.log(f"Kill requested: PID {pid} (force={force})", LogLevel.CODE)

    protected = {1, 4, os.getpid()}
    if pid in protected:
        raise NovaToolError(f"Refusing to kill protected PID {pid}.")

    try:
        proc = psutil.Process(pid)
        name = proc.name()
        if force:
            proc.kill()
            return f"SIGKILL sent to PID {pid} ({name})."
        else:
            proc.terminate()
            return f"SIGTERM sent to PID {pid} ({name}). Use force=True if still running."
    except psutil.NoSuchProcess:
        raise NovaToolError(f"PID {pid} does not exist.")
    except psutil.AccessDenied:
        raise NovaToolError(f"Access denied killing PID {pid}. Try elevated prompt.")


def get_system_stats() -> str:
    """
    Snapshot of CPU, RAM, and disk usage.
    """
    session_logger.log("Fetching system stats", LogLevel.STRUCT)

    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    lines = [
        "── System Snapshot ──────────────────────────",
        f"  CPU Usage    : {cpu:.1f}%",
        f"  RAM Total    : {ram.total / (1024**3):.1f} GB",
        f"  RAM Used     : {ram.used / (1024**3):.1f} GB  ({ram.percent:.1f}%)",
        f"  RAM Free     : {ram.available / (1024**3):.1f} GB",
        f"  Disk Total   : {disk.total / (1024**3):.1f} GB",
        f"  Disk Used    : {disk.used / (1024**3):.1f} GB  ({disk.percent:.1f}%)",
        f"  Disk Free    : {disk.free / (1024**3):.1f} GB",
        "─────────────────────────────────────────────",
    ]
    return "\n".join(lines)
