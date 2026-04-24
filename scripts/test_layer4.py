"""
Layer 4 Tests — The Hands
Tests Nova's ability to write, run, and fix code autonomously
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nova.core.logger import log, set_level
from nova.core.executor import Executor
from nova.core.builder import Builder
from nova.core.config import load_config

set_level("CODE")

config = load_config()
workspace = config.get("workspace", "C:/Users/dazch/nova")

log("VISION", "=== Layer 4 Tests Begin ===")

# Test 1 — Executor: Run good code
log("VISION", "Test 1: Execute valid Python code")
executor = Executor(workspace)
result = executor.run_code(
    'print("Nova Imagination Engine — Layer 4 active")',
    "test_valid.py"
)
assert result.success, f"Should succeed: {result.error}"
assert "Nova Imagination Engine" in result.output
print(f"✅ Test 1 passed: {result.output}")

# Test 2 — Executor: Handle broken code
log("VISION", "Test 2: Execute broken Python code")
result = executor.run_code(
    'print("missing closing',
    "test_broken.py"
)
assert not result.success, "Should fail on syntax error"
print(f"✅ Test 2 passed: caught error correctly")

# Test 3 — Executor: File not found
log("VISION", "Test 3: Handle missing file")
result = executor.run_file("nonexistent_file.py")
assert not result.success
assert "not found" in result.error
print(f"✅ Test 3 passed: missing file handled")

# Test 4 — Builder: Build working code
log("VISION", "Test 4: Builder with valid code")
builder = Builder(workspace)
result = builder.build(
    code='print("Built by Nova")\nprint("Layer 4 operational")',
    filename="test_build.py"
)
assert result.success, f"Build should succeed: {result.error}"
assert result.attempts == 1
print(f"✅ Test 4 passed: {result.output.splitlines()[0]}")

# Test 5 — Build a real word counter app
log("VISION", "Test 5: Build a real word counter app")
word_counter_code = '''
def count_words(text):
    words = text.split()
    return len(words)

sample = "Nova Imagination Engine is a creative AI built for makers"
count = count_words(sample)
print(f"Word count: {count}")
print(f"Words: {sample.split()}")
'''
result = builder.build(
    code=word_counter_code,
    filename="word_counter.py"
)
assert result.success, f"Word counter should build: {result.error}"
assert "Word count: 10" in result.output
print(f"✅ Test 5 passed: {result.output.splitlines()[0]}")

log("VISION", "=== Layer 4 Tests Complete ===")
print("\n✅ All Layer 4 tests passed")
print("The Hands are operational 🤲")
