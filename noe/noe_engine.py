"""
Nova Output Engine (NOE) - Main Processing Loop
Judge and improve architecture with refinement cycles
"""

import requests
import json
import re
from nova.core.scoring import calculate_weighted_score

# Configuration
PRIMARY_URL = "http://localhost:1234/v1/chat/completions"
REFLECTOR_URL = "http://192.168.100.2:11434/api/generate"
ACCEPT_THRESHOLD = 0.85
REJECT_THRESHOLD = 0.50
MAX_REFINEMENTS = 3

SYSTEM_PROMPT = """You are Nova, a local-first AI operating system and Imagination Engine. 
You run on a decoupled two-node architecture:
- Primary Node: Lenovo Legion Pro 7i with RTX 5090 running Nemotron 70B (that's you)
- Validation Node: MacBook Pro M4 running Llama 3.1 8B as a "Reflector" for quality scoring
Your creator is Daz (Phase 12). You operate from C:\\Users\\dazch\\nova."""


def strip_markdown_wrapper(text: str) -> str:
    """Remove markdown code fences from Reflector responses."""
    pattern = r'^```(?:json)?\s*\n?(.*?)\n?```$'
    match = re.search(pattern, text.strip(), re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def generate_output(prompt: str, feedback: str = None) -> str:
    """Generate response from Primary Node"""
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if feedback:
        messages.append({"role": "user", "content": prompt})
        messages.append({"role": "assistant", "content": "[Previous attempt was scored and needs improvement]"})
        messages.append({"role": "user", "content": f"Please improve your response based on this feedback:\n{feedback}"})
    else:
        messages.append({"role": "user", "content": prompt})
    
    response = requests.post(PRIMARY_URL, json={
        "model": "nemotron",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024
    }, timeout=300)
    return response.json()["choices"][0]["message"]["content"]


def score_with_reflector(prompt: str, response: str) -> dict:
    """Get quality scores from Reflector"""

    scoring_prompt = f'''You are Nova's Reflector - a quality validation node.

Score this response on 5 dimensions (0.0-1.0 each):

**Original Request:** {prompt}

**Response to Score:** {response}

Return ONLY valid JSON:
{{"quality": 0.X, "clarity": 0.X, "structure": 0.X, "hallucination_risk": 0.X, "identity_alignment": 0.X, "feedback": "specific improvement suggestions"}}'''

    result = requests.post(REFLECTOR_URL, json={
        "model": "llama3.1:8b",
        "prompt": scoring_prompt,
        "stream": False,
        "temperature": 0.3
    }, timeout=120)

    text = result.json()["response"]
    
    # Strip markdown wrappers first
    text = strip_markdown_wrapper(text)
    
    # DEBUG: Show what Reflector returned
    print(f"  [DEBUG] Reflector raw ({len(text)} chars): {text[:300]}...")
    
    # Try multiple extraction patterns
    # Pattern 1: Standard JSON block
    match = re.search(r'\{[^{}]*"quality"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    # Pattern 2: Any JSON-like structure
    match = re.search(r'\{.*?\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    # Pattern 3: Extract scores manually with regex
    scores = {}
    for key in ["quality", "clarity", "structure", "hallucination_risk", "identity_alignment"]:
        m = re.search(rf'"{key}":\s*([\d.]+)', text)
        if m:
            scores[key] = float(m.group(1))
    
    if len(scores) >= 3:  # At least 3 scores found
        # Fill missing with neutral values
        for key in ["quality", "clarity", "structure", "hallucination_risk", "identity_alignment"]:
            if key not in scores:
                scores[key] = 0.7
        scores["feedback"] = "Extracted from partial response"
        print(f"  [DEBUG] Fallback extraction: {scores}")
        return scores
    
    print(f"  [DEBUG] Parse failed, no scores extracted")
    return None


def process(prompt: str) -> dict:
    """Main NOE processing loop with refinement"""
    
    print("\n" + "="*50)
    print("NOE PROCESSING")
    print("="*50)
    
    attempt = 0
    feedback = None
    
    while attempt <= MAX_REFINEMENTS:
        attempt += 1
        print(f"\n[Attempt {attempt}/{MAX_REFINEMENTS + 1}]")
        
        # Generate
        print("  Generating with Nemotron...")
        response = generate_output(prompt, feedback)
        print(f"  Generated {len(response)} chars")
        
        # Score
        print("  Scoring with Reflector...")
        scores = score_with_reflector(prompt, response)
        
        if not scores:
            print("  ERROR: Could not parse scores")
            continue
            
        weighted = calculate_weighted_score(scores)
        print(f"  Score: {weighted:.3f}")
        
        # Decision
        if weighted >= ACCEPT_THRESHOLD:
            print(f"  ✓ ACCEPT")
            return {"status": "ACCEPT", "score": weighted, "output": response, "attempts": attempt}
        
        if weighted < REJECT_THRESHOLD:
            print(f"  ✗ REJECT")
            return {"status": "REJECT", "score": weighted, "output": response, "attempts": attempt}
        
        if attempt <= MAX_REFINEMENTS:
            print(f"  → REFINING (feedback: {scores.get('feedback', 'none')[:50]}...)")
            feedback = scores.get("feedback", "Please improve clarity and structure.")
    
    # Max attempts reached
    print(f"  ! MAX ATTEMPTS - accepting best effort")
    return {"status": "ACCEPT_MARGINAL", "score": weighted, "output": response, "attempts": attempt}


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        prompt = "Explain what Nova is in one paragraph."
    
    result = process(prompt)
    
    print("\n" + "="*50)
    print(f"FINAL: {result['status']} (Score: {result['score']:.3f}, Attempts: {result['attempts']})")
    print("="*50)
    print(f"\nOutput:\n{result['output']}")

