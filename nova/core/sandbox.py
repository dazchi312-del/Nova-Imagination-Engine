--- a/core/sandbox.py
+++ b/core/sandbox.py
@@ -1,5 +1,5 @@
 # nova/core/sandbox.py
-# v2.1.0 — Layered defense: preflight + AST Shield + Docker
+# v2.1.1 — Runtime detection (runsc→runc fallback) + _skip_preflight for tests
@@
 import os
+import shutil
 import subprocess
@@
-DOCKER_RUNTIME = "runsc"
+def _detect_runtime() -> str:
+    """
+    Resolution order:
+      1. NOVA_SANDBOX_RUNTIME env var (explicit override)
+      2. runsc on PATH (gVisor, strict isolation)
+      3. runc fallback (standard, permissive — Dreamer default until gVisor lands)
+    """
+    override = os.environ.get("NOVA_SANDBOX_RUNTIME")
+    if override:
+        return override
+    if shutil.which("runsc"):
+        return "runsc"
+    return "runc"
+
+DOCKER_RUNTIME = _detect_runtime()
@@
 @dataclass
 class SandboxResult:
     stdout: str
     stderr: str
     exit_code: int
     timed_out: bool
     oom_killed: bool
     duration_s: float
     artifacts: Dict[str, bytes]
+    runtime_used: Optional[str] = None
@@
-def execute_sandboxed(code: str, timeout_s: float = 5.0) -> SandboxResult:
+def execute_sandboxed(
+    code: str,
+    timeout_s: float = 5.0,
+    _skip_preflight: bool = False,
+) -> SandboxResult:
+    """
+    Execute untrusted code in a Docker sandbox.
+
+    _skip_preflight: INTERNAL. Tests only. Bypasses the performance-tier
+    string filter so integration tests can validate syscall-level isolation
+    (socket, os.getuid, etc.). Do not use in production paths.
+    """
@@
-    # 1. Preflight string check
-    if _preflight_reject(code):
-        return SandboxResult(..., exit_code=-1, ...)
+    # 1. Preflight string check (skippable for integration tests)
+    if not _skip_preflight and _preflight_reject(code):
+        return SandboxResult(
+            stdout="", stderr="preflight: forbidden token",
+            exit_code=-1, timed_out=False, oom_killed=False,
+            duration_s=0.0, artifacts={}, runtime_used=DOCKER_RUNTIME,
+        )
@@
     # (populate runtime_used on every return path below)

