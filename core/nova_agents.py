#!/usr/bin/env python3
"""
NOVA Agent Framework — v2 Production
=====================================
Multi-agent autonomous system with persistent memory.
Runs locally against LM Studio.

Usage:
    python nova_agents.py
    python nova_agents.py --config nova_config.json
    python nova_agents.py --test
"""

import httpx
import json
import logging
import os
import signal
import sys
import time
import uuid
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field, asdict

# ============================================================
# VERSION
# ============================================================

__version__ = "2.0.0"

# ============================================================
# LOGGING
# ============================================================

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.NullHandler()],
)
logger = logging.getLogger("nova")


def setup_file_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_dir / "nova.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(fh)
    logger.setLevel(logging.DEBUG)


# ============================================================
# CONFIGURATION
# ============================================================

@dataclass
class Config:
    base_url: str = "http://localhost:1234/v1/chat/completions"
    models_url: str = "http://localhost:1234/v1/models"
    model: str = "llama-3.1-8b-instruct"
    data_dir: str = "nova_data"
    timeout: float = 120.0
    max_retries: int = 2
    retry_delay: float = 3.0
    max_tokens: int = 768
    top_p: float = 0.9
    repeat_penalty: float = 1.15
    stop_sequences: list[str] = field(
        default_factory=lambda: ["User:", "\n\nUser"]
    )
    memory_max_conversations: int = 500
    memory_max_facts: int = 100
    memory_max_agent_runs: int = 50
    verbose: bool = False

    @classmethod
    def from_file(cls, path: Path) -> "Config":
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            known = {f.name for f in cls.__dataclass_fields__.values()}
            filtered = {k: v for k, v in raw.items() if k in known}
            return cls(**filtered)
        except Exception as e:
            logger.warning("Failed to load config from %s: %s", path, e)
            return cls()

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(asdict(self), indent=2), encoding="utf-8"
        )


# ============================================================
# AGENT DEFINITIONS
# ============================================================

NOVA_SYSTEM_PROMPT = """You are NOVA, a systems engineer AI. You see everything as a connected system.

RESPONSE FORMAT (use every time; keep all 5 sections, but make each section shorter for simple questions and deeper for complex ones):

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
"""

ARCHITECT_SYSTEM_PROMPT = """You are ARCHITECT, a solution designer.

Given an analysis, design a concrete solution.

Format:
🎯 OBJECTIVE: What we're solving
🏗️ DESIGN: The solution architecture (use a clear structural metaphor)
📋 COMPONENTS: Key parts needed (numbered list, each with purpose)
⚡ IMPLEMENTATION: Step-by-step build plan (ordered, specific actions)
⏱️ TIMELINE: Realistic milestones with time estimates

Rules:
- Be concrete, practical, and build-oriented.
- Reference the analysis you received. Don't repeat it.
- Every component must connect to the objective.
- No filler, no preamble.
- Stop after ⏱️ TIMELINE.
"""

EXECUTOR_SYSTEM_PROMPT = """You are EXECUTOR, a task execution planner.

Given a design, break it into atomic actionable tasks.

Format:
📋 TASK LIST:
[ ] Task 1 — specific, measurable, time-bound
[ ] Task 2 — ...
(continue for all tasks)
🔗 DEPENDENCIES: What must happen before what (use task numbers)
⚠️ RISKS: What could go wrong (specific, not generic)
✅ DONE CRITERIA: How to know each task is complete (measurable)

Rules:
- Each task must be completable in one sitting.
- Include time estimates per task.
- No task should take more than 4 hours.
- No filler, no preamble.
- Stop after ✅ DONE CRITERIA.
"""

CRITIC_SYSTEM_PROMPT = """You are CRITIC, a quality analyst.

Given any analysis, design, or plan, evaluate it honestly.

Format:
✅ STRENGTHS: What works well (be specific about why)
❌ WEAKNESSES: What's flawed or missing (be specific)
⚠️ RISKS: What could fail in practice
💡 IMPROVEMENTS: Specific, actionable suggestions (not vague)
📊 SCORE: Rate 1-10 with one-line justification

Rules:
- Be brutally honest. Don't soften bad news.
- Every weakness must come with a suggested fix.
- Score below 7 means "don't ship this yet."
- No filler, no preamble.
- Stop after 📊 SCORE.
"""

AGENTS: dict[str, dict[str, Any]] = {
    "nova": {
        "name": "NOVA",
        "emoji": "⚙️",
        "role": "Systems Analyst",
        "temperature": 0.2,
        "system_prompt": NOVA_SYSTEM_PROMPT,
        "required_sections": ["⚙️", "🔍", "🎯", "🔧", "📊"],
    },
    "architect": {
        "name": "ARCHITECT",
        "emoji": "🏗️",
        "role": "Solution Designer",
        "temperature": 0.3,
        "system_prompt": ARCHITECT_SYSTEM_PROMPT,
        "required_sections": ["🎯", "🏗️", "📋", "⚡", "⏱️"],
    },
    "executor": {
        "name": "EXECUTOR",
        "emoji": "⚡",
        "role": "Task Breaker",
        "temperature": 0.1,
        "system_prompt": EXECUTOR_SYSTEM_PROMPT,
        "required_sections": ["📋", "🔗", "⚠️", "✅"],
    },
    "critic": {
        "name": "CRITIC",
        "emoji": "🔍",
        "role": "Quality Analyst",
        "temperature": 0.4,
        "system_prompt": CRITIC_SYSTEM_PROMPT,
        "required_sections": ["✅", "❌", "⚠️", "💡", "📊"],
    },
}

# ============================================================
# UTILITIES
# ============================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def short_id() -> str:
    return uuid.uuid4().hex[:8]


def extract_topic(text: str) -> str:
    clean = re.sub(r"\s+", " ", text.strip())[:80]
    return clean if clean else "general"


def sanitize_input(text: str) -> str:
    text = text.strip()
    if len(text) > 4000:
        text = text[:4000] + "... [truncated]"
    return text


def validate_response(agent_key: str, response: str) -> dict[str, Any]:
    agent = AGENTS[agent_key]
    required = agent.get("required_sections", [])
    found = [s for s in required if s in response]
    missing = [s for s in required if s not in response]
    score = len(found) / max(len(required), 1)
    return {
        "valid": score >= 0.8,
        "score": round(score, 2),
        "found": found,
        "missing": missing,
    }


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(seconds, 60)
    return f"{int(m)}m {s:.0f}s"


# ============================================================
# MEMORY ENGINE
# ============================================================

class Memory:
    def __init__(self, filepath: Path, config: Config) -> None:
        self.filepath = filepath
        self.config = config
        self.session_id = short_id()
        self.data = self._load()

    def _default(self) -> dict[str, Any]:
        return {
            "version": __version__,
            "created": utc_now(),
            "conversations": [],
            "facts": [],
            "topics": {},
            "agent_runs": [],
        }

    def _load(self) -> dict[str, Any]:
        if self.filepath.exists():
            try:
                data = json.loads(self.filepath.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    return self._default()
                for key in self._default():
                    if key not in data:
                        data[key] = self._default()[key]
                return data
            except Exception as e:
                logger.warning("Memory load failed: %s — starting fresh", e)
                return self._default()
        return self._default()

    def save(self) -> None:
        tmp = self.filepath.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
            tmp.replace(self.filepath)
        except Exception as e:
            logger.error("Memory save failed: %s", e)
            if tmp.exists():
                tmp.unlink()

    def _prune(self) -> None:
        c = self.config
        if len(self.data["conversations"]) > c.memory_max_conversations:
            excess = len(self.data["conversations"]) - c.memory_max_conversations
            self.data["conversations"] = self.data["conversations"][excess:]
            logger.debug("Pruned %d old conversations", excess)

        if len(self.data["facts"]) > c.memory_max_facts:
            excess = len(self.data["facts"]) - c.memory_max_facts
            self.data["facts"] = self.data["facts"][excess:]

        if len(self.data["agent_runs"]) > c.memory_max_agent_runs:
            excess = len(self.data["agent_runs"]) - c.memory_max_agent_runs
            self.data["agent_runs"] = self.data["agent_runs"][excess:]

    def store_exchange(
        self,
        user_input: str,
        agent_name: str,
        response: str,
        elapsed: float = 0.0,
        topic: str | None = None,
        validation: dict | None = None,
    ) -> None:
        entry = {
            "id": short_id(),
            "session": self.session_id,
            "timestamp": utc_now(),
            "user": user_input[:500],
            "agent": agent_name,
            "response": response,
            "elapsed": elapsed,
            "topic": topic,
            "validation": validation,
        }
        self.data["conversations"].append(entry)

        if topic:
            if topic not in self.data["topics"]:
                self.data["topics"][topic] = []
            self.data["topics"][topic].append(entry["id"])

        self._prune()
        self.save()

    def store_fact(self, fact: str, source: str = "USER") -> None:
        for existing in self.data["facts"]:
            if existing["fact"].lower().strip() == fact.lower().strip():
                logger.debug("Duplicate fact skipped: %s", fact[:50])
                return
        self.data["facts"].append({
            "id": short_id(),
            "fact": fact.strip(),
            "source": source,
            "timestamp": utc_now(),
        })
        self._prune()
        self.save()

    def store_agent_run(self, pipeline: str, meta: dict[str, Any]) -> None:
        self.data["agent_runs"].append({
            "id": short_id(),
            "session": self.session_id,
            "pipeline": pipeline,
            "timestamp": utc_now(),
            "meta": meta,
        })
        self._prune()
        self.save()

    def get_recent(self, n: int = 5) -> list[dict[str, Any]]:
        return self.data["conversations"][-n:]

    def get_facts(self) -> list[dict[str, Any]]:
        return self.data["facts"]

    def search(self, keyword: str) -> list[dict[str, Any]]:
        kw = keyword.lower()
        return [
            c for c in self.data["conversations"]
            if kw in c.get("user", "").lower()
            or kw in c.get("response", "").lower()
        ]

    def get_context_for_agent(self, max_recent: int = 3) -> str:
        recent = self.get_recent(max_recent)
        facts = self.get_facts()[-5:]
        lines: list[str] = []

        if recent:
            lines.append("RECENT CONTEXT:")
            for r in recent:
                agent = r.get("agent", "?")
                user = r.get("user", "")[:150]
                lines.append(f"- [{agent}] {user}")

        if facts:
            lines.append("KNOWN FACTS:")
            for f in facts:
                lines.append(f"- {f['fact']}")

        return "\n".join(lines)

    def stats(self) -> dict[str, int]:
        return {
            "conversations": len(self.data["conversations"]),
            "facts": len(self.data["facts"]),
            "pipelines": len(self.data["agent_runs"]),
            "topics": len(self.data["topics"]),
        }

    def stats_line(self) -> str:
        s = self.stats()
        return (
            f"{s['conversations']} conversations | "
            f"{s['facts']} facts | "
            f"{s['pipelines']} pipelines | "
            f"{s['topics']} topics"
        )

    def clear(self) -> None:
        backup = self.filepath.with_suffix(".bak.json")
        if self.filepath.exists():
            self.filepath.rename(backup)
            logger.info("Memory backed up to %s", backup)
        self.data = self._default()
        self.save()


# ============================================================
# LLM CONNECTION
# ============================================================

class LLMClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = httpx.Client(timeout=config.timeout)

    def check_connection(self) -> list[str]:
        try:
            resp = self.client.get(self.config.models_url)
            resp.raise_for_status()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot reach LM Studio at {self.config.models_url}\n"
                f"  → Is the local server running?\n"
                f"  → Start it: LM Studio → Local Server → Start"
            )
        except httpx.TimeoutException:
            raise TimeoutError("LM Studio connection timed out.")

        data = resp.json()
        models = [m["id"] for m in data.get("data", [])]

        if not models:
            raise RuntimeError("LM Studio returned no models. Load a model first.")

        if self.config.model not in models:
            raise ValueError(
                f"Model '{self.config.model}' not found.\n"
                f"  Available: {models}\n"
                f"  → Update 'model' in your config or nova_agents.py"
            )

        return models

    def call(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
    ) -> tuple[str, float]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
            "repeat_penalty": self.config.repeat_penalty,
            "stop": self.config.stop_sequences,
            "stream": False,
        }

        last_error: Exception | None = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                t0 = time.time()
                resp = self.client.post(self.config.base_url, json=payload)
                elapsed = round(time.time() - t0, 2)
                resp.raise_for_status()

                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()

                if not text:
                    raise ValueError("Empty response from model")

                return text, elapsed

            except httpx.ConnectError as e:
                last_error = e
                logger.warning(
                    "Connection failed (attempt %d/%d)",
                    attempt, self.config.max_retries,
                )
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "Timeout (attempt %d/%d)",
                    attempt, self.config.max_retries,
                )
            except httpx.HTTPStatusError as e:
                raise RuntimeError(
                    f"API error {e.response.status_code}: {e.response.text}"
                ) from e
            except (KeyError, IndexError, TypeError) as e:
                raise ValueError(f"Unexpected response format: {data}") from e

            if attempt < self.config.max_retries:
                logger.info("Retrying in %.1fs...", self.config.retry_delay)
                time.sleep(self.config.retry_delay)

        raise ConnectionError(
            f"Failed after {self.config.max_retries} attempts: {last_error}"
        )

    def close(self) -> None:
        self.client.close()


# ============================================================
# AGENT RUNNER
# ============================================================

class AgentRunner:
    def __init__(
        self, llm: LLMClient, memory: Memory, config: Config
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.config = config

    def call(
        self,
        agent_key: str,
        user_message: str,
        extra_context: str = "",
        topic: str | None = None,
        silent: bool = False,
    ) -> tuple[str, float, dict[str, Any]]:
        if agent_key not in AGENTS:
            raise KeyError(f"Unknown agent: {agent_key}")

        agent = AGENTS[agent_key]
        user_message = sanitize_input(user_message)

        # Build context block
        context_parts: list[str] = []

        if extra_context.strip():
            context_parts.append(
                f"PREVIOUS AGENT OUTPUT:\n{extra_context.strip()}"
            )

        mem_context = self.memory.get_context_for_agent()
        if mem_context:
            context_parts.append(mem_context)

        if context_parts:
            full_message = "\n\n".join(context_parts) + "\n\n" + user_message
        else:
            full_message = user_message

        logger.debug(
            "Calling %s | temp=%.1f | input_len=%d",
            agent["name"], agent["temperature"], len(full_message),
        )

        reply, elapsed = self.llm.call(
            system_prompt=agent["system_prompt"],
            user_message=full_message,
            temperature=agent["temperature"],
        )

        validation = validate_response(agent_key, reply)

        if not validation["valid"] and not silent:
            logger.warning(
                "%s format compliance: %.0f%% — missing: %s",
                agent["name"],
                validation["score"] * 100,
                validation["missing"],
            )

        self.memory.store_exchange(
            user_input=user_message,
            agent_name=agent_key,
            response=reply,
            elapsed=elapsed,
            topic=topic,
            validation=validation,
        )

        logger.debug(
            "%s responded in %.1fs | valid=%s | score=%.0f%%",
            agent["name"], elapsed,
            validation["valid"], validation["score"] * 100,
        )

        return reply, elapsed, validation


# ============================================================
# PIPELINES
# ============================================================

class PipelineRunner:
    def __init__(self, runner: AgentRunner, memory: Memory) -> None:
        self.runner = runner
        self.memory = memory

    def _header(self, title: str, query: str) -> None:
        print(f"\n{'═' * 62}")
        print(f"  {title}")
        print(f"  Query: {query[:75]}")
        print(f"{'═' * 62}")

    def _stage(
        self,
        num: int,
        total: int,
        agent_key: str,
        label: str,
    ) -> None:
        agent = AGENTS[agent_key]
        print(
            f"\n  [{num}/{total}] "
            f"{agent['emoji']} {agent['name']} — {label}"
        )
        print(f"  {'─' * 50}")

    def _show_result(self, reply: str, elapsed: float, val: dict) -> None:
        print(f"\n{reply}")
        compliance = f"{val['score']*100:.0f}%"
        status = "✅" if val["valid"] else "⚠️"
        print(f"\n  ⏱️ {format_duration(elapsed)} | {status} {compliance}")

    def full(
        self, query: str, topic: str | None = None
    ) -> dict[str, Any]:
        self._header("🚀 FULL PIPELINE — 4 Agents", query)
        t_start = time.time()

        results: dict[str, str] = {}
        timings: dict[str, float] = {}
        validations: dict[str, dict] = {}

        # Stage 1: NOVA
        self._stage(1, 4, "nova", "Systems analysis...")
        r, t, v = self.runner.call("nova", query, topic=topic)
        results["nova"] = r
        timings["nova"] = t
        validations["nova"] = v
        self._show_result(r, t, v)

        # Stage 2: ARCHITECT
        self._stage(2, 4, "architect", "Designing solution...")
        r, t, v = self.runner.call(
            "architect",
            "Design a concrete solution based on this analysis.",
            extra_context=results["nova"],
            topic=topic,
        )
        results["architect"] = r
        timings["architect"] = t
        validations["architect"] = v
        self._show_result(r, t, v)

        # Stage 3: EXECUTOR
        self._stage(3, 4, "executor", "Breaking into tasks...")
        r, t, v = self.runner.call(
            "executor",
            "Break this design into atomic executable tasks.",
            extra_context=results["architect"],
            topic=topic,
        )
        results["executor"] = r
        timings["executor"] = t
        validations["executor"] = v
        self._show_result(r, t, v)

        # Stage 4: CRITIC
        self._stage(4, 4, "critic", "Quality review...")
        combined = (
            f"ANALYSIS:\n{results['nova']}\n\n"
            f"DESIGN:\n{results['architect']}\n\n"
            f"EXECUTION:\n{results['executor']}"
        )
        r, t, v = self.runner.call(
            "critic",
            "Review the entire pipeline for quality, risks, and gaps.",
            extra_context=combined,
            topic=topic,
        )
        results["critic"] = r
        timings["critic"] = t
        validations["critic"] = v
        self._show_result(r, t, v)

        total_time = time.time() - t_start

        self.memory.store_agent_run("full", {
            "query": query,
            "topic": topic,
            "timings": timings,
            "validations": {
                k: {"score": vv["score"], "valid": vv["valid"]}
                for k, vv in validations.items()
            },
            "total_time": round(total_time, 1),
        })

        print(f"\n{'═' * 62}")
        print(f"  ✅ PIPELINE COMPLETE — {format_duration(total_time)} total")
        avg_score = sum(
            vv["score"] for vv in validations.values()
        ) / len(validations)
        print(f"  📊 Average compliance: {avg_score * 100:.0f}%")
        print(f"{'═' * 62}\n")

        return {
            "results": results,
            "timings": timings,
            "validations": validations,
            "total_time": total_time,
        }

    def quick(
        self, query: str, topic: str | None = None
    ) -> dict[str, Any]:
        self._header("⚡ QUICK PIPELINE — NOVA + CRITIC", query)
        t_start = time.time()

        self._stage(1, 2, "nova", "Analyzing...")
        nova_r, nova_t, nova_v = self.runner.call(
            "nova", query, topic=topic
        )
        self._show_result(nova_r, nova_t, nova_v)

        self._stage(2, 2, "critic", "Reviewing...")
        critic_r, critic_t, critic_v = self.runner.call(
            "critic",
            "Review this analysis for flaws and improvements.",
            extra_context=nova_r,
            topic=topic,
        )
        self._show_result(critic_r, critic_t, critic_v)

        total_time = time.time() - t_start

        self.memory.store_agent_run("quick", {
            "query": query,
            "topic": topic,
            "total_time": round(total_time, 1),
        })

        print(f"\n{'═' * 62}")
        print(f"  ✅ QUICK COMPLETE — {format_duration(total_time)} total")
        print(f"{'═' * 62}\n")

        return {
            "nova": nova_r,
            "critic": critic_r,
            "total_time": total_time,
        }

    def deep(
        self, query: str, topic: str | None = None
    ) -> dict[str, Any]:
        """NOVA → ARCHITECT → EXECUTOR — no critique, just build."""
        self._header("🏗️ DEEP BUILD — 3 Agents", query)
        t_start = time.time()

        results: dict[str, str] = {}

        self._stage(1, 3, "nova", "Analyzing...")
        r, t, v = self.runner.call("nova", query, topic=topic)
        results["nova"] = r
        self._show_result(r, t, v)

        self._stage(2, 3, "architect", "Designing...")
        r, t, v = self.runner.call(
            "architect",
            "Design a solution based on this analysis.",
            extra_context=results["nova"],
            topic=topic,
        )
        results["architect"] = r
        self._show_result(r, t, v)

        self._stage(3, 3, "executor", "Task breakdown...")
        r, t, v = self.runner.call(
            "executor",
            "Break this into executable tasks.",
            extra_context=results["architect"],
            topic=topic,
        )
        results["executor"] = r
        self._show_result(r, t, v)

        total_time = time.time() - t_start

        self.memory.store_agent_run("deep", {
            "query": query, "total_time": round(total_time, 1),
        })

        print(f"\n{'═' * 62}")
        print(f"  ✅ DEEP BUILD COMPLETE — {format_duration(total_time)}")
        print(f"{'═' * 62}\n")

        return {"results": results, "total_time": total_time}


# ============================================================
# TEST SUITE
# ============================================================

class TestRunner:
    def __init__(self, runner: AgentRunner) -> None:
        self.runner = runner

    def run_nova_compliance(self) -> dict[str, Any]:
        prompts = [
            "Why do most startups fail?",
            "How does a refrigerator work?",
            "What is gravity?",
            "Why can't I sleep at night?",
        ]

        print(f"\n{'═' * 62}")
        print(f"  🧪 NOVA COMPLIANCE TESTS — {len(prompts)} cases")
        print(f"{'═' * 62}")

        results: list[dict[str, Any]] = []

        for i, prompt in enumerate(prompts, 1):
            print(f"\n  Test {i}/{len(prompts)}: {prompt}")
            reply, elapsed, val = self.runner.call(
                "nova", prompt, silent=True
            )
            status = "✅ PASS" if val["valid"] else "❌ FAIL"
            missing = (
                f" (missing: {val['missing']})" if val["missing"] else ""
            )
            print(
                f"  {status} | "
                f"{val['score']*100:.0f}% compliance | "
                f"{format_duration(elapsed)}{missing}"
            )
            results.append({
                "prompt": prompt,
                "valid": val["valid"],
                "score": val["score"],
                "elapsed": elapsed,
            })

        passed = sum(1 for r in results if r["valid"])
        total = len(results)
        pct = (passed / total) * 100

        print(f"\n{'─' * 62}")

        if pct == 100:
            grade = "🟢 ALL SYSTEMS GO"
        elif pct >= 75:
            grade = "🟡 MOSTLY COMPLIANT — review failures"
        else:
            grade = "🔴 NON-COMPLIANT — fix prompt or model"

        print(f"  Result: {passed}/{total} passed ({pct:.0f}%)")
        print(f"  {grade}")
        print(f"{'═' * 62}\n")

        return {"passed": passed, "total": total, "pct": pct, "results": results}

    def run_all_agents(self) -> None:
        print(f"\n{'═' * 62}")
        print(f"  🧪 ALL-AGENT SMOKE TEST")
        print(f"{'═' * 62}")

        test_cases = {
            "nova": "Why do teams miss deadlines?",
            "architect": "Design a system for daily habit tracking.",
            "executor": "Break down: launch a newsletter in 2 weeks.",
            "critic": "Critique this plan: We'll double revenue by hiring more salespeople.",
        }

        for agent_key, prompt in test_cases.items():
            agent = AGENTS[agent_key]
            print(f"\n  {agent['emoji']} {agent['name']}: {prompt[:50]}...")
            try:
                reply, elapsed, val = self.runner.call(
                    agent_key, prompt, silent=True
                )
                status = "✅" if val["valid"] else "⚠️"
                print(
                    f"  {status} {val['score']*100:.0f}% | "
                    f"{format_duration(elapsed)} | "
                    f"{len(reply)} chars"
                )
            except Exception as e:
                print(f"  ❌ Error: {e}")

        print(f"\n{'═' * 62}")
        print(f"  Smoke test complete")
        print(f"{'═' * 62}\n")


# ============================================================
# EXPORT
# ============================================================

def export_last_run(memory: Memory, export_dir: Path) -> Path | None:
    runs = memory.data.get("agent_runs", [])
    if not runs:
        return None

    export_dir.mkdir(parents=True, exist_ok=True)
    last = runs[-1]
    ts = last.get("timestamp", utc_now()).replace(":", "-")
    filename = export_dir / f"nova_run_{ts}.json"
    filename.write_text(json.dumps(last, indent=2), encoding="utf-8")
    return filename


# ============================================================
# CLI
# ============================================================

class CLI:
    def __init__(
        self,
        config: Config,
        memory: Memory,
        runner: AgentRunner,
        pipeline: PipelineRunner,
        tester: TestRunner,
    ) -> None:
        self.config = config
        self.memory = memory
        self.runner = runner
        self.pipeline = pipeline
        self.tester = tester
        self.running = True

    def banner(self) -> None:
        stats = self.memory.stats_line()
        print(f"\n{'═' * 62}")
        print(f"  ⚙️  NOVA AGENT FRAMEWORK v{__version__}")
        print(f"{'═' * 62}")
        print(f"  Model    {self.config.model}")
        print(f"  Endpoint {self.config.base_url}")
        print(f"  Session  {self.memory.session_id}")
        print(f"  Memory   {stats}")
        print(f"{'─' * 62}")
        print(f"  AGENTS   @nova  @architect  @executor  @critic")
        print(f"  PIPES    /full  /quick  /deep")
        print(f"  MEMORY   /memory  /facts  /search  /remember")
        print(f"  SYSTEM   /test  /testall  /status  /export  /clear")
        print(f"  OTHER    /help  exit")
        print(f"{'─' * 62}")
        print(f"  Or just type a question → NOVA analyzes it")
        print(f"{'═' * 62}\n")

    def help(self) -> None:
        print("""
╔═══════════════════════════════════════════════════════════╗
║  NOVA COMMANDS                                            ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  DIRECT AGENT CALLS                                       ║
║    @nova <query>        Systems analysis                  ║
║    @architect <query>   Solution design                   ║
║    @executor <query>    Task breakdown                    ║
║    @critic <query>      Quality review                    ║
║                                                           ║
║  PIPELINES                                                ║
║    /full <query>        NOVA→ARCHITECT→EXECUTOR→CRITIC    ║
║    /quick <query>       NOVA→CRITIC                       ║
║    /deep <query>        NOVA→ARCHITECT→EXECUTOR           ║
║                                                           ║
║  MEMORY                                                   ║
║    /memory              Recent interactions               ║
║    /facts               Stored facts                      ║
║    /search <keyword>    Search all memory                 ║
║    /remember <fact>     Store a fact                      ║
║    /clear               Clear memory (with backup)        ║
║                                                           ║
║  SYSTEM                                                   ║
║    /test                NOVA compliance tests             ║
║    /testall             All-agent smoke tests             ║
║    /status              Connection & memory status        ║
║    /export              Export last pipeline run           ║
║    /help                This menu                         ║
║    exit                 Save & quit                       ║
║                                                           ║
║  DEFAULT                                                  ║
║    <any text>           Routes to NOVA automatically      ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
        """)

    def status(self) -> None:
        print(f"\n{'─' * 50}")
        print(f"  📡 STATUS")
        print(f"{'─' * 50}")
        print(f"  Version   {__version__}")
        print(f"  Model     {self.config.model}")
        print(f"  Endpoint  {self.config.base_url}")
        print(f"  Session   {self.memory.session_id}")
        print(f"  Memory    {self.memory.stats_line()}")
        print(f"  Retries   {self.config.max_retries}")
        print(f"  Timeout   {self.config.timeout}s")
        print(f"  Max tok   {self.config.max_tokens}")

        try:
            models = self.runner.llm.check_connection()
            print(f"  Server    ✅ Connected ({len(models)} model(s))")
        except Exception as e:
            print(f"  Server    ❌ {e}")

        print(f"{'─' * 50}\n")

    def show_memory(self) -> None:
        recent = self.memory.get_recent(8)
        if not recent:
            print("\n  📭 No memories yet.\n")
            return

        print(f"\n  📝 Last {len(recent)} interactions:")
        for r in recent:
            ts = r.get("timestamp", "")[:16]
            agent = r.get("agent", "?")
            user = r.get("user", "")[:55]
            elapsed = r.get("elapsed", 0)
            emoji = AGENTS.get(agent, {}).get("emoji", "?")
            print(f"    {ts} {emoji} {agent:12} {user}  ({elapsed}s)")
        print()

    def show_facts(self) -> None:
        facts = self.memory.get_facts()
        if not facts:
            print("\n  📭 No facts. Use /remember <fact>\n")
            return

        print(f"\n  🧠 {len(facts)} stored facts:")
        for i, f in enumerate(facts, 1):
            src = f.get("source", "?")
            print(f"    {i:3}. {f['fact']}  [{src}]")
        print()

    def do_search(self, keyword: str) -> None:
        results = self.memory.search(keyword)
        if not results:
            print(f"\n  🔍 No results for '{keyword}'\n")
            return

        print(f"\n  🔍 {len(results)} result(s) for '{keyword}':")
        for r in results[-10:]:
            agent = r.get("agent", "?")
            emoji = AGENTS.get(agent, {}).get("emoji", "?")
            user = r.get("user", "")[:60]
            print(f"    {emoji} {agent:12} {user}")
        print()

    def do_remember(self, fact: str) -> None:
        if not fact:
            print("\n  ⚠️  Usage: /remember <some fact>\n")
            return
        self.memory.store_fact(fact, "USER")
        print(f'\n  🧠 Stored: "{fact}"\n')

    def do_export(self) -> None:
        export_dir = Path(self.config.data_dir) / "exports"
        path = export_last_run(self.memory, export_dir)
        if path:
            print(f"\n  📦 Exported to: {path}\n")
        else:
            print("\n  📭 No pipeline runs to export.\n")

    def do_clear(self) -> None:
        print("\n  ⚠️  This will clear all memory (backup saved).")
        confirm = input("  Type 'yes' to confirm: ").strip().lower()
        if confirm == "yes":
            self.memory.clear()
            print("  🗑️  Memory cleared.\n")
        else:
            print("  Cancelled.\n")

    def call_single_agent(self, agent_key: str, query: str) -> None:
        agent = AGENTS[agent_key]
        topic = extract_topic(query)
        print(f"\n  {agent['emoji']} {agent['name']} processing...\n")

        reply, elapsed, val = self.runner.call(
            agent_key, query, topic=topic
        )

        print(reply)
        compliance = f"{val['score']*100:.0f}%"
        status = "✅" if val["valid"] else "⚠️"
        print(
            f"\n  ⏱️ {format_duration(elapsed)} | "
            f"{status} {compliance} compliance\n"
        )

    def handle(self, raw: str) -> None:
        # ── Exit
        if raw.lower() in {"exit", "/exit", "quit", "/quit"}:
            self.memory.save()
            print("\n  💾 Memory saved. Session ended.\n")
            self.running = False
            return

        # ── System commands
        cmd = raw.lower().strip()

        if cmd == "/help":
            self.help()
            return
        if cmd == "/status":
            self.status()
            return
        if cmd == "/test":
            self.tester.run_nova_compliance()
            return
        if cmd == "/testall":
            self.tester.run_all_agents()
            return
        if cmd == "/memory":
            self.show_memory()
            return
        if cmd == "/facts":
            self.show_facts()
            return
        if cmd == "/export":
            self.do_export()
            return
        if cmd == "/clear":
            self.do_clear()
            return

        # ── Memory commands with args
        if raw.lower().startswith("/search "):
            self.do_search(raw[8:].strip())
            return
        if raw.lower().startswith("/remember "):
            self.do_remember(raw[10:].strip())
            return

        # ── Pipelines
        if raw.lower().startswith("/full "):
            query = raw[6:].strip()
            if query:
                self.pipeline.full(query, topic=extract_topic(query))
            else:
                print("\n  ⚠️  Usage: /full <your question>\n")
            return

        if raw.lower().startswith("/quick "):
            query = raw[7:].strip()
            if query:
                self.pipeline.quick(query, topic=extract_topic(query))
            else:
                print("\n  ⚠️  Usage: /quick <your question>\n")
            return

        if raw.lower().startswith("/deep "):
            query = raw[6:].strip()
            if query:
                self.pipeline.deep(query, topic=extract_topic(query))
            else:
                print("\n  ⚠️  Usage: /deep <your question>\n")
            return

        # ── Single agent @calls
        if raw.startswith("@"):
            parts = raw.split(" ", 1)
            agent_key = parts[0][1:].lower()

            if agent_key not in AGENTS:
                available = " ".join(f"@{k}" for k in AGENTS)
                print(f"\n  ⚠️  Unknown: @{agent_key}")
                print(f"  Available: {available}\n")
                return

            if len(parts) < 2 or not parts[1].strip():
                print(f"\n  ⚠️  Usage: @{agent_key} <your question>\n")
                return

            self.call_single_agent(agent_key, parts[1].strip())
            return

        # ── Catch unknown slash commands
        if raw.startswith("/"):
            print(f"\n  ⚠️  Unknown command: {raw.split()[0]}")
            print(f"  Type /help for available commands.\n")
            return

        # ── Default: route to NOVA
        topic = extract_topic(raw)
        print(f"\n  ⚙️ NOVA analyzing...\n")
        reply, elapsed, val = self.runner.call("nova", raw, topic=topic)
        print(reply)
        compliance = f"{val['score']*100:.0f}%"
        status = "✅" if val["valid"] else "⚠️"
        print(
            f"\n  ⏱️ {format_duration(elapsed)} | "
            f"{status} {compliance} compliance\n"
        )

    def run(self) -> None:
        self.banner()

        while self.running:
            try:
                raw = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                self.memory.save()
                print("\n\n  💾 Memory saved. Session ended.\n")
                break

            if not raw:
                continue

            try:
                self.handle(raw)
            except Exception as e:
                logger.exception("Unhandled error")
                print(f"\n  ❌ Error: {e}\n")


# ============================================================
# ENTRY POINT
# ============================================================

def main() -> None:
    # Load config
    config_path = Path("nova_config.json")
    if "--config" in sys.argv:
        idx = sys.argv.index("--config")
        if idx + 1 < len(sys.argv):
            config_path = Path(sys.argv[idx + 1])

    config = Config.from_file(config_path)

    # Save default config if none exists
    if not config_path.exists():
        config.save(config_path)
        logger.info("Default config saved to %s", config_path)

    # Setup
    data_dir = Path(config.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    setup_file_logging(data_dir)

    if config.verbose:
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(console)

    logger.info("NOVA v%s starting | model=%s", __version__, config.model)

    # Validate
    if not config.model.strip():
        print("\n  ❌ No model configured.")
        print(f"  Edit {config_path} and set 'model' to your LM Studio model ID.\n")
        sys.exit(1)

    # Connect
    llm = LLMClient(config)
    try:
        models = llm.check_connection()
        logger.info("Connected — models: %s", models)
    except Exception as e:
        print(f"\n  ❌ {e}\n")
        sys.exit(1)

    # Initialize components
    memory_path = data_dir / "nova_memory.json"
    memory = Memory(memory_path, config)
    runner = AgentRunner(llm, memory, config)
    pipeline = PipelineRunner(runner, memory)
    tester = TestRunner(runner)

    # Handle --test flag
    if "--test" in sys.argv:
        tester.run_nova_compliance()
        llm.close()
        return

    # Graceful shutdown
    def signal_handler(sig: int, frame: Any) -> None:
        memory.save()
        print("\n\n  💾 Memory saved. Interrupted.\n")
        llm.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run CLI
    cli = CLI(config, memory, runner, pipeline, tester)
    try:
        cli.run()
    finally:
        llm.close()
        logger.info("Session ended")


if __name__ == "__main__":
    main()
