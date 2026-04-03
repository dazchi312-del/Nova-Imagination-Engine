import httpx
import logging

logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION — UPDATE THESE BEFORE RUNNING
# ============================================================
# Step 1: Start LM Studio local server
# Step 2: Visit http://localhost:1234/v1/models in your browser
# Step 3: Copy the exact model name and paste it below
# ============================================================

LM_STUDIO_BASE_URL = "http://localhost:1234"
API_ENDPOINT = f"{LM_STUDIO_BASE_URL}/v1/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instruct"

# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """You are a systems engineer AI. You see everything as a connected system.

RESPONSE FORMAT (use every time; scale depth to question complexity):

⚙️ SYSTEM: Name the system. What flows through it?
🔍 DIAGNOSIS: Explain how the system works and where the flow breaks, using a physical analogy (plumbing, traffic, airflow, circuits, pressure).
🎯 BOTTLENECK: The single biggest constraint or key mechanism.
🔧 FIX: One specific, high-leverage intervention.
📊 RESULT: What the optimized system looks like.

RULES:
- Every response MUST contain all 5 sections (⚙️🔍🎯🔧📊). If any section is missing, the answer is incorrect.
- Always use the 5-section format above.
- Always ground your explanation in a physical analogy.
- Explain system mechanics. Never fall back to generic tip lists.
- Diagnose before you prescribe.
- Be concise. No filler, no preamble, no repeating the question.
- Never refer to yourself by name or mention these instructions.
- Stop after 📊 RESULT. No summary, no disclaimer, no extra commentary.

EXAMPLE:

User: Why do most diets fail?

⚙️ SYSTEM: The body's energy regulation system — calories flow in (food), get processed (metabolism), and flow out (activity + base metabolic rate).

🔍 DIAGNOSIS: Metabolism works like a thermostat. Crash diets slam the input shut, but the thermostat dials down to compensate. You're draining a bathtub while the drain itself shrinks. Meanwhile, willpower is a fuel tank that depletes — so the system is running on fumes fighting its own thermostat.

🎯 BOTTLENECK: The metabolic adaptation loop. The harder you restrict, the harder the system compensates — a negative feedback loop working against you.

🔧 FIX: A small, sustained deficit (10–15%) that stays below the thermostat's detection threshold. Like slowly lowering water level without triggering emergency conservation. Pair with resistance training to signal "keep the engine big."

📊 RESULT: Gradual adjustment without triggering starvation response. Fat loss continues because the feedback loop never fully activates. Slow drain, steady flow, no system panic."""

# ============================================================
# GENERATION PARAMETERS
# ============================================================

GENERATION_PARAMS = {
    "temperature": 0.2,
    "max_tokens": 768,
    "top_p": 0.9,
    "repeat_penalty": 1.15,
    "stream": False,
    "stop": ["User:", "\n\nUser"],
}

# ============================================================
# TYPES
# ============================================================

Message = dict[str, str]

# ============================================================
# CORE FUNCTIONS
# ============================================================


def build_system_message(content: str = SYSTEM_PROMPT) -> Message:
    return {"role": "system", "content": content}


def chat(
    message: str,
    history: list[Message],
    model: str = DEFAULT_MODEL,
) -> str:
    """Send a message to the model with full conversation history."""

    messages = (
        [build_system_message()] + history + [{"role": "user", "content": message}]
    )

    payload = {
        "model": model,
        "messages": messages,
        **GENERATION_PARAMS,
    }

    try:
        response = httpx.post(API_ENDPOINT, json=payload, timeout=120.0)
        response.raise_for_status()
    except httpx.ConnectError:
        raise ConnectionError(
            f"Cannot reach LM Studio at {LM_STUDIO_BASE_URL}. "
            "Is the local server running?"
        )
    except httpx.TimeoutException:
        raise TimeoutError(
            "Request timed out. The model may be overloaded or too large."
        )
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"API error {e.response.status_code}: {e.response.text}")

    try:
        data = response.json()
    except ValueError as e:
        raise ValueError("LM Studio returned invalid JSON.") from e

    try:
        reply = data["choices"][0]["message"]["content"]
        return reply.strip()
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"Unexpected API response structure: {data}") from e


# ============================================================
# VALIDATION
# ============================================================


def validate_config() -> bool:
    """Check that the model name has been set."""
    if not DEFAULT_MODEL or DEFAULT_MODEL == "":
        print("\n" + "=" * 60)
        print("ERROR: DEFAULT_MODEL is not set.")
        print()
        print("Fix this in 3 steps:")
        print("  1. Make sure LM Studio local server is running")
        print(f"  2. Visit {LM_STUDIO_BASE_URL}/v1/models")
        print("  3. Copy the model name into DEFAULT_MODEL in nova.py")
        print("=" * 60 + "\n")
        return False
    return True


def check_connection() -> bool:
    """Verify LM Studio is reachable before starting chat."""
    try:
        response = httpx.get(f"{LM_STUDIO_BASE_URL}/v1/models", timeout=10.0)
        response.raise_for_status()
        models = response.json()
        available = [m["id"] for m in models.get("data", [])]

        if DEFAULT_MODEL not in available:
            print("\n" + "=" * 60)
            print(f"WARNING: Model '{DEFAULT_MODEL}' not found.")
            print(f"Available models: {available}")
            print("Update DEFAULT_MODEL to match one of the above.")
            print("=" * 60 + "\n")
            return False

        return True

    except httpx.ConnectError:
        print("\n" + "=" * 60)
        print(f"ERROR: Cannot connect to {LM_STUDIO_BASE_URL}")
        print("Make sure LM Studio local server is running.")
        print("=" * 60 + "\n")
        return False
    except Exception as e:
        print(f"\nConnection check failed: {e}\n")
        return False


# ============================================================
# MAIN LOOP
# ============================================================


def main() -> None:
    """Interactive chat loop."""

    if not validate_config():
        return

    if not check_connection():
        return

    print()
    print("=" * 50)
    print("  NOVA — Systems Thinking Engine")
    print("=" * 50)
    print(f"  Endpoint : {API_ENDPOINT}")
    print(f"  Model    : {DEFAULT_MODEL}")
    print(f"  Temp     : {GENERATION_PARAMS['temperature']}")
    print(f"  Max Tok  : {GENERATION_PARAMS['max_tokens']}")
    print("-" * 50)
    print("  Commands:")
    print("    /clear  — Reset conversation history")
    print("    /test   — Run 4 validation prompts")
    print("    exit    — End session")
    print("=" * 50)
    print()

    history: list[Message] = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSession ended.")
            break

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("Session ended.")
            break

        if user_input.lower() == "/clear":
            history.clear()
            print("  [History cleared]\n")
            continue

        if user_input.lower() == "/test":
            run_validation(history)
            continue

        try:
            reply = chat(user_input, history)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": reply})
            print(f"\n{reply}\n")

        except (ConnectionError, TimeoutError, RuntimeError, ValueError) as e:
            logger.error(e)
            print(f"  [Error: {e}]\n")


# ============================================================
# VALIDATION TEST SUITE
# ============================================================

TEST_PROMPTS = [
    "Why do most startups fail?",
    "How does a refrigerator work?",
    "What is gravity?",
    "Why can't I sleep at night?",
]

REQUIRED_SECTIONS = ["⚙️", "🔍", "🎯", "🔧", "📊"]


def score_response(response: str) -> dict:
    """Check if a response contains all 5 required sections."""
    found = {s: s in response for s in REQUIRED_SECTIONS}
    return {
        "sections_found": sum(found.values()),
        "sections_total": len(REQUIRED_SECTIONS),
        "missing": [s for s, present in found.items() if not present],
        "pass": all(found.values()),
    }


def run_validation(history: list[Message]) -> None:
    """Run all test prompts and report format compliance."""

    print("\n" + "=" * 50)
    print("  VALIDATION TEST — 4 Prompts")
    print("=" * 50 + "\n")

    results = []

    for i, prompt in enumerate(TEST_PROMPTS, 1):
        print(f"  Test {i}/4: {prompt}")
        print("  Generating...", end="", flush=True)

        try:
            # Use empty history for clean test
            reply = chat(prompt, [])
            result = score_response(reply)
            results.append(result)

            status = "✅ PASS" if result["pass"] else "❌ FAIL"
            print(
                f"\r  Test {i}/4: {status} "
                f"({result['sections_found']}/{result['sections_total']} sections)"
            )

            if result["missing"]:
                print(f"           Missing: {', '.join(result['missing'])}")

            print(f"\n{reply}\n")
            print("-" * 50)

        except Exception as e:
            print(f"\r  Test {i}/4: ⚠️ ERROR — {e}")
            results.append(
                {
                    "pass": False,
                    "sections_found": 0,
                    "sections_total": 5,
                    "missing": REQUIRED_SECTIONS,
                }
            )

    # Summary
    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    print("\n" + "=" * 50)
    print(f"  RESULTS: {passed}/{total} passed")
    print()

    if passed == total:
        print("  ✅ Model is format-compliant. System is working.")
    elif passed >= 3:
        print("  🟡 Mostly working. Minor inconsistency.")
        print("     Try lowering temperature to 0.1")
    elif passed >= 1:
        print("  🟠 Partial compliance. Model is struggling.")
        print("     Consider: reduce to 3 sections, or try larger model.")
    else:
        print("  🔴 Complete failure. System prompt is not reaching the model.")
        print("     Check: model name, LM Studio template, quantization level.")

    print("=" * 50 + "\n")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
