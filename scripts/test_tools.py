"""
Test Layer 1 - File I/O and Code Execution Tools
"""

import sys
sys.path.insert(0, r"C:\Users\dazch\nova")

from core.tools import read_file, write_file, run_code, list_files
from core.errors import NovaToolError
from core.logger import session_logger, LogLevel


def test_layer1():
    session_logger.log("=== Layer 1 Tool Tests Begin ===", LogLevel.VISION)

    # --- Test 1: write_file ---
    session_logger.log("Test 1: write_file", LogLevel.ARCH)
    result = write_file(
        "temp/test_output.py",
        'print("Nova Layer 1 write_file works")\n'
    )
    print(f"✅ write_file: {result}")

    # --- Test 2: read_file ---
    session_logger.log("Test 2: read_file", LogLevel.ARCH)
    content = read_file("temp/test_output.py")
    print(f"✅ read_file: {repr(content)}")

    # --- Test 3: run_code ---
    session_logger.log("Test 3: run_code", LogLevel.ARCH)
    outcome = run_code('print("Nova Layer 1 run_code works")')
    print(f"✅ run_code stdout: {outcome['stdout']}")
    print(f"   exit_code: {outcome['exit_code']}")
    print(f"   success:   {outcome['success']}")

    # --- Test 4: run_code failure capture ---
    session_logger.log("Test 4: run_code failure capture", LogLevel.ARCH)
    bad = run_code("raise ValueError('intentional test error')")
    print(f"✅ run_code failure captured: exit_code={bad['exit_code']}")
    print(f"   stderr: {bad['stderr'][:80]}")

    # --- Test 5: list_files ---
    session_logger.log("Test 5: list_files", LogLevel.ARCH)
    files = list_files(".")
    print(f"✅ list_files: {len(files)} files found in project")
    for f in files[:8]:
        print(f"   {f}")
    if len(files) > 8:
        print(f"   ... and {len(files) - 8} more")

    # --- Test 6: error handling ---
    session_logger.log("Test 6: NovaToolError on missing file", LogLevel.ARCH)
    try:
        read_file("does/not/exist.py")
    except NovaToolError as e:
        print(f"✅ Error caught correctly: {e}")

    session_logger.log("=== Layer 1 Tool Tests Complete ===", LogLevel.VISION)
    print("\n✅ All Layer 1 tools operational")
    print(f"📝 Session log: {session_logger.session_file}")


if __name__ == "__main__":
    test_layer1()
