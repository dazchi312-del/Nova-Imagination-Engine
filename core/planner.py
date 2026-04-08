"""
Nova Planner — Layer 5
Breaks a plain English goal into ordered build steps
"""

from dataclasses import dataclass, field
from typing import List
from core.logger import session_logger, LogLevel
from core.ai_engine import AIEngine


@dataclass
class BuildStep:
    index: int
    description: str
    filename: str
    code: str = ""
    completed: bool = False
    output: str = ""


@dataclass
class BuildPlan:
    goal: str
    steps: List[BuildStep] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"Goal: {self.goal}", "Steps:"]
        for step in self.steps:
            status = "✅" if step.completed else "⬜"
            lines.append(f"  {status} {step.index}. {step.description} → {step.filename}")
        return "\n".join(lines)


class Planner:
    def __init__(self, ai: AIEngine):
        self.ai = ai
        session_logger.log("Planner ready", LogLevel.ARCH)

    def plan(self, goal: str) -> BuildPlan:
        session_logger.log(f"Planning goal: {goal}", LogLevel.VISION)

        prompt = f"""You are Nova, an autonomous Python app builder.

Your job is to break this goal into clear build steps.

Goal: {goal}

Rules:
- Each step produces exactly ONE Python file
- Keep it simple — 1 to 3 steps maximum
- Each file must be self-contained and runnable
- Respond ONLY in this exact format, nothing else:

STEP 1
description: <what this step does>
filename: <output_filename.py>

STEP 2
description: <what this step does>
filename: <output_filename.py>"""

        response = self.ai.generate(prompt)
        session_logger.log(f"Plan received from AI", LogLevel.ARCH)

        return self._parse_plan(goal, response)

    def _parse_plan(self, goal: str, response: str) -> BuildPlan:
        plan = BuildPlan(goal=goal)
        current = {}
        index = 0

        for line in response.strip().splitlines():
            line = line.strip()
            if line.upper().startswith("STEP"):
                if current:
                    plan.steps.append(BuildStep(
                        index=index,
                        description=current.get("description", ""),
                        filename=current.get("filename", f"step_{index}.py")
                    ))
                index += 1
                current = {}
            elif line.startswith("description:"):
                current["description"] = line.split(":", 1)[1].strip()
            elif line.startswith("filename:"):
                current["filename"] = line.split(":", 1)[1].strip()

        if current:
            plan.steps.append(BuildStep(
                index=index,
                description=current.get("description", ""),
                filename=current.get("filename", f"step_{index}.py")
            ))

        session_logger.log(f"Plan parsed: {len(plan.steps)} steps", LogLevel.ARCH)
        return plan
