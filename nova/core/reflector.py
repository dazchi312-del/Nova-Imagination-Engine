"""
core/reflector.py - L5 Response Evaluator
Uses secondary 8B model to score and flag primary responses.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI


class Reflector:
    def __init__(self, config: dict):
        self.client = OpenAI(
            base_url=config.get("base_url", "http://localhost:1234/v1"),
            api_key=config.get("api_key", "lm-studio"),
        )
        self.model      = config.get("reflection_model", "llama-3.1-nemotron-70b-instruct-hf")
        self.threshold  = config.get("reflection_threshold", 0.75)
        self.dimensions = ["accuracy", "coherence", "identity_alignment", "utility"]

    # ------------------------------------------------------------------
    def evaluate(self, prompt: str, response: str) -> dict:
        messages = self._build_eval_prompt(prompt, response)

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=256,
            )
            raw = completion.choices[0].message.content or ""
            result = self._parse_evaluation(raw)
        except Exception as e:
            print(f"[Reflector] Evaluation error: {e}")
            result = self._fallback()

        result["passed"] = result["score"] >= self.threshold
        return result

    # ------------------------------------------------------------------
    def _build_eval_prompt(self, prompt: str, response: str) -> list:
        dimension_list = "\n".join(f"- {d}" for d in self.dimensions)
        return [
            {
                "role": "system",
                "content": (
                    "You are a strict response quality evaluator. "
                    "You output only valid JSON. No markdown. No explanation. "
                    "You MUST assign real numeric scores between 0.0 and 1.0. "
                    "Never output 0.0 for all dimensions unless the response is completely empty."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Score this AI response. The user asked: \"{prompt}\"\n\n"
                    f"The AI responded: \"{response}\"\n\n"
                    f"Rate each dimension with a REAL score from 0.0 to 1.0:\n"
                    f"{dimension_list}\n\n"
                    "Rules:\n"
                    "- accuracy: Is the response factually plausible?\n"
                    "- coherence: Is it logically structured and clear?\n"
                    "- identity_alignment: Does it sound like a helpful AI assistant?\n"
                    "- utility: Does it actually answer the question?\n\n"
                    "- score: average of the 4 dimension scores\n"
                    "- flags: list from [HALLUCINATION_RISK, FILLER_DETECTED, OFF_TOPIC, INCOMPLETE] "
                    "only if genuinely applicable. Empty list [] if none apply.\n\n"
                    "Output ONLY valid JSON, nothing else:\n"
                    "{\"dimensions\": {\"accuracy\": 0.85, \"coherence\": 0.9, "
                    "\"identity_alignment\": 0.8, \"utility\": 0.88}, "
                    "\"score\": 0.86, \"flags\": []}\n\n"
                    "Now evaluate and output your JSON:"
                ),
            },
        ]

    # ------------------------------------------------------------------
    def _parse_evaluation(self, raw: str) -> dict:
        text = raw.strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(
                line for line in lines
                if not line.startswith("```")
            ).strip()

        # Extract first JSON object if there is surrounding text
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            text = text[start:end]

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[Reflector] JSON parse error: {e}")
            return self._fallback()

        dimensions = data.get("dimensions", {})
        score      = data.get("score", 0.0)
        flags      = data.get("flags", [])

        # Recompute score from dimensions if score is 0 but dimensions exist
        if score == 0.0 and dimensions:
            values = [v for v in dimensions.values() if isinstance(v, (int, float))]
            if values:
                score = sum(values) / len(values)

        return {
            "score":      round(float(score), 4),
            "flags":      [str(f) for f in flags],
            "dimensions": {k: round(float(v), 4) for k, v in dimensions.items()},
        }

    # ------------------------------------------------------------------
    def _fallback(self) -> dict:
        return {
            "score":      0.0,
            "flags":      ["INCOMPLETE"],
            "dimensions": {d: 0.0 for d in self.dimensions},
        }


# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("Running standalone Reflector test...")

    config = {
        "base_url":           "http://localhost:1234/v1",
        "api_key":            "lm-studio",
        "reflection_model":   "llama-3.1-nemotron-70b-instruct-hf",
        "reflection_threshold": 0.75,
    }

    r = Reflector(config)
    result = r.evaluate(
        prompt="What is the capital of France?",
        response="The capital of France is Paris. It is known for the Eiffel Tower.",
    )

    print(f"Score:      {result['score']}")
    print(f"Passed:     {result['passed']}")
    print(f"Flags:      {result['flags']}")
    print(f"Dimensions: {result['dimensions']}")

