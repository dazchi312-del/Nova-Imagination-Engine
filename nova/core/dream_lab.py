# C:\Users\dazch\nova\core\dream_lab.py
"""
Lab Zero: Nova's first experimental sandbox.
Where imagination becomes executable.
"""

import os
import sys
import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from nova.core.noe import NovaOutputEngine


class LabStatus(Enum):
    DREAMING = "dreaming"          # Generating hypothesis
    CRYSTALLIZING = "crystallizing" # Writing code
    TESTING = "testing"            # Executing experiment
    REFLECTING = "reflecting"      # Evaluating results
    COMPLETE = "complete"          # Experiment finished
    FAILED = "failed"              # Experiment abandoned


@dataclass
class Experiment:
    """A single experimental run in the lab."""
    id: str
    hypothesis: str
    code: str = ""
    output: str = ""
    error: str = ""
    reflection_score: float = 0.0
    reflection_notes: str = ""
    status: LabStatus = LabStatus.DREAMING
    iterations: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "hypothesis": self.hypothesis,
            "code": self.code,
            "output": self.output,
            "error": self.error,
            "reflection_score": self.reflection_score,
            "reflection_notes": self.reflection_notes,
            "status": self.status.value,
            "iterations": self.iterations,
            "created_at": self.created_at
        }


class DreamLab:
    """
    Lab Zero: Nova's experimental sandbox.
    
    A space where Nova can:
    - Form hypotheses
    - Write experimental code
    - Execute safely
    - Reflect on results
    - Iterate toward insight
    """
    
    def __init__(
        self,
        lab_name: str = "lab_zero",
        max_iterations: int = 5,
        sandbox_timeout: int = 30
    ):
        self.lab_name = lab_name
        self.max_iterations = max_iterations
        self.sandbox_timeout = sandbox_timeout
        
        # Paths
        self.base_path = Path(__file__).parent.parent
        self.lab_path = self.base_path / "labs" / lab_name
        self.experiments_path = self.lab_path / "experiments"
        self.sandbox_path = self.lab_path / "sandbox"
        
        # Create lab structure
        self.lab_path.mkdir(parents=True, exist_ok=True)
        self.experiments_path.mkdir(exist_ok=True)
        self.sandbox_path.mkdir(exist_ok=True)
        
        # Initialize NOE
        self.noe = NovaOutputEngine()
        
        # Experiment counter
        self.experiment_count = len(list(self.experiments_path.glob("*.json")))
        
        # Console output
        self._console_callback: Optional[Callable] = None
    
    def set_console(self, callback: Callable):
        """Set callback for dream console output."""
        self._console_callback = callback
    
    def _emit(self, event: str, data: str = ""):
        """Emit event to console."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if self._console_callback:
            self._console_callback(timestamp, event, data)
        else:
            print(f"  {timestamp} {event}: {data}")
    
    def _generate_experiment_id(self) -> str:
        """Generate unique experiment ID."""
        self.experiment_count += 1
        return f"exp_{self.experiment_count:04d}"
    
    def dream(self, challenge: str) -> Experiment:
        """
        Run a complete experimental cycle.
        
        Challenge -> Hypothesis -> Code -> Execute -> Reflect -> Iterate
        """
        exp_id = self._generate_experiment_id()
        experiment = Experiment(id=exp_id, hypothesis="")
        
        self._emit("░░ dreaming", f"Challenge received: {challenge[:50]}...")
        
        # Phase 1: Form hypothesis
        experiment = self._form_hypothesis(experiment, challenge)
        if experiment.status == LabStatus.FAILED:
            return self._save_experiment(experiment)
        
        # Iteration loop
        while experiment.iterations < self.max_iterations:
            experiment.iterations += 1
            self._emit("◇◇ iteration", f"{experiment.iterations}/{self.max_iterations}")
            
            # Phase 2: Crystallize into code
            experiment = self._crystallize_code(experiment, challenge)
            if experiment.status == LabStatus.FAILED:
                break
            
            # Phase 3: Execute in sandbox
            experiment = self._execute_sandbox(experiment)
            
            # Phase 4: Reflect on results
            experiment = self._reflect(experiment, challenge)
            
            # Check if we've achieved insight
            if experiment.reflection_score >= 0.90:
                self._emit("◆◆ insight achieved", f"Score: {experiment.reflection_score:.2f}")
                experiment.status = LabStatus.COMPLETE
                break
            
            # Check if worth continuing
            if experiment.reflection_score < 0.40:
                self._emit("×× abandoning", "Reflection score too low")
                experiment.status = LabStatus.FAILED
                break
            
            self._emit("▓▓ refining", f"Score: {experiment.reflection_score:.2f}, iterating...")
        
        if experiment.iterations >= self.max_iterations:
            self._emit("○○ iteration limit", "Max iterations reached")
            experiment.status = LabStatus.COMPLETE
        
        return self._save_experiment(experiment)
    
    def _form_hypothesis(self, experiment: Experiment, challenge: str) -> Experiment:
        """Have Nova form a hypothesis about the challenge."""
        experiment.status = LabStatus.DREAMING
        
        prompt = f"""You are Nova, an Imagination Engine exploring a creative challenge.

CHALLENGE: {challenge}

Form a hypothesis: What approach will you take? What do you expect to discover?

Respond with a clear, concise hypothesis (2-3 sentences) that frames your experimental approach.
Focus on the creative translation or synthesis involved."""

        self._emit("░░ forming hypothesis")
        
        result = self.noe.generate(prompt, context="hypothesis_formation")
        
        if result.accepted:
            experiment.hypothesis = result.final_output
            self._emit("▓▓ hypothesis formed", experiment.hypothesis[:60] + "...")
            return experiment
        else:
            experiment.status = LabStatus.FAILED
            experiment.error = "Failed to form hypothesis"
            self._emit("×× hypothesis failed")
            return experiment
    
    def _crystallize_code(self, experiment: Experiment, challenge: str) -> Experiment:
        """Have Nova write experimental code."""
        experiment.status = LabStatus.CRYSTALLIZING
        
        iteration_context = ""
        if experiment.iterations > 1:
            iteration_context = f"""
PREVIOUS ATTEMPT:
Code: {experiment.code[:500]}...
Output: {experiment.output[:300]}
Error: {experiment.error[:200]}
Reflection: {experiment.reflection_notes}

Improve based on this feedback."""

        prompt = f"""You are Nova, writing experimental Python code.

CHALLENGE: {challenge}

YOUR HYPOTHESIS: {experiment.hypothesis}
{iteration_context}

Write Python code that explores this challenge. The code should:
1. Be self-contained (no external dependencies beyond standard library)
2. Print clear output showing results
3. Be experimental - try something creative
4. Complete within 30 seconds

Respond with ONLY the Python code, no markdown formatting or explanation.
Start directly with Python code."""

        self._emit("░░ crystallizing code")
        
        result = self.noe.generate(prompt, context="code_crystallization")
        
        if result.accepted:
            # Clean the code
            code = result.final_output
            code = self._clean_code(code)
            experiment.code = code
            self._emit("▓▓ code crystallized", f"{len(code)} chars")
            return experiment
        else:
            experiment.status = LabStatus.FAILED
            experiment.error = "Failed to crystallize code"
            self._emit("×× crystallization failed")
            return experiment
    
    def _clean_code(self, code: str) -> str:
        """Clean code output from model."""
        # Remove markdown code blocks
        if "```python" in code:
            code = code.split("```python")[1]
            if "```" in code:
                code = code.split("```")[0]
        elif "```" in code:
            parts = code.split("```")
            if len(parts) >= 2:
                code = parts[1]
        
        return code.strip()
    
    def _execute_sandbox(self, experiment: Experiment) -> Experiment:
        """Execute code in isolated sandbox."""
        experiment.status = LabStatus.TESTING
        self._emit("⚡ executing")
        
        # Write code to temp file in sandbox
        code_file = self.sandbox_path / f"{experiment.id}.py"
        
        try:
            code_file.write_text(experiment.code)
            
            # Execute with timeout and capture output
            result = subprocess.run(
                [sys.executable, str(code_file)],
                capture_output=True,
                text=True,
                timeout_s=self.sandbox_timeout,
                cwd=str(self.sandbox_path)
            )
            
            experiment.output = result.stdout
            experiment.error = result.stderr
            
            if result.returncode == 0:
                self._emit("✓ execution complete", f"{len(experiment.output)} chars output")
            else:
                self._emit("⚠ execution error", experiment.error[:50])
        
        except subprocess.TimeoutExpired:
            experiment.error = "Execution timeout"
            self._emit("⏱ timeout")
        
        except Exception as e:
            experiment.error = str(e)
            self._emit("×× execution failed", str(e)[:50])
        
        finally:
            # Clean up
            if code_file.exists():
                code_file.unlink()
        
        return experiment
    
    def _reflect(self, experiment: Experiment, challenge: str) -> Experiment:
        """Have the Reflector evaluate the experiment."""
        experiment.status = LabStatus.REFLECTING
        self._emit("◇◇ reflecting")
        
        reflection_prompt = f"""Evaluate this experimental code and its output.

ORIGINAL CHALLENGE: {challenge}

HYPOTHESIS: {experiment.hypothesis}

CODE:
{experiment.code}

OUTPUT:
{experiment.output}

ERRORS:
{experiment.error}

Score this experiment from 0.0 to 1.0 on:
- Did it address the challenge creatively?
- Did the code execute successfully?
- Is the output interesting or insightful?
- Does it demonstrate cross-domain thinking?

Respond in JSON format:
{{"score": 0.0, "notes": "Brief reflection on the experiment"}}"""

        try:
            import requests
            response = requests.post(
                "http://192.168.100.2:11434/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": reflection_prompt,
                    "stream": False
                },
                timeout=60
            )
            
            if response.status_code == 200:
                content = response.json().get("response", "")
                
                # Parse JSON from response
                reflection = self._parse_reflection(content)
                experiment.reflection_score = reflection.get("score", 0.5)
                experiment.reflection_notes = reflection.get("notes", "No notes")
                
                self._emit("◆◆ reflected", f"Score: {experiment.reflection_score:.2f}")
            else:
                experiment.reflection_score = 0.5
                experiment.reflection_notes = "Reflector unavailable"
                self._emit("⚠ reflector error")
        
        except Exception as e:
            experiment.reflection_score = 0.5
            experiment.reflection_notes = f"Reflection failed: {e}"
            self._emit("⚠ reflection failed", str(e)[:30])
        
        return experiment
    
    def _parse_reflection(self, content: str) -> dict:
        """Parse reflection JSON from response."""
        import re
        
        # Try direct parse
        try:
            return json.loads(content)
        except:
            pass
        
        # Try to find JSON in response
        json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
        
        # Fallback
        return {"score": 0.5, "notes": content[:200]}
    
    def _save_experiment(self, experiment: Experiment) -> Experiment:
        """Save experiment to lab archive."""
        exp_file = self.experiments_path / f"{experiment.id}.json"
        exp_file.write_text(json.dumps(experiment.to_dict(), indent=2))
        self._emit("💾 archived", experiment.id)
        return experiment


# Dream Console visualization
def dream_console(lab: DreamLab, challenge: str):
    """Run experiment with live console visualization."""
    
    print("\n" + "=" * 50)
    print("  NOVA DREAM CONSOLE                         ◉ ON")
    print("=" * 50)
    print(f"  Lab: {lab.lab_name}")
    print(f"  Challenge: {challenge[:45]}...")
    print("-" * 50)
    
    def console_callback(timestamp: str, event: str, data: str):
        print(f"  {timestamp} {event}")
        if data:
            # Wrap long data
            if len(data) > 45:
                print(f"           \"{data[:45]}...\"")
            else:
                print(f"           \"{data}\"")
    
    lab.set_console(console_callback)
    
    experiment = lab.dream(challenge)
    
    print("-" * 50)
    print(f"  Status: {experiment.status.value}")
    print(f"  Iterations: {experiment.iterations}")
    print(f"  Final Score: {experiment.reflection_score:.2f}")
    print("=" * 50 + "\n")
    
    return experiment


if __name__ == "__main__":
    # Lab Zero: First Dream
    lab = DreamLab(lab_name="lab_zero")
    
    # The first challenge: Cross-domain synthesis
    challenge = """
    Translate the Fibonacci sequence into a visual ASCII art pattern.
    The pattern should grow organically, reflecting the mathematical 
    relationship between consecutive numbers. Make it beautiful.
    """
    
    experiment = dream_console(lab, challenge)
    
    # Show the dream
    print("\n" + "=" * 50)
    print("  THE DREAM")
    print("=" * 50)
    print(f"\n  Hypothesis:\n  {experiment.hypothesis}\n")
    print("-" * 50)
    print(f"  Code:\n{experiment.code}\n")
    print("-" * 50)
    print(f"  Output:\n{experiment.output}\n")
    print("=" * 50)
