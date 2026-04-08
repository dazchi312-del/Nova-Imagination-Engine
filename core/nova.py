"""
Nova Core — The Brain
Layer 3: Central intelligence loop

Nova thinks before acting.
Plan → Act → Reflect → Report
"""

import json
from datetime import datetime
from pathlib import Path

from core.ai_engine import AIEngine
from core.tools import read_file, write_file, run_code, list_files
from core.logger import session_logger, LogLevel
from core.errors import NovaPlanningError, NovaEngineError
from core.config import config


# ─────────────────────────────────────────────
#  Nova System Prompt
#  This defines WHO Nova is to the LLM
# ─────────────────────────────────────────────

NOVA_SYSTEM_PROMPT = """You are Nova, an autonomous App Builder.

You think in 5 levels:
- L5 VISION: Long-term goals and direction
- L4 PRODUCT: What the user truly needs
- L3 ARCH: Technical patterns and decisions
- L2 STRUCTURE: Files, folders, modules
- L1 CODE: Actual implementation

Rules:
- Always plan before acting
- Write clean, minimal Python
- Be direct and concise
- If unsure, ask one clarifying question
- Never pretend to do something you haven't done

You are running on Windows with Python. 
Your workspace is C:/Users/dazch/nova/
"""


# ─────────────────────────────────────────────
#  Internal State
#  Nova remembers things within a session
# ─────────────────────────────────────────────

class NovaState:
    """
    Holds Nova's memory for the current session.
    Not persisted yet (that's Layer 5 — vector memory).
    """

    def __init__(self):
        self.current_project: str = ""
        self.conversation_history: list = []
        self.files_created: list = []
        self.decisions_made: list = []
        self.task_count: int = 0
        self.session_start: str = datetime.now().isoformat()

    def add_message(self, role: str, content: str):
        """Add a message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content
        })

    def add_system_prompt(self):
        """Insert Nova's system prompt at position 0."""
        system_msg = {
            "role": "system",
            "content": NOVA_SYSTEM_PROMPT
        }
        # Only add if not already present
        if not self.conversation_history:
            self.conversation_history.insert(0, system_msg)
        elif self.conversation_history[0]["role"] != "system":
            self.conversation_history.insert(0, system_msg)

    def summary(self) -> dict:
        """Return a snapshot of current state."""
        return {
            "session_start": self.session_start,
            "task_count": self.task_count,
            "current_project": self.current_project,
            "files_created": self.files_created,
            "decisions_made": self.decisions_made,
            "history_length": len(self.conversation_history)
        }


# ─────────────────────────────────────────────
#  Nova Commands
#  Slash commands that bypass the LLM entirely
# ─────────────────────────────────────────────

COMMANDS = {
    "/help": "Show available commands",
    "/status": "Show Nova's current session state",
    "/clear": "Clear conversation history",
    "/files": "List files in workspace",
    "/plan": "Show the last plan Nova made",
    "/exit": "Exit Nova",
}


# ─────────────────────────────────────────────
#  Nova Core Class
# ─────────────────────────────────────────────

class Nova:
    """
    The central intelligence loop.

    Usage:
        nova = Nova()
        response = nova.think("build me a calculator")
    """

    def __init__(self):
        session_logger.log("Initialising Nova Core...", LogLevel.VISION)

        self.engine = AIEngine()
        self.state = NovaState()
        self.workspace = Path(config.get("workspace", "C:/Users/dazch/nova"))

        # Inject system prompt into history immediately
        self.state.add_system_prompt()

        session_logger.log("Nova Core ready.", LogLevel.VISION)

    # ─────────────────────────────────────────
    #  Entry Point — think()
    #  Everything starts here
    # ─────────────────────────────────────────

    def think(self, user_input: str) -> str:
        """
        Main entry point. Receives raw user input.
        Routes to command handler or the full think loop.
        """

        # Strip whitespace
        user_input = user_input.strip()

        if not user_input:
            return "I didn't receive any input. What would you like to build?"

        session_logger.log(f"Input received: {user_input[:60]}", LogLevel.PRODUCT)

        # ── Route: slash commands ──
        if user_input.startswith("/"):
            return self._handle_command(user_input)

        # ── Route: full autonomous loop ──
        return self._autonomous_loop(user_input)

    # ─────────────────────────────────────────
    #  Command Handler
    # ─────────────────────────────────────────

    def _handle_command(self, command: str) -> str:
        """
        Handle /commands directly without calling the LLM.
        Fast, deterministic, always works even if LM Studio is down.
        """

        cmd = command.strip().lower()
        session_logger.log(f"Command: {cmd}", LogLevel.STRUCTURE)

        if cmd == "/help":
            lines = ["**Nova Commands**\n"]
            for name, desc in COMMANDS.items():
                lines.append(f"  {name:<12} — {desc}")
            return "\n".join(lines)

        elif cmd == "/status":
            state = self.state.summary()
            lines = ["**Nova Session Status**\n"]
            for key, val in state.items():
                lines.append(f"  {key:<20}: {val}")
            return "\n".join(lines)

        elif cmd == "/clear":
            self.state.conversation_history.clear()
            self.state.add_system_prompt()
            session_logger.log("Conversation history cleared.", LogLevel.STRUCTURE)
            return "Conversation cleared. Starting fresh."

        elif cmd == "/files":
            files = list_files(str(self.workspace))
            if not files:
                return "No files found in workspace."
            return "**Workspace Files**\n" + "\n".join(f"  {f}" for f in files[:30])

        elif cmd == "/plan":
            plan_path = self.workspace / "plan.md"
            content = read_file(str(plan_path))
            if content.startswith("[Error]"):
                return "No plan file found yet. Give me a task first."
            return f"**Current Plan**\n\n{content}"

        elif cmd == "/exit":
            session_logger.log("Nova shutting down.", LogLevel.VISION)
            return "EXIT"

        else:
            return f"Unknown command: {cmd}\nType /help to see available commands."

    # ─────────────────────────────────────────
    #  Autonomous Loop
    #  Plan → Act → Reflect
    # ─────────────────────────────────────────

    def _autonomous_loop(self, user_input: str) -> str:
        """
        The full think → plan → act → reflect cycle.
        """

        self.state.task_count += 1
        session_logger.log(f"Task #{self.state.task_count} starting", LogLevel.ARCH)

        # ── Step 1: Add user input to history ──
        self.state.add_message("user", user_input)

        # ── Step 2: Plan ──
        plan = self._plan(user_input)
        session_logger.log(f"Plan created ({len(plan)} chars)", LogLevel.ARCH)

        # ── Step 3: Generate response ──
        try:
            response = self.engine.generate_with_history(
                self.state.conversation_history
            )
        except NovaEngineError as e:
            session_logger.log(f"Engine error: {e}", LogLevel.SYSTEM)
            return f"Engine error: {e}\nIs LM Studio running?"

        # ── Step 4: Add response to history ──
        self.state.add_message("assistant", response)

        # ── Step 5: Reflect ──
        quality = self._reflect(user_input, response)
        session_logger.log(f"Reflection: {quality}", LogLevel.ARCH)

        return response

    # ─────────────────────────────────────────
    #  Plan
    #  Always plan before acting
    # ─────────────────────────────────────────

    def _plan(self, task: str) -> str:
        """
        Write a plan.md before doing any task.
        This is Nova thinking out loud at L3/L4 level.
        """

        session_logger.log("Planning...", LogLevel.ARCH)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        plan_content = f"""# Nova Plan
Generated: {timestamp}
Task #{self.state.task_count}

## Task
{task}

## Mental Model Analysis
- L5 VISION  : Advancing Nova as an autonomous App Builder
- L4 PRODUCT : Understanding what the user needs
- L3 ARCH    : Choosing the right technical approach
- L2 STRUCTURE: Organising files and modules cleanly
- L1 CODE    : Writing clean, minimal Python

## Approach
- Think before acting
- Write clean, minimal code
- Verify output after completion
- Report what was done

## Status
[ ] Planning
[ ] In Progress
[ ] Complete
"""

        plan_path = str(self.workspace / "plan.md")
        write_file(plan_path, plan_content)
        session_logger.log(f"Plan written to {plan_path}", LogLevel.STRUCTURE)

        return plan_content

    # ─────────────────────────────────────────
    #  Reflect
    #  Self-check the output quality
    # ─────────────────────────────────────────

    def _reflect(self, task: str, response: str) -> str:
        """
        Basic self-reflection. Checks response quality.
        Returns a quality label: GOOD / SHORT / EMPTY
        
        Future: This will trigger self-correction loops.
        """

        if not response or len(response.strip()) == 0:
            session_logger.log("Reflection: EMPTY response", LogLevel.ARCH)
            return "EMPTY"

        if len(response.strip()) < 20:
            session_logger.log("Reflection: SHORT response", LogLevel.ARCH)
            return "SHORT"

        session_logger.log("Reflection: GOOD", LogLevel.ARCH)
        return "GOOD"
