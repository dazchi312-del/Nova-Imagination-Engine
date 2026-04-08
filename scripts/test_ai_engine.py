"""
Test Layer 2 - AI Engine
Verifies LM Studio connection and generation
"""

import sys
sys.path.insert(0, r"C:\Users\dazch\nova")

from core.ai_engine import AIEngine
from core.errors import NovaEngineError
from core.logger import session_logger, LogLevel


def test_ai_engine():
    session_logger.log("=== AI Engine Tests Begin ===", LogLevel.VISION)

    engine = AIEngine()

    # --- Test 1: Basic generation ---
    session_logger.log("Test 1: Basic generation", LogLevel.ARCH)
    try:
        response = engine.generate("Say exactly this: NOVA_ENGINE_OK")
        print(f"✅ generate(): {response[:80]}")
    except NovaEngineError as e:
        print(f"❌ generate() failed: {e}")
        print("   Is LM Studio running with a model loaded?")
        return

    # --- Test 2: generate_with_history ---
    session_logger.log("Test 2: generate_with_history", LogLevel.ARCH)
    history = [
        {"role": "user",      "content": "My name is Daz."},
        {"role": "assistant", "content": "Got it, Daz."},
        {"role": "user",      "content": "What is my name?"},
    ]
    response2 = engine.generate_with_history(history)
    print(f"✅ generate_with_history(): {response2[:80]}")

    # --- Test 3: Token tracking ---
    session_logger.log("Test 3: Token tracking", LogLevel.ARCH)
    usage = engine.token_usage()
    print(f"✅ token_usage(): {usage}")

    # --- Test 4: Empty input error ---
    session_logger.log("Test 4: Empty input guard", LogLevel.ARCH)
    try:
        engine.generate("")
        print("❌ Should have raised NovaEngineError")
    except NovaEngineError as e:
        print(f"✅ Empty input caught: {e}")

    session_logger.log("=== AI Engine Tests Complete ===", LogLevel.VISION)
    print(f"\n✅ AI Engine operational")
    print(f"📝 Session log: {session_logger.session_file}")


if __name__ == "__main__":
    test_ai_engine()
