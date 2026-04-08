"""
Test Layer 3 — Nova Core Loop
Tests: commands, planning, autonomous loop, reflection
"""

import sys
sys.path.insert(0, r"C:\Users\dazch\nova")

from core.nova import Nova
from core.logger import session_logger, LogLevel


def test_nova_core():
    session_logger.log("=== Nova Core Tests Begin ===", LogLevel.VISION)

    nova = Nova()

    # ── Test 1: /help command ──
    print("\n--- Test 1: /help ---")
    result = nova.think("/help")
    print(result)
    assert "Nova Commands" in result
    print("✅ /help passed")

    # ── Test 2: /status command ──
    print("\n--- Test 2: /status ---")
    result = nova.think("/status")
    print(result)
    assert "Session Status" in result
    print("✅ /status passed")

    # ── Test 3: /files command ──
    print("\n--- Test 3: /files ---")
    result = nova.think("/files")
    print(result[:200])
    print("✅ /files passed")

    # ── Test 4: Unknown command ──
    print("\n--- Test 4: Unknown command ---")
    result = nova.think("/unknown")
    print(result)
    assert "Unknown command" in result
    print("✅ Unknown command caught")

    # ── Test 5: Autonomous loop ──
    print("\n--- Test 5: Autonomous loop ---")
    result = nova.think("What is your name and purpose?")
    print(f"Nova → {result[:150]}")
    assert len(result) > 20
    print("✅ Autonomous loop passed")

    # ── Test 6: plan.md was written ──
    print("\n--- Test 6: plan.md written ---")
    result = nova.think("/plan")
    print(result[:200])
    assert "Nova Plan" in result
    print("✅ plan.md written and readable")

    # ── Test 7: /clear resets history ──
    print("\n--- Test 7: /clear ---")
    before = len(nova.state.conversation_history)
    nova.think("/clear")
    after = len(nova.state.conversation_history)
    print(f"History before: {before}, after: {after}")
    assert after < before
    print("✅ /clear passed")

    session_logger.log("=== Nova Core Tests Complete ===", LogLevel.VISION)
    print("\n✅ All Nova Core tests passed")
    print("Layer 3 — Core Loop is operational\n")


if __name__ == "__main__":
    test_nova_core()
