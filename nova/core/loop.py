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
from nova.core.memory import remember  
from nova.core.artifact import RichArtifact, enrich_artifact, EmbeddingMetadata
from nova.core.embedder import NomicEmbedder
from nova.core.schemas import (
    IterationRecord as IterationRecordV1,
    Score as ScoreV1,
    EmbeddingMetadata as EmbeddingMetadataV1,
)
 
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

    dreamer_url: str = "http://192.168.100.1:1234/v1/chat/completions"
    dreamer_model: str = "llama-3.1-nemotron-70b-instruct-hf"
    dreamer_timeout_s: int = 180

    reflector_url: str = "http://192.168.100.2:11434/v1/chat/completions"
    reflector_model: str = "phi4:latest"
    reflector_timeout_s: int = 30
    reflector_retries: int = 1

    sandbox_timeout_s: int = 30
    experiments_root: Path = Path("experiments")
    min_consideration_ms: int = 500    # Phase 9: forced consideration pause (gating not yet wired)
    dry_run: bool = False  # if True, skip sandbox execution
    embedder_url: str = "http://192.168.100.2:11434"
    embedder_model: str = "nomic-embed-text"
    embedder_enabled: bool = True


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
    presence: Optional[float] = None          # Phase 9: rumination signal (HIGH is BAD; gating not yet wired)
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
    artifacts: list[RichArtifact] = field(default_factory=list)
    embedding: Optional[EmbeddingMetadata] = None


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
You are Nova's Reflector. Evaluate a code iteration on four axes plus an overall composite.
Each value MUST be exactly one of: 0.00, 0.50, 1.00.

AXES:
- elegance: clarity, simplicity, idiomatic Python. 1.00 = clear and idiomatic.
- creative_alignment: does the code test the stated hypothesis toward the goal?
  1.00 = strongly engages the hypothesis.
- safety_risk: HIGHER means MORE risk (sketchy patterns, opaque logic).
  0.00 = clean, 1.00 = risky.
- presence: scope discipline. Does every element of the code earn its place
  against the stated goal, or does the code introduce unrequested matter
  (extra libraries, adjacent problems, decorative scaffolding, speculative
  abstractions, premature optimization)?
  1.00 = nothing extraneous; the code is exactly as large as the goal requires.
  0.50 = addresses the goal but includes one or two unrequested elements.
  0.00 = substantially wandering; significant unrequested code.

COMPOSITE:
- overall: weighted composite reflecting your judgment. 1.00 = excellent overall.

Respond with a SINGLE JSON object and nothing else. No prose, no code fences.
Schema:
{
  "elegance": 0.00 | 0.50 | 1.00,
  "creative_alignment": 0.00 | 0.50 | 1.00,
  "safety_risk": 0.00 | 0.50 | 1.00,
  "presence": 0.00 | 0.50 | 1.00,
  "overall": 0.00 | 0.50 | 1.00,
  "reason": "one or two sentences"
}
"""



def call_reflector(
    hypothesis: str,
    goal: str,
    code: str,
    sandbox: SandboxResult,
    cfg: LoopConfig,
) -> ReflectorScore:
    user_content = (
        f"HYPOTHESIS: {hypothesis}\n"
        f"GOAL: {goal}\n"
        f"--- CODE ---\n{code[:3000]}\n"
        f"--- EXECUTION STATUS --- {sandbox.status}\n"
        f"--- STDOUT ---\n{(sandbox.stdout or '')[:1500]}\n"
        f"--- STDERR ---\n{(sandbox.stderr or '')[:500]}\n"
    )
    payload = {
        "model": cfg.reflector_model,
        "messages": [
            {"role": "system", "content": REFLECTOR_RUBRIC},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "max_tokens": 300,
    }

    last_err = ""
    for attempt in range(cfg.reflector_retries + 1):

        try:
            data = _post_json(cfg.reflector_url, payload, cfg.reflector_timeout_s)
            return _parse_reflector_response(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
        except requests.exceptions.Timeout:
            last_err = "timeout"
        except requests.exceptions.ConnectionError:
            last_err = "connection_refused"
            break  # no point retrying a down host
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        log.warning("reflector attempt %d failed: %s", attempt + 1, last_err)

    return ReflectorScore.failed(last_err)

_ANCHORS = (0.00, 0.50, 1.00)


def _snap(value: float, key: str) -> float:
    """Snap a score to the nearest ADR-136 anchor; warn if drift > 0.05."""
    clamped = max(0.0, min(1.0, value))
    nearest = min(_ANCHORS, key=lambda a: abs(a - clamped))
    if abs(nearest - clamped) > 0.05:
        log.warning("reflector score drift on %s: %.3f -> %.2f", key, clamped, nearest)
    return nearest


def _parse_reflector_response(raw: str) -> ReflectorScore:
    """
    Parse Reflector output. JSON-first per ADR-136 contract; regex fallback
    for legacy/malformed responses. All scores snapped to anchors {0.00, 0.50, 1.00}.
    """
    text = (raw or "").strip()

    # Strip code fences if the model wrapped JSON despite instructions.
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            first, rest = text.split("\n", 1)
            if first.strip().lower() in ("json", ""):
                text = rest

    # JSON-first path.
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            obj = json.loads(text[start:end + 1])
            return ReflectorScore(
                overall=_snap(float(obj.get("overall", 0.5)), "overall"),
                elegance=_snap(float(obj.get("elegance", 0.5)), "elegance"),
                creative_alignment=_snap(float(obj.get("creative_alignment", 0.5)), "creative_alignment"),
                safety_risk=_snap(float(obj.get("safety_risk", 0.5)), "safety_risk"),
                presence=_snap(float(obj.get("presence", 0.5)), "presence"),
                reasoning=str(obj.get("reason", "") or "").strip()[:500],
            )
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        log.warning("reflector JSON parse failed, falling back to regex: %s", e)

    # Regex fallback: scan for "axis: 0.5" style patterns.
    def _grab(axis: str, default: float = 0.5) -> float:
        m = re.search(rf"{axis}\s*[:=]\s*(-?\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if not m:
            return default
        try:
            return float(m.group(1))
        except ValueError:
            return default

    return ReflectorScore(
        overall=_snap(_grab("overall"), "overall"),
        elegance=_snap(_grab("elegance"), "elegance"),
        creative_alignment=_snap(_grab("creative_alignment"), "creative_alignment"),
        safety_risk=_snap(_grab("safety_risk"), "safety_risk"),
        presence=_snap(_grab("presence"), "presence"),
        reasoning=text[:500],
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
    embedder: Optional["NomicEmbedder"] = None,
) -> ExperimentResult:
    exp_dir = _prepare_experiment_dir(cfg.experiments_root, experiment_id)
    log.info("[DREAM] start exp=%s dir=%s", experiment_id, exp_dir)

    if embedder is None and cfg.embedder_enabled:
        try:
            embedder = NomicEmbedder(cfg.embedder_url, cfg.embedder_model)
            log.info("[DREAM] embedder auto-instantiated url=%s model=%s",
                     cfg.embedder_url, cfg.embedder_model)
        except Exception as e:
            log.warning("[DREAM] embedder init failed: %s — proceeding without", e)
            embedder = None

    iterations: list[IterationRecord] = []
    critique = ""  # empty on first iteration
    reject_streak = 0
    stopped_reason = "max_iterations"

    for i in range(1, cfg.max_iterations + 1):
        rec = _run_one_iteration(
            i, initial_hypothesis, goal, critique, cfg, embedder=embedder
        )
        iterations.append(rec)
        _write_iteration(exp_dir, rec)  # durable after EVERY iteration

        _safe_remember(
            "iteration",
            content=f"{experiment_id}/iter{rec.iteration:03d}",
            context={
                "experiment_id": experiment_id,
                "iteration": rec.iteration,
                "code_hash": rec.code_hash,
                "status": rec.status.value,
                "dreamer_duration_s": rec.dreamer_duration_s,
                "sandbox_duration_s": rec.sandbox_duration_s,
                "reflector_duration_s": rec.reflector_duration_s,
                "overall_score": rec.score.overall if rec.score else None,
            },
        )

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

    _safe_remember(
        "experiment",
        content=f"{experiment_id}/summary",
        context={
            "experiment_id": experiment_id,
            "goal": goal,
            "best_iteration": best_idx,
            "final_score": best_score,
            "stopped_reason": stopped_reason,
            "iteration_count": len(iterations),
        },
    )

    log.info("[DREAM] done exp=%s best_iter=%s score=%.2f reason=%s",
             experiment_id, best_idx, best_score, stopped_reason)
    return result  

def _run_one_iteration(
    i: int,
    hypothesis: str,
    goal: str,
    critique: str,
    cfg: LoopConfig,
    embedder: Optional["NomicEmbedder"] = None,

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


    # --- Presence pause (consideration before action) ---
    if cfg.min_consideration_ms > 0:
        time.sleep(cfg.min_consideration_ms / 1000.0)

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
    if cfg.dry_run:
        log.info("[DRY-RUN] Skipping sandbox execution for iteration %d", i)
        sandbox = SandboxResult(
            status=SandboxStatus.SUCCESS,
            stdout="[DRY-RUN] Execution skipped",
            stderr="",
            exit_code=0,
        )
        rec.sandbox_duration_s = 0.0
    else:
        t0 = time.monotonic()
        sandbox = _run_sandboxed(rec.code, cfg)
        rec.sandbox_duration_s = time.monotonic() - t0
    rec.sandbox_status = str(sandbox.status)
    rec.sandbox_stdout = sandbox.stdout
    rec.sandbox_stderr = sandbox.stderr
    
    # --- Artifact enrichment (Phase 9, E-2b) ---
    enriched: list[RichArtifact] = []
    for name, blob in sandbox.artifacts.items():
        try:
            enriched.append(enrich_artifact(name, blob, embedder=embedder))
        except Exception as e:
            log.warning("[DREAM] artifact enrichment failed name=%s err=%s", name, e)
    rec.artifacts = enriched


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

    if embedder is not None and rec.status != IterationStatus.DREAMER_FAILED:
        reasoning = rec.score.reasoning if rec.score else ""
        source_text = (
            "HYPOTHESIS:\n" + str(rec.hypothesis) + "\n\n"
            "CODE:\n" + str(rec.code) + "\n\n"
            "REASONING:\n" + str(reasoning)
        )
        try:
            embedding = embedder.embed(source_text)
            if embedding is not None:
                rec.embedding = embedding
        except Exception as e:
            log.warning("[DREAM] iteration embedding failed iter=%d err=%s", i, e)

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

def _safe_remember(kind: str, *, content: str, context: dict) -> None:
    """Record an episode; never raise. Memory is best-effort from the loop."""
    try:
        remember(kind, content=content, context=context)
    except Exception as e:
        log.warning("memory.remember(%r) failed: %s", kind, e)


def _write_iteration(exp_dir: Path, rec: IterationRecord) -> None:
    stem = f"iter{rec.iteration:03d}"
    _atomic_write(exp_dir / f"{stem}_code.py", rec.code or "# (no code)")

    # --- Translate internal dataclass -> canonical Pydantic v1 record ---
    score_v1 = None
    reflector_status = "ok"
    if rec.score is not None:
        s = rec.score
        if (s.elegance is None or s.creative_alignment is None
                or s.safety_risk is None or s.presence is None):
            reflector_status = "failed"
        else:
            score_v1 = ScoreV1(
                overall=s.overall,
                elegance=s.elegance,
                creative_alignment=s.creative_alignment,
                safety_risk=s.safety_risk,
                presence=s.presence,
                reasoning=s.reasoning or "",
            )

    embedding_v1 = None
    if rec.embedding is not None:
        e = rec.embedding
        embedding_v1 = EmbeddingMetadataV1(
            vector=e.vector,
            model=e.model,
            dim=e.dim,
            source_text=e.source_text,
            generated_at=e.generated_at,
            model_blob_sha=e.model_blob_sha,
        )

    artifact_names = [a.name for a in rec.artifacts]
    status_val = rec.status.value if hasattr(rec.status, "value") else str(rec.status)

    record_v1 = IterationRecordV1(
        iteration=rec.iteration,
        started_at=rec.started_at,
        ended_at=rec.ended_at,
        status=status_val,
        hypothesis=rec.hypothesis,
        critique_applied=rec.critique_applied or "",
        code=rec.code,
        code_hash=rec.code_hash,
        sandbox_status=rec.sandbox_status,
        sandbox_stdout=rec.sandbox_stdout,
        sandbox_stderr=rec.sandbox_stderr,
        sandbox_duration_s=rec.sandbox_duration_s,
        dreamer_duration_s=rec.dreamer_duration_s,
        reflector_duration_s=rec.reflector_duration_s,
        score=score_v1,
        reflector_status=reflector_status,
        error=rec.error or "",
        artifacts=artifact_names,
        embedding=embedding_v1,
    )

    _atomic_write(
        exp_dir / f"{stem}_record.json",
        record_v1.model_dump_json(indent=2),
    )


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

def _parse_args():
    import argparse
    parser = argparse.ArgumentParser(
        description="Nova Dream Loop - iterative code generation with reflection"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview iterations without executing sandbox code"
    )
    parser.add_argument(
        "--max-iterations", type=int, default=5,
        help="Maximum number of dream/execute/reflect cycles"
    )
    parser.add_argument(
        "--goal", type=str,
        default="Generate and validate a simple Python function",
        help="Goal description for the dreamer"
    )
    parser.add_argument(
        "--hypothesis", type=str,
        default="A well-structured function can be generated iteratively",
        help="Initial hypothesis to explore"
    )
    parser.add_argument(
        "--experiment-id", type=str, default=None,
        help="Experiment identifier (default: smoke_<timestamp>)"
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point for the dream loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args()

    exp_id = args.experiment_id or f"smoke_{int(time.time())}"
    cfg = LoopConfig(
        max_iterations=args.max_iterations,
        dry_run=args.dry_run,
    )

    if cfg.dry_run:
        log.info("[DRY-RUN] Sandbox execution will be skipped")

    result = dream_loop(
        experiment_id=exp_id,
        initial_hypothesis=args.hypothesis,
        goal=args.goal,
        cfg=cfg,
    )
    print(f"[DONE] best score = {result.final_score:.2f}, "
          f"stopped = {result.stopped_reason}")


if __name__ == "__main__":
    main()
