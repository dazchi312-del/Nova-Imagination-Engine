# nova/core/schemas.py
# Block C: Boundary Hardening — Pydantic v2 schemas for persistence + network I/O.
#
# DESIGN PRINCIPLES:
#   1. Construct-then-dump: build the model, then serialize. Never write raw dicts.
#   2. Schema versioning starts at v1. Absent version = v1 (legacy compat).
#   3. Validators normalize legacy quirks (e.g. "SandboxStatus.SUCCESS" -> "success")
#      so disk records are never mutated, only re-interpreted on load.
#   4. extra="forbid" by default to fail loud on typos. Override per-model only
#      when forward-compat with unknown future fields is desired.

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SCHEMA_VERSION = 1


# ===== EMBEDDING =====

class EmbeddingMetadata(BaseModel):
    """Vector + provenance for a single embedding."""
    model_config = ConfigDict(extra="forbid")

    vector: List[float] = Field(..., min_length=1)
    model: str
    dim: int = Field(..., gt=0)
    source_text: str
    generated_at: datetime
    model_blob_sha: Optional[str] = None

    @field_validator("vector")
    @classmethod
    def _vector_matches_dim(cls, v: List[float], info) -> List[float]:
        # dim is validated separately; cross-check happens in model_validator below.
        return v

    def model_post_init(self, __context) -> None:
        if len(self.vector) != self.dim:
            raise ValueError(
                f"embedding vector length {len(self.vector)} != declared dim {self.dim}"
            )


# ===== SCORE RUBRIC =====

class Score(BaseModel):
    """Reflector's multi-dimensional rubric output."""
    model_config = ConfigDict(extra="forbid")

    overall: float = Field(..., ge=0.0, le=1.0)
    elegance: float = Field(..., ge=0.0, le=1.0)
    creative_alignment: float = Field(..., ge=0.0, le=1.0)
    safety_risk: float = Field(..., ge=0.0, le=1.0)
    presence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str


# ===== ITERATION RECORD =====

# Canonical sandbox status values. Legacy records may contain "SandboxStatus.SUCCESS"
# style strings; the validator normalizes them.
SandboxStatusLiteral = Literal[
    "success", "error", "timeout", "blocked", "skipped"
]

IterationStatusLiteral = Literal[
    "ok",
    "dreamer_failed",
    "shield_blocked",
    "sandbox_error",
    "sandbox_timeout",
    "reflector_failed",
]


class IterationRecord(BaseModel):
    """The single source of truth for one Dream→Execute→Reflect iteration."""
    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION

    iteration: int = Field(..., ge=1)
    started_at: datetime
    ended_at: datetime
    status: IterationStatusLiteral

    hypothesis: str
    critique_applied: str = ""

    code: str
    code_hash: str

    sandbox_status: SandboxStatusLiteral
    sandbox_stdout: Optional[str] = None
    sandbox_stderr: Optional[str] = None
    sandbox_duration_s: float = Field(..., ge=0.0)

    dreamer_duration_s: float = Field(..., ge=0.0)
    reflector_duration_s: float = Field(..., ge=0.0)

    score: Optional[Score] = None

    reflector_status: Literal["ok", "failed", "timeout", "skipped"] = "ok"

    error: str = ""
    artifacts: List[str] = Field(default_factory=list)
    embedding: Optional[EmbeddingMetadata] = None

    @field_validator("sandbox_status", mode="before")
    @classmethod
    def _normalize_sandbox_status(cls, v):
        """Accept legacy 'SandboxStatus.SUCCESS' and enum instances; emit canonical lowercase."""
        if v is None:
            return v
        s = str(v)
        if "." in s:                       # "SandboxStatus.SUCCESS"
            s = s.split(".", 1)[1]
        return s.lower()


# ===== NETWORK BOUNDARIES =====

class DreamerOutput(BaseModel):
    """What we accept back from the Dreamer LLM after parsing."""
    model_config = ConfigDict(extra="forbid")

    hypothesis: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)


class ReflectorOutput(BaseModel):
    """What we accept back from the Reflector LLM after parsing."""
    model_config = ConfigDict(extra="forbid")

    score: Score
    critique: str = ""
