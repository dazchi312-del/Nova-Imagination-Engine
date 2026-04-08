"""
Nova Builder — Layer 4
Autonomous build loop: Write → Run → Reflect → Fix
The creative engine
"""

from core.executor import Executor, ExecutionResult
from core.tools import write_file, read_file
from core.logger import log
from pathlib import Path


class BuildResult:
    def __init__(self, success: bool, code: str, output: str,
                 error: str, attempts: int, filepath: str):
        self.success = success
        self.code = code
        self.output = output
        self.error = error
        self.attempts = attempts
        self.filepath = filepath

    def summary(self) -> str:
        status = "✅ Built successfully" if self.success else "❌ Build failed"
        return (
            f"{status}\n"
            f"File: {self.filepath}\n"
            f"Attempts: {self.attempts}\n"
            f"Output: {self.output or 'none'}\n"
            f"Error: {self.error or 'none'}"
        )


class Builder:
    MAX_ATTEMPTS = 3

    def __init__(self, workspace: str = "C:/Users/dazch/nova"):
        self.workspace = Path(workspace)
        self.executor = Executor(workspace)
        log("ARCH", "Builder ready")

    def build(self, code: str, filename: str, ai_engine=None) -> BuildResult:
        filepath = str(self.workspace / filename)
        attempts = 0
        current_code = code
        last_error = ""
        last_output = ""

        log("ARCH", f"Build starting: {filename}")

        while attempts < self.MAX_ATTEMPTS:
            attempts += 1
            log("ARCH", f"Build attempt {attempts}/{self.MAX_ATTEMPTS}")

            write_file(filepath, current_code)

            result = self.executor.run_file(filepath)
            last_output = result.output
            last_error = result.error

            if result.success:
                log("ARCH", f"Build succeeded on attempt {attempts}")
                return BuildResult(
                    success=True,
                    code=current_code,
                    output=last_output,
                    error="",
                    attempts=attempts,
                    filepath=filepath
                )

            log("ARCH", f"Build failed: {result.error[:100]}")

            if ai_engine and attempts < self.MAX_ATTEMPTS:
                log("ARCH", "Asking AI to fix the error...")
                current_code = self._fix_with_ai(
                    current_code, result.error, ai_engine
                )
            else:
                break

        log("ARCH", f"Build failed after {attempts} attempts")
        return BuildResult(
            success=False,
            code=current_code,
            output=last_output,
            error=last_error,
            attempts=attempts,
            filepath=filepath
        )

    def _fix_with_ai(self, code: str, error: str, ai_engine) -> str:
        prompt = (
            f"This Python code has an error. Fix it and return ONLY the corrected "
            f"Python code with no explanation, no markdown, no backticks.\n\n"
            f"CODE:\n{code}\n\n"
            f"ERROR:\n{error}\n\n"
            f"Return only the fixed Python code:"
        )

        fixed = ai_engine.generate(prompt, temperature=0.3)

        fixed = fixed.strip()
        if fixed.startswith("```"):
            lines = fixed.split("\n")
            fixed = "\n".join(lines[1:-1])

        return fixed
