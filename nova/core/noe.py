# core/noe.py
# Nova Output Engine - Class wrapper for dream_lab integration
# v1.2.0

import json
from dataclasses import dataclass
from nova.core.loop import call_primary, call_reflector

with open("nova_config.json") as f:
    cfg = json.load(f)

THRESHOLD = cfg.get("reflector", {}).get("threshold", 0.75)


@dataclass
class GenerationResult:
    """Result object from NOE generation."""
    final_output: str
    score: float
    critique: str
    accepted: bool
    iterations: int = 1


class NovaOutputEngine:
    """
    Class interface for the Nova Output Engine.
    Wraps the functional API from loop.py for use by dream_lab and other modules.
    """
    
    def __init__(self):
        self.threshold = THRESHOLD
        self.last_score = None
        self.last_critique = None
    
    def generate(self, prompt: str, context: str = "") -> GenerationResult:
        """
        Generate a response from the Primary Node (Nemotron 70B),
        then reflect and return a structured result.
        
        Args:
            prompt: The generation prompt
            context: Optional context description (for logging)
            
        Returns:
            GenerationResult with final_output, score, critique, accepted
        """
        # Build messages in the format call_primary expects
        messages = [
            {
                "role": "user", 
                "content": prompt
            }
        ]
        
        # Generate from Primary
        response = call_primary(messages)
        
        # Reflect on the output - returns a float directly
        score = call_reflector(prompt, response)
        
        # Ensure score is a float
        if isinstance(score, dict):
            score = score.get("score", 0.0)
        
        score = float(score)
        
        self.last_score = score
        self.last_critique = f"Score: {score:.2f}"  # Simple critique since reflector only returns score
        
        return GenerationResult(
            final_output=response,
            score=score,
            critique=f"Reflector score: {score:.2f}",
            accepted=score >= self.threshold
        )
    
    def generate_raw(self, prompt: str) -> str:
        """
        Generate without reflection (for simple queries).
        
        Returns:
            Raw string response from Primary
        """
        messages = [{"role": "user", "content": prompt}]
        return call_primary(messages)
    
    def reflect_only(self, original_prompt: str, response: str) -> float:
        """
        Score a response using the Reflector Node (Llama 8B).
        
        Returns:
            float score 0.0-1.0
        """
        return call_reflector(original_prompt, response)

