# sandbox.py v2.2.0
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
import os
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

# Runtime detection: prefer gVisor (runsc), fall back to runc.
# Override via NOVA_SANDBOX_RUNTIME env var for CI/dev flexibility.
def _detect_runtime() -> str:
    override = os.environ.get("NOVA_SANDBOX_RUNTIME")
    if override:
        return override
    if shutil.which("runsc"):
        return "runsc"
    return "runc"

DOCKER_RUNTIME = _detect_runtime()  # gVisor if available, else runc
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
    OOM_KILLED = "oom_killed"
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
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None
    runtime_used: Optional[str] = None
    # default_factory=list avoids the classic "mutable default" bug:
    # if we wrote `artifacts: list = []`, ALL instances would share ONE list.
    artifacts: dict[str, bytes] = field(default_factory=dict)
    truncated_stdout: bool = False
    truncated_stderr: bool = False
    duration_s: float = 0.0
    gpu_enabled: bool = False

    @property
    def returncode(self) -> Optional[int]:
        """Back-compat alias for exit_code (matches subprocess.CompletedProcess)."""
        return self.exit_code

    @property
    def timed_out(self) -> bool:
        """Derived: True if the run hit the timeout wall."""
        return self.status == SandboxStatus.TIMEOUT

    @property
    def oom_killed(self) -> bool:
        """Derived: True if the container was killed for exceeding memory.
        Docker reports OOM kills via exit code 137 (128 + SIGKILL=9)."""
        return self.exit_code == 137


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

def _collect_artifacts(workdir: Path, exclude: set[str]) -> dict[str, bytes]:
    """
    Collect files in workdir that look like artifacts (not our wrapper files).

    Returns a dict mapping filename -> file contents (bytes).

    Safety checks applied:
      - regular files only (no symlinks — defense against symlink tricks)
      - size-capped (defense against disk-fill attacks)
      - unreadable files silently skipped
    """
    artifacts: dict[str, bytes] = {}
    for f in workdir.iterdir():
        if f.name in exclude:
            continue
        if f.is_symlink():
            continue
        if not f.is_file():
            continue
        try:
            size_mb = f.stat().st_size / (1024 * 1024)
            if size_mb > MAX_ARTIFACT_SIZE_MB:
                continue
            artifacts[f.name] = f.read_bytes()
        except OSError:
            continue
    return artifacts


# === MAIN ENTRYPOINT ===

def execute_sandboxed(code: str, timeout_s: Optional[int] = None, gpu_access: bool = False, _skip_preflight: bool = False) -> SandboxResult:
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
    timeout_s = timeout_s or EXECUTION_TIMEOUT
    start_time = time.monotonic()  # monotonic = not affected by clock changes

    # ---- Layer 1: Preflight (performance, not security) ----
    # _skip_preflight bypasses string check for tests that exercise the
    # Docker path directly. Does NOT bypass AST Shield or container isolation.
    if not _skip_preflight:
        clean, reason = _preflight_check(code)
        if not clean:
            return SandboxResult(
                status=SandboxStatus.BLOCKED,
                stderr=f"preflight: {reason}",
                exit_code=-1,
                duration_s=time.monotonic() - start_time,
                gpu_enabled=False,
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
            stderr=f"line {e.lineno}: {e.msg}",
            duration_s=time.monotonic() - start_time,
            gpu_enabled=False,
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
        # Make workdir + code readable by container UID (65534/nobody)
        os.chmod(workdir, 0o777)
        os.chmod(code_file, 0o644)

        # ---- Layer 4: The real security boundary — the container ----
        # Every flag below is deliberate. If you don't know why one is there,
        # look it up before removing it.
        # ADR-133: GPU access requires the nvidia runtime; gVisor (runsc) does
        # not support CUDA passthrough. When gpu_access=True we trade the
        # user-space kernel boundary for hardware acceleration. Caller's choice.
        active_runtime = "nvidia" if gpu_access else DOCKER_RUNTIME
        docker_cmd = [
            "docker", "run",
            "--rm",                                   # auto-delete container on exit
            f"--runtime={active_runtime}",            # nvidia w/ GPU, else runsc/runc
            "--network=none",                         # no network access at all
            "--memory=512m",                          # RAM cap; OOM-kill if exceeded
            "--memory-swap=512m",                     # Disable swap; force OOM at cap
            "--cpus=1",                               # CPU cap
            "--pids-limit=64",                        # prevent fork bombs
            "--read-only",                            # root FS is read-only
            "--tmpfs", "/tmp:size=64m",               # writable /tmp, size-capped
            "--user=65534:65534",                     # run as 'nobody', not root
            "--cap-drop=ALL",                         # drop all Linux capabilities
            "--security-opt=no-new-privileges",       # block setuid/setgid escalation
            "-v", f"{workdir.resolve()}:/workspace:rw", # our workdir is the only writable mount
            "-w", "/workspace",
        ]
        if gpu_access:
            docker_cmd.append("--gpus=all")
        docker_cmd += [
            DOCKER_IMAGE,
            "python", "/workspace/user_code.py",
        ]

        # ---- Execute ----
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                encoding='utf-8',
                errors='replace',
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                status=SandboxStatus.TIMEOUT,
                stderr=f"execution exceeded {timeout_s}s",
                duration_s=time.monotonic() - start_time,
                runtime_used=active_runtime,
                gpu_enabled=gpu_access,
            )
        except FileNotFoundError:
            return SandboxResult(
                status=SandboxStatus.DOCKER_MISSING,
                stderr="docker not on PATH; is dockerd running?",
                duration_s=time.monotonic() - start_time,
                gpu_enabled=False,
            )
        except Exception as e:  # deliberately broad: host-side surprises
            return SandboxResult(
                status=SandboxStatus.EXCEPTION,
                stderr=f"host-side: {type(e).__name__}: {e}",
                duration_s=time.monotonic() - start_time,
                runtime_used=active_runtime, 
                gpu_enabled=gpu_access,
            )

        # ---- Process output ----
        stdout_full = proc.stdout or ""
        stderr_full = proc.stderr or ""
        stdout_trunc = len(stdout_full) > OUTPUT_LIMIT_BYTES
        stderr_trunc = len(stderr_full) > ERROR_LIMIT_BYTES

        artifacts = _collect_artifacts(workdir, exclude={"user_code.py"})

        # Note: we collect artifact NAMES, not contents. The caller can read
        # them from workdir if needed — but workdir is deleted in finally!
        # For v2.2 that is acceptable; in a later version, move artifacts to
        # a persistent location before cleanup if Reflector needs them.
        # TODO v2.3: persistent artifact store (Reflector-readable across cleanup)

        return SandboxResult(
            status=(SandboxStatus.SUCCESS if proc.returncode == 0 else SandboxStatus.OOM_KILLED if proc.returncode == 137 else SandboxStatus.ERROR),
            stdout=stdout_full[:OUTPUT_LIMIT_BYTES] if stdout_full else None,
            stderr=stderr_full[:ERROR_LIMIT_BYTES] if stderr_full else None,
            exit_code=proc.returncode,
            artifacts=artifacts,
            truncated_stdout=stdout_trunc,
            truncated_stderr=stderr_trunc,
            duration_s=time.monotonic() - start_time,
            runtime_used=active_runtime,
            gpu_enabled=gpu_access,
        )

    finally:
        # Guaranteed cleanup. Runs even if we returned above, even on exception,
        # even on KeyboardInterrupt. THIS is why try/finally matters.
        shutil.rmtree(workdir, ignore_errors=True)


# === SMOKE TESTS ===
# These are NOT proper tests — they just verify the pipe is connected.
# Real tests go in tests/test_sandbox.py with pytest.

if __name__ == "__main__":
    print("=== Sandbox v2.2.0 smoke tests ===\n")

    cases = [
        ("safe code", "print('hello'); import math; print(math.pi)"),
        ("blocked import", "import os\nos.system('whoami')"),
        ("syntax error", "def broken(:\n    pass"),
        ("timeout", "import time; time.sleep(10)"),
    ]

    for name, code in cases:
        print(f"--- {name} ---")
        r = execute_sandboxed(code, timeout_s=5)
        print(f"  status:    {r.status.value}")
        print(f"  duration:  {r.duration_s:.2f}s")
        if r.stdout:   print(f"  output:    {r.stdout[:100]!r}")
        if r.error:    print(f"  error:     {r.error[:100]!r}")
        print()

