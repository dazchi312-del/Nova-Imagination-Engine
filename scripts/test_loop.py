import sys
sys.path.insert(0, r"C:\Users\dazch\nova")

from nova.core.loop import run_loop

print("=== Test 1: Plain conversation (no tool) ===")
reply = run_loop("What is 2 + 2? Answer in one sentence.")
print("Nova:", reply)
print()

print("=== Test 2: Tool use (list directory) ===")
reply = run_loop("List the files in the current directory using your list_directory tool.")
print("Nova:", reply)
print()

print("=== All loop tests done ===")
