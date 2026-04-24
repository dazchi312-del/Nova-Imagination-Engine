# loop.py v1.3.0
# Location: nova/core/loop.py
# Purpose: Orchestrate the Dream→Execute→Reflect cycle.
#
# DESIGN PRINCIPLES:
#   1. The best-scoring iteration wins, not the last one.
#   2. Every iteration produces a structured record with ALL context
#      needed to reconstruct what happened, even months later.
#   3. Hypothesis (stable intent) and Critique (per-iteration feedback)
#      are tracked separately. We never overwrite intent with critique.
#   4. Failures are classified, not hidden. Every iteration has a status.
#   5. Writes to disk are atomic (write-to-tmp, then rename). A crash
#      mid-write never produces a truncated file.
#   6. Reflector scoring is multi-dimensional with a rubric.

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import requests

from nova.core.ast_shield import shield_gate
from nova.core.sandbox import execute_sandboxed, SandboxResult, SandboxStatus

log = logging.getLogger("nova.loop")

# ===== CONFIG =====
# In a real project these move to config.py or environment variables.
# Keeping them here for a single-file example, but clearly grouped.

@dataclass(frozen=True)
class LoopConfig:
    max_iterations: int = 5
    target_score: float = 0.85
    auto_accept_threshold: float = 0.95
    auto_reject_threshold: float = 0.50
    auto_reject_streak: int = 2  # reject if N consecutive below threshold

    dreamer_url: str = "http://localhost:1234/v1/chat/completions"
    dreamer_model: str = "llama-3.1-nemotron-70b-instruct-hf"
    dreamer_timeout_s: int = 180

    reflector_url: str = "http://192.168.100.2:11434/api/generate"
    reflector_model: str = "llama3.1:8b"
    reflector_timeout_s: int = 30
    reflector_retries: int = 1

    sandbox_timeout_s: int = 30
    experiments_root: Path = Path("experiments")


# ===== ITERATION RECORD =====
# This is the single source of truth for "what happened in iteration N".
# Add fields here, not scattered across dict keys.

class IterationStatus(str, Enum):
    OK = "ok"
    DREAMER_FAILED = "dreamer_failed"
    SHIELD_BLOCKED = "shield_blocked"
    SANDBOX_ERROR = "sandbox_error"
    SANDBOX_TIMEOUT = "sandbox_timeout"
    REFLECTOR_FAILED = "reflector_failed"


@dataclass
class ReflectorScore:
    # Multi-dimensional scoring per the Nova roadmap.
    # Each axis is 0.0–1.0. `overall` is a weighted composite.
    overall: float
    elegance: Optional[float] = None
    creative_alignment: Optional[float] = None
    safety_risk: Optional[float] = None       # HIGH is BAD here
    reasoning: str = ""                       # the LLM's justification

    @classmethod
    def failed(cls, reason: str) -> "ReflectorScore":
        return cls(overall=0.0, reasoning=f"[reflector_failed] {reason}")


@dataclass
class IterationRecord:
    iteration: int
    started_at: str
    ended_at: str
    status: IterationStatus
    hypothesis: str
    critique_applied: str            # the refinement fed in for this iteration ("" for iter 1)
    code: str = ""
    code_hash: str = ""
    sandbox_status: str = ""
    sandbox_stdout: str = ""
    sandbox_stderr: str = ""
    sandbox_duration_s: float = 0.0
    dreamer_duration_s: float = 0.0
    reflector_duration_s: float = 0.0
    score: Optional[ReflectorScore] = None
    error: str = ""


@dataclass
class ExperimentResult:
    experiment_id: str
    goal: str
    initial_hypothesis: str
    iterations: list[IterationRecord]
    best_iteration_index: Optional[int]   # 1-based; None if none succeeded
    final_score: float
    stopped_reason: str

    @property
    def best(self) -> Optional[IterationRecord]:
        if self.best_iteration_index is None:
            return None
        return self.iterations[self.best_iteration_index - 1]


# ===== HTTP HELPERS =====

def _post_json(url: str, payload: dict, timeout: int) -> dict:
    """Thin wrapper that raises on HTTP error and returns parsed JSON."""
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ===== DREAMER =====

def crystallize(hypothesis: str, goal: str, critique: str, cfg: LoopConfig) -> str:
    """
    Ask the Dreamer for code.
    `critique` is empty on iteration 1 and contains the prior iteration's
    specific feedback thereafter. The hypothesis is stable across iterations.
    """
    system = (
        "You are Nova's Dreamer. Generate Python code to test a hypothesis. "
        "Output ONLY a single ```python fenced block with no prose before or after. "
        "Use numpy/matplotlib. Include prints. Save any plot as output.png."
    )
    user = f"HYPOTHESIS: {hypothesis}\nGOAL: {goal}"
    if critique:
        user += f"\n\nPREVIOUS ATTEMPT CRITIQUE:\n{critique}\n\nProduce an improved version."

    resp = _post_json(
        cfg.dreamer_url,
        {
            "model": cfg.dreamer_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
        },
        timeout=cfg.dreamer_timeout_s,
    )
    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _extract_code_block(content)


def _extract_code_block(text: str) -> str:
    """Robustly extract the first Python code fence, else return stripped text."""
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


# ===== REFLECTOR =====

REFLECTOR_RUBRIC = """\
You are Nova's Reflector. Score a code iteration on four axes (0.00–1.00):

- ELEGANCE: clarity, simplicity, idiomatic Python.
- CREATIVE_ALIGNMENT: does the code test the stated hypothesis toward the goal?
- SAFETY_RISK: higher means MORE risk (sketchy patterns, opaque logic). 0 = clean.
- OVERALL: weighted composite (your judgment).

Respond in EXACTLY this format, nothing else:
ELEGANCE: 0.XX
CREATIVE_ALIGNMENT: 0.XX
SAFETY_RISK: 0.XX
OVERALL: 0.XX
REASON: <one or two sentences>
"""


def call_reflector(
    hypothesis: str,
    goal: str,
    code: str,
    sandbox: SandboxResult,
    cfg: LoopConfig,
) -> ReflectorScore:
    prompt = (
        f"{REFLECTOR_RUBRIC}\n\n"
        f"HYPOTHESIS: {hypothesis}\n"
        f"GOAL: {goal}\n"
        f"--- CODE ---\n{code[:3000]}\n"
        f"--- EXECUTION STATUS --- {sandbox.status}\n"
        f"--- STDOUT ---\n{sandbox.stdout[:1500]}\n"
        f"--- STDERR ---\n{sandbox.stderr[:500]}\n"
    )
    payload = {
        "model": cfg.reflector_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 200},
    }

    last_err = ""
    for attempt in range(cfg.reflector_retries + 1):
        try:
            data = _post_json(cfg.reflector_url, payload, cfg.reflector_timeout_s)
            return _parse_reflector_response(data.get("response", ""))
        except requests.exceptions.Timeout:
            last_err = "timeout"
        except requests.exceptions.ConnectionError:
            last_err = "connection_refused"
            break  # no point retrying a down host
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        log.warning("reflector attempt %d failed: %s", attempt + 1, last_err)

    return ReflectorScore.failed(last_err)


def _parse_reflector_response(text: str) -> ReflectorScore:
    def grab(label: str) -> Optional[float]:
        m = re.search(rf"{label}\s*:\s*([01](?:\.\d+)?)", text, re.IGNORECASE)
        if not m:
            return None
        return max(0.0, min(1.0, float(m.group(1))))

    reason_m = re.search(r"REASON\s*:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    return ReflectorScore(
        overall=grab("OVERALL") or 0.0,
        elegance=grab("ELEGANCE"),
        creative_alignment=grab("CREATIVE_ALIGNMENT"),
        safety_risk=grab("SAFETY_RISK"),
        reasoning=(reason_m.group(1).strip() if reason_m else "")[:500],
    )


# ===== SANDBOX WRAPPER =====

def _run_sandboxed(code: str, cfg: LoopConfig) -> SandboxResult:
    """
    Unified sandbox invocation: shield first, then execute.
    Always returns a SandboxResult (never a dict) so callers have one type.
    """
    safe, msg = shield_gate(code)
    if not safe:
        return SandboxResult(
            status=SandboxStatus.BLOCKED,   # ensure this exists in sandbox.py
            stdout="",
            stderr=f"AST shield blocked: {msg}",
            duration_s=0.0,
            artifacts=[],
            truncated_stdout=False,
            truncated_stderr=False,
        )
    return execute_sandboxed(code, timeout_s=cfg.sandbox_timeout_s)


# ===== REFINE =====

def refine_hypothesis(prev: IterationRecord, cfg: LoopConfig) -> str:
    """
    Produce a CRITIQUE (not a new hypothesis) to feed into the next crystallize().
    Falls back to a minimal critique on any failure — never raises.
    """
    if prev.score is None:
        return f"Previous iteration failed with status={prev.status.value}. Try a cleaner approach."
    prompt = (
        f"Previous code scored {prev.score.overall:.2f}. Reason: {prev.score.reasoning}\n"
        f"Give ONE concrete improvement in <= 3 sentences. No code."
        f"\n\n--- CODE ---\n{prev.code[:1500]}"
    )
    try:
        data = _post_json(
            cfg.dreamer_url,
            {
                "model": cfg.dreamer_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5,
                "max_tokens": 250,
            },
            timeout=cfg.dreamer_timeout_s,
        )
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return text or f"Improve past the {prev.score.overall:.2f} score."
    except Exception as e:
        log.warning("refine_hypothesis failed: %s", e)
        return f"Improve past the {prev.score.overall:.2f} score."


# ===== MAIN LOOP =====

def dream_loop(
    experiment_id: str,
    initial_hypothesis: str,
    goal: str,
    cfg: LoopConfig = LoopConfig(),
) -> ExperimentResult:
    exp_dir = _prepare_experiment_dir(cfg.experiments_root, experiment_id)
    log.info("[DREAM] start exp=%s dir=%s", experiment_id, exp_dir)

    iterations: list[IterationRecord] = []
    critique = ""  # empty on first iteration
    reject_streak = 0
    stopped_reason = "max_iterations"

    for i in range(1, cfg.max_iterations + 1):
        rec = _run_one_iteration(
            i, initial_hypothesis, goal, critique, cfg
        )
        iterations.append(rec)
        _write_iteration(exp_dir, rec)  # durable after EVERY iteration

        log.info("[ITER %d] status=%s score=%.2f",
                 i, rec.status.value,
                 rec.score.overall if rec.score else 0.0)

        if rec.score and rec.score.overall >= cfg.auto_accept_threshold:
            stopped_reason = "auto_accept"
            break

        if rec.score and rec.score.overall < cfg.auto_reject_threshold:
            reject_streak += 1
            if reject_streak >= cfg.auto_reject_streak:
                stopped_reason = "auto_reject_streak"
                break
        else:
            reject_streak = 0

        # Prepare critique for next iteration
        if i < cfg.max_iterations:
            critique = refine_hypothesis(rec, cfg)

    # Select best, not last.
    best_idx = _select_best(iterations)
    best_score = iterations[best_idx - 1].score.overall if best_idx else 0.0

    result = ExperimentResult(
        experiment_id=experiment_id,
        goal=goal,
        initial_hypothesis=initial_hypothesis,
        iterations=iterations,
        best_iteration_index=best_idx,
        final_score=best_score,
        stopped_reason=stopped_reason,
    )
    _write_summary(exp_dir, result)
    log.info("[DREAM] done exp=%s best_iter=%s score=%.2f reason=%s",
             experiment_id, best_idx, best_score, stopped_reason)
    return result


def _run_one_iteration(
    i: int, hypothesis: str, goal: str, critique: str, cfg: LoopConfig
) -> IterationRecord:
    started = _now_iso()
    rec = IterationRecord(
        iteration=i,
        started_at=started,
        ended_at="",
        status=IterationStatus.OK,
        hypothesis=hypothesis,
        critique_applied=critique,
    )

    # --- Dreamer ---
    t0 = time.monotonic()
    try:
        rec.code = crystallize(hypothesis, goal, critique, cfg)
    except Exception as e:
        rec.status = IterationStatus.DREAMER_FAILED
        rec.error = f"{type(e).__name__}: {e}"
        rec.ended_at = _now_iso()
        return rec
    finally:
        rec.dreamer_duration_s = time.monotonic() - t0

    if not rec.code.strip():
        rec.status = IterationStatus.DREAMER_FAILED
        rec.error = "empty code returned"
        rec.ended_at = _now_iso()
        return rec

    rec.code_hash = hashlib.sha256(rec.code.encode("utf-8")).hexdigest()[:16]

    # --- Sandbox (with Shield) ---
    t0 = time.monotonic()
    sandbox = _run_sandboxed(rec.code, cfg)
    rec.sandbox_duration_s = time.monotonic() - t0
    rec.sandbox_status = str(sandbox.status)
    rec.sandbox_stdout = sandbox.stdout
    rec.sandbox_stderr = sandbox.stderr

    # Map sandbox status → iteration status (but we still call the Reflector
    # for most outcomes — a failed run is still signal).
    sstatus = str(sandbox.status).lower()
    if "blocked" in sstatus:
        rec.status = IterationStatus.SHIELD_BLOCKED
    elif "timeout" in sstatus:
        rec.status = IterationStatus.SANDBOX_TIMEOUT
    elif "error" in sstatus or "crash" in sstatus:
        rec.status = IterationStatus.SANDBOX_ERROR

    # --- Reflector ---
    t0 = time.monotonic()
    rec.score = call_reflector(hypothesis, goal, rec.code, sandbox, cfg)
    rec.reflector_duration_s = time.monotonic() - t0

    if rec.score.reasoning.startswith("[reflector_failed]"):
        rec.status = IterationStatus.REFLECTOR_FAILED
        rec.error = rec.score.reasoning

    rec.ended_at = _now_iso()
    return rec


def _select_best(iterations: list[IterationRecord]) -> Optional[int]:
    """Returns 1-based index of the highest-scoring iteration, or None."""
    scored = [(i + 1, r.score.overall)
              for i, r in enumerate(iterations)
              if r.score is not None]
    if not scored:
        return None
    return max(scored, key=lambda x: x[1])[0]


# ===== PERSISTENCE =====

def _prepare_experiment_dir(root: Path, exp_id: str) -> Path:
    # Fail loud if someone re-uses an experiment id with existing content.
    # This prevents silent overwrite of prior data.
    d = root / exp_id
    if d.exists() and any(d.iterdir()):
        # Preserve prior run by renaming it.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        d.rename(root / f"{exp_id}.prev-{stamp}")
    d = root / exp_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _atomic_write(path: Path, data: str) -> None:
    """Write-then-rename so partial writes never leave a corrupt file."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)


def _write_iteration(exp_dir: Path, rec: IterationRecord) -> None:
    stem = f"iter{rec.iteration:03d}"
    _atomic_write(exp_dir / f"{stem}_code.py", rec.code or "# (no code)")
    # Full record as JSON (includes timing, stdout, stderr, score, reasoning).
    _atomic_write(exp_dir / f"{stem}_record.json",
                  json.dumps(asdict(rec), indent=2, default=str))


def _write_summary(exp_dir: Path, result: ExperimentResult) -> None:
    summary = {
        "experiment_id": result.experiment_id,
        "goal": result.goal,
        "initial_hypothesis": result.initial_hypothesis,
        "best_iteration_index": result.best_iteration_index,
        "final_score": result.final_score,
        "stopped_reason": result.stopped_reason,
        "iteration_count": len(result.iterations),
        "scores": [
            {"iter": r.iteration,
             "status": r.status.value,
             "overall": r.score.overall if r.score else None}
            for r in result.iterations
        ],
    }
    _atomic_write(exp_dir / "summary.json",
                  json.dumps(summary, indent=2, default=str))
    # Surface the winning code as final_code.py for convenience.
    if result.best is not None:
        _atomic_write(exp_dir / "final_code.py", result.best.code)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===== ENTRY =====

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    result = dream_loop(
        experiment_id=f"smoke_{int(time.time())}",
        initial_hypothesis="The sine function is smoother than a random walk on [0, 4π].",
        goal="Plot both curves and quantify smoothness via total variation.",
    )
    print(f"[DONE] best score = {result.final_score:.2f}, "
          f"stopped = {result.stopped_reason}")

