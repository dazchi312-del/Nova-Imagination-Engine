import sys
sys.path.insert(0, r"C:\Users\dazch\nova")

from nova.core.dispatcher import dispatch, TOOL_SCHEMA

# Test 1: no tool call
called, out = dispatch("Hello Nova, how are you?")
assert called == False, f"Expected False, got {called}"
print("[OK] Test 1 passthrough: called=False")

# Test 2: valid tool call
test_input = '[TOOL] {"tool": "list_directory", "args": {"path": "."}} [/TOOL]'
called, out = dispatch(test_input)
assert called == True, f"Expected True, got {called}"
print("[OK] Test 2 tool dispatch: called=True")
print("     Output preview:", out[:120])

# Test 3: unknown tool
test_bad = '[TOOL] {"tool": "explode", "args": {}} [/TOOL]'
called, out = dispatch(test_bad)
assert called == True
assert "TOOL ERROR" in out
print("[OK] Test 3 unknown tool handled gracefully")
print("     Output:", out)

# Test 4: malformed JSON
test_malformed = '[TOOL] {bad json here} [/TOOL]'
called, out = dispatch(test_malformed)
assert called == True
assert "DISPATCH ERROR" in out
print("[OK] Test 4 malformed JSON handled gracefully")
print("     Output:", out)

print()
print("=== All tests passed ===")
