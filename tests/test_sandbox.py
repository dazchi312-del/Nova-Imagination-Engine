# tests/test_sandbox.py
# Nova sandbox integration tests — tiered by runtime strictness.
import os
import subprocess
import pytest

docker = pytest.importorskip("docker", reason="docker SDK not installed")

from nova.core.sandbox import execute_sandboxed, DOCKER_RUNTIME

STRICT = DOCKER_RUNTIME == "runsc"


@pytest.fixture(scope="session", autouse=True)
def _docker_available():
    try:
        r = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=5
        )
        if r.returncode != 0:
            pytest.skip("docker daemon not reachable")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("docker CLI not available")


@pytest.mark.integration
class TestSandboxContract:
    """Runs on any runtime (runc or runsc)."""

    def test_hello_world(self):
        r = execute_sandboxed("print('hi')")
        assert r.exit_code == 0
        assert r.stdout.strip() == "hi"
        assert r.runtime_used in ("runc", "runsc")

    def test_syntax_error_fast_path(self):
        r = execute_sandboxed("def (:")
        assert r.exit_code != 0
        assert r.duration_s < 0.5  # never hit Docker

    def test_timeout_kill(self):
        r = execute_sandboxed("while True: pass", timeout_s=1.0)
        assert r.timed_out is True
        assert r.duration_s < 3.0

    def test_oom_kill(self):
        code = "x = bytearray(800 * 1024 * 1024)"  # 800MB vs 512MB cap
        r = execute_sandboxed(code, timeout_s=10.0)
        assert r.oom_killed is True

    def test_tmpfs_writable(self):
        r = execute_sandboxed("open('/tmp/x','w').write('ok'); print('ok')")
        assert r.exit_code == 0
        assert "ok" in r.stdout

    def test_root_fs_readonly(self):
        r = execute_sandboxed("open('/etc/evil','w').write('x')")
        assert r.exit_code != 0
        assert "read-only" in r.stderr.lower() or "permission" in r.stderr.lower()

    def test_network_blocked(self):
        code = (
            "import socket\n"
            "s = socket.socket()\n"
            "s.settimeout(2)\n"
            "try:\n"
            "    s.connect(('1.1.1.1', 53))\n"
            "    print('LEAK')\n"
            "except Exception as e:\n"
            "    print('BLOCKED')\n"
        )
        r = execute_sandboxed(code, _skip_preflight=True)
        assert "BLOCKED" in r.stdout
        assert "LEAK" not in r.stdout

    def test_non_root_user(self):
        code = "import os; print(os.getuid())"
        r = execute_sandboxed(code, _skip_preflight=True)
        assert r.exit_code == 0
        assert r.stdout.strip() == "65534"

    def test_artifact_collection(self):
        code = (
            "with open('/workspace/out.txt','w') as f:\n"
            "    f.write('artifact-ok')\n"
        )
        r = execute_sandboxed(code)
        assert r.exit_code == 0
        assert "out.txt" in r.artifacts
        assert r.artifacts["out.txt"] == b"artifact-ok"

    def test_preflight_still_blocks_by_default(self):
        # sanity: bypass is opt-in, default path still rejects
        r = execute_sandboxed("import socket")
        assert r.exit_code == -1
        assert "preflight" in r.stderr


@pytest.mark.integration
@pytest.mark.skipif(not STRICT, reason="requires runsc (gVisor)")
class TestSandboxStrict:
    """Placeholder for gVisor-only syscall isolation tests."""

    def test_runtime_is_runsc(self):
        assert DOCKER_RUNTIME == "runsc"

    # TODO: ptrace block, kernel keyring, /proc/kcore, unshare, etc.
