"""
Nova Agent — Layer 5
Orchestrates the full autonomous loop:
Goal -> Plan -> Build -> Execute -> Verify -> Fix -> Ship
"""

from core.logger import session_logger, LogLevel
from core.ai_engine import AIEngine
from core.planner import Planner, BuildPlan, BuildStep
from core.builder import Builder
from core.executor import Executor


class Agent:
    def __init__(self):
        session_logger.log("Agent initializing...", LogLevel.ARCH)
        self.ai = AIEngine()
        self.planner = Planner(self.ai)
        self.builder = Builder()
        self.executor = Executor()
        session_logger.log("Agent ready", LogLevel.ARCH)

    def _generate_code(self, task: str, filename: str) -> str:
        import re
        prompt = f"""Write Python code for this task: {task}
Output ONLY raw Python code. No explanation. No markdown. No code fences."""
        
        raw = self.ai.generate(prompt)
        
        # Strip markdown fences robustly
        cleaned = re.sub(r'^```[\w\s]*\n?', '', raw.strip())
        cleaned = re.sub(r'\n?```[\w\s]*$', '', cleaned)
        return cleaned.strip()



    def run(self, goal: str) -> str:
        session_logger.log(f"Agent received goal: {goal}", LogLevel.VISION)
        print(f"\n Goal: {goal}\n")

        # Phase 1: Plan
        print("Planning...")
        plan = self.planner.plan(goal)
        print(plan.summary())

        # Phase 2: Build + Execute each step
        for step in plan.steps:
            print(f"\nBuilding Step {step.index}: {step.description}")

            # Generate code from description
            print(f"  Generating code...")
            raw_code = self._generate_code(step.description, step.filename)
            if not raw_code:
                print(f"  Code generation failed for step {step.index}")
                continue

            # Build (validate + write)
            result = self.builder.build(raw_code, step.filename)
            step.code = raw_code
            step.output = result.output
            step.completed = result.success

            if result.success:
                print(f"  Success:\n{result.output}")
            else:
                print(f"  Failed:\n{result.output}")

                # Fix attempt
                print(f"  Attempting fix...")
                fixed_result = self.builder.build(raw_code, step.filename, ai_engine=self.ai)
                step.output = fixed_result.output
                step.completed = fixed_result.success
                if fixed_result.success:
                    print(f"  Fixed and verified:\n{fixed_result.output}")
                else:
                    print(f"  Fix failed:\n{fixed_result.output}")

        # Phase 3: Report
        completed = sum(1 for s in plan.steps if s.completed)
        total = len(plan.steps)
        print(f"\nResult: {completed}/{total} steps completed")
        session_logger.log(f"Goal complete: {completed}/{total} steps", LogLevel.VISION)

        return plan.summary()
