# sandbox.py v2.1.0
# Location: nova/core/sandbox.py
# Purpose: Docker + gVisor isolated execution for LLM-generated code
#
# SECURITY MODEL:
#   This module is ONE layer of a defense-in-depth strategy.
#   - Preflight string check: fast-reject only, NOT a security boundary
#   - AST Shield (separate module): semantic analysis, authoritative code check
#   - Docker + gVisor: kernel-level isolation — the REAL security boundary
#   - Network/FS restrictions: blast-radius reduction if other layers fail
#
# If you are reading this and thinking "the string check protects us" — STOP.
# It does not. The container protects us. The string check just rejects
# obvious nonsense before we spend 2s spinning up Docker.

import subprocess
import tempfile
import shutil
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


# === CONFIGURATION ===

# Pinned by digest would be better (see TODO). Unpinned means the image can
# change under us when upstream rebuilds. Acceptable for local dev; not for prod.
# TODO: pin to python:3.11-slim@sha256:<digest>
DOCKER_IMAGE = "python:3.11-slim"

DOCKER_RUNTIME = "runsc"          # gVisor — user-space kernel, sandboxes syscalls
EXECUTION_TIMEOUT = 30             # seconds; wall-clock, not CPU time
OUTPUT_LIMIT_BYTES = 3000          # stdout truncation threshold
ERROR_LIMIT_BYTES = 500            # stderr truncation threshold
MAX_ARTIFACT_SIZE_MB = 10          # per-file artifact size cap (defense against disk fill)


# === STATUS ENUM ===
# Using (str, Enum) so values serialize as strings in JSON/logs,
# while still getting typo-safety and autocomplete.

class SandboxStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"                # code ran but exited non-zero
    BLOCKED = "blocked"            # preflight rejected
    SYNTAX_ERROR = "syntax_error"
    TIMEOUT = "timeout"
    DOCKER_MISSING = "docker_missing"
    EXCEPTION = "exception"        # unexpected host-side error


# === RESULT DATACLASS ===
# Why a dataclass instead of a dict?
#   1. Typos fail loudly (result.outpu -> AttributeError)
#   2. IDE autocomplete works
#   3. The schema is self-documenting
#   4. Adding a field is a one-line change in one place

@dataclass
class SandboxResult:
    status: SandboxStatus
    output: Optional[str] = None
    error: Optional[str] = None
    return_code: Optional[int] = None
    # default_factory=list avoids the classic "mutable default" bug:
    # if we wrote `artifacts: list = []`, ALL instances would share ONE list.
    artifacts: list[str] = field(default_factory=list)
    truncated_stdout: bool = False
    truncated_stderr: bool = False
    duration_sec: float = 0.0


# === PREFLIGHT (NOT A SECURITY CONTROL) ===

# Modules whose mere presence suggests the code is unsafe or useless in sandbox.
# This is a fast-reject for obvious cases, NOT defense. A determined caller can
# trivially bypass with string tricks (getattr, __import__, exec, encoding, etc.).
# The container is what actually protects us.
_SUSPICIOUS_MODULES = frozenset({
    'os', 'sys', 'subprocess', 'shutil',
    'socket', 'requests', 'urllib', 'http',
    'pickle', 'shelve',
    'ctypes', 'multiprocessing',
})

_SUSPICIOUS_BUILTINS = frozenset({
    'eval', 'exec', '__import__',
})


def _preflight_check(code: str) -> tuple[bool, str]:
    """
    Fast-reject obviously suspicious code BEFORE spending 2s on Docker startup.

    This is a PERFORMANCE optimization, not a security boundary.
    The AST Shield and the container do the real work.

    Returns: (is_clean, reason)
    """
    for module in _SUSPICIOUS_MODULES:
        # We check a couple of obvious surface patterns. Not exhaustive.
        if f'import {module}' in code or f'from {module}' in code:
            return False, f"suspicious module reference: {module}"

    for builtin in _SUSPICIOUS_BUILTINS:
        if f'{builtin}(' in code:
            return False, f"suspicious builtin call: {builtin}()"

    return True, "ok"


# === ARTIFACT COLLECTION ===

def _collect_artifacts(workdir: Path, exclude: set[str]) -> list[str]:
    """
    List files in workdir that look like artifacts (not our wrapper files).

    Safety checks applied:
      - regular files only (no symlinks — defense against symlink tricks)
      - size-capped (defense against disk-fill attacks)
    """
    artifacts = []
    for f in workdir.iterdir():
        if f.name in exclude:
            continue
        # is_file() with follow_symlinks=False would be ideal, but Path.is_file()
        # follows symlinks. Use is_symlink() as the explicit guard.
        if f.is_symlink():
            continue
        if not f.is_file():
            continue
        try:
            size_mb = f.stat().st_size / (1024 * 1024)
            if size_mb > MAX_ARTIFACT_SIZE_MB:
                continue
        except OSError:
            continue
        artifacts.append(f.name)
    return artifacts


# === MAIN ENTRYPOINT ===

def execute_sandboxed(code: str, timeout: Optional[int] = None) -> SandboxResult:
    """
    Execute untrusted Python code in a Docker + gVisor sandbox.

    Design principles:
      1. Per-call isolation: each execution gets a fresh temp directory.
         This means concurrent calls don't collide, and there's no shared
         state to leak between runs.
      2. Guaranteed cleanup: try/finally ensures temp dirs are removed
         even if Docker crashes, we get interrupted, etc.
      3. Structured result: returns a typed SandboxResult, not a dict.
      4. Defense in depth: layered controls, none relied upon alone.
    """
    timeout = timeout or EXECUTION_TIMEOUT
    start_time = time.monotonic()  # monotonic = not affected by clock changes

    # ---- Layer 1: Preflight (performance, not security) ----
    clean, reason = _preflight_check(code)
    if not clean:
        return SandboxResult(
            status=SandboxStatus.BLOCKED,
            error=f"preflight: {reason}",
            duration_sec=time.monotonic() - start_time,
        )

    # ---- Layer 2: Syntax check (saves a Docker startup on broken code) ----
    # Note: compile() parses but does not execute. It's safe to run on
    # untrusted strings. The only risk is parser DoS via pathological input,
    # which is a low-severity concern for local use.
    try:
        compile(code, '<sandbox>', 'exec')
    except SyntaxError as e:
        return SandboxResult(
            status=SandboxStatus.SYNTAX_ERROR,
            error=f"line {e.lineno}: {e.msg}",
            duration_sec=time.monotonic() - start_time,
        )

    # ---- Layer 3: Per-call isolated workdir ----
    # mkdtemp() creates a uniquely-named directory. No collision with
    # concurrent calls. No leftover state from prior runs.
    workdir = Path(tempfile.mkdtemp(prefix="nova_sandbox_"))

    try:
        # Write user code. We wrap it minimally to ensure UTF-8 stdout.
        code_file = workdir / "user_code.py"
        wrapped = (
            "import sys, io\n"
            "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')\n"
            "sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')\n"
            "# --- user code below (line offset: 3) ---\n"
            + code
        )
        code_file.write_text(wrapped, encoding='utf-8')

        # ---- Layer 4: The real security boundary — the container ----
        # Every flag below is deliberate. If you don't know why one is there,
        # look it up before removing it.
        docker_cmd = [
            "docker", "run",
            "--rm",                                   # auto-delete container on exit
            f"--runtime={DOCKER_RUNTIME}",            # gVisor user-space kernel
            "--network=none",                         # no network access at all
            "--memory=512m",                          # RAM cap; OOM-kill if exceeded
            "--cpus=1",                               # CPU cap
            "--pids-limit=64",                        # prevent fork bombs
            "--read-only",                            # root FS is read-only
            "--tmpfs", "/tmp:size=64m",               # writable /tmp, size-capped
            "--user=65534:65534",                     # run as 'nobody', not root
            "--cap-drop=ALL",                         # drop all Linux capabilities
            "--security-opt=no-new-privileges",       # block setuid/setgid escalation
            "-v", f"{workdir.resolve()}:/sandbox:rw", # our workdir is the only writable mount
            "-w", "/sandbox",
            DOCKER_IMAGE,
            "python", "/sandbox/user_code.py",
        ]

        # ---- Execute ----
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace',
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                status=SandboxStatus.TIMEOUT,
                error=f"execution exceeded {timeout}s",
                duration_sec=time.monotonic() - start_time,
            )
        except FileNotFoundError:
            return SandboxResult(
                status=SandboxStatus.DOCKER_MISSING,
                error="docker not on PATH; is dockerd running?",
                duration_sec=time.monotonic() - start_time,
            )
        except Exception as e:  # deliberately broad: host-side surprises
            return SandboxResult(
                status=SandboxStatus.EXCEPTION,
                error=f"host-side: {type(e).__name__}: {e}",
                duration_sec=time.monotonic() - start_time,
            )

        # ---- Process output ----
        stdout_full = proc.stdout or ""
        stderr_full = proc.stderr or ""
        stdout_trunc = len(stdout_full) > OUTPUT_LIMIT_BYTES
        stderr_trunc = len(stderr_full) > ERROR_LIMIT_BYTES

        artifacts = _collect_artifacts(workdir, exclude={"user_code.py"})

        # Note: we collect artifact NAMES, not contents. The caller can read
        # them from workdir if needed — but workdir is deleted in finally!
        # For v2.1 that's acceptable; in a later version, move artifacts to
        # a persistent location before cleanup if Reflector needs them.
        # TODO v2.2: persistent artifact store

        return SandboxResult(
            status=SandboxStatus.SUCCESS if proc.returncode == 0 else SandboxStatus.ERROR,
            output=stdout_full[:OUTPUT_LIMIT_BYTES] if stdout_full else None,
            error=stderr_full[:ERROR_LIMIT_BYTES] if stderr_full else None,
            return_code=proc.returncode,
            artifacts=artifacts,
            truncated_stdout=stdout_trunc,
            truncated_stderr=stderr_trunc,
            duration_sec=time.monotonic() - start_time,
        )

    finally:
        # Guaranteed cleanup. Runs even if we returned above, even on exception,
        # even on KeyboardInterrupt. THIS is why try/finally matters.
        shutil.rmtree(workdir, ignore_errors=True)


# === SMOKE TESTS ===
# These are NOT proper tests — they just verify the pipe is connected.
# Real tests go in tests/test_sandbox.py with pytest.

if __name__ == "__main__":
    print("=== Sandbox v2.1.0 smoke tests ===\n")

    cases = [
        ("safe code", "print('hello'); import math; print(math.pi)"),
        ("blocked import", "import os\nos.system('whoami')"),
        ("syntax error", "def broken(:\n    pass"),
        ("timeout", "import time; time.sleep(10)"),
    ]

    for name, code in cases:
        print(f"--- {name} ---")
        r = execute_sandboxed(code, timeout=5)
        print(f"  status:    {r.status.value}")
        print(f"  duration:  {r.duration_sec:.2f}s")
        if r.output:   print(f"  output:    {r.output[:100]!r}")
        if r.error:    print(f"  error:     {r.error[:100]!r}")
        print()

