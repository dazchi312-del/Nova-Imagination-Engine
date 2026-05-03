"""E-2b: Verify artifact enrichment threading in the dream loop."""
from __future__ import annotations

import pytest

from nova.core.loop import _run_one_iteration, LoopConfig, ReflectorScore
from nova.core.sandbox import SandboxResult, SandboxStatus
from nova.core.artifact import RichArtifact
from datetime import datetime, timezone


class FakeEmbedder:
    """Stub embedder returning deterministic 768-d vectors."""
    def __init__(self):
        self.calls = 0

    def embed(self, text: str):
        from nova.core.artifact import EmbeddingMetadata
        self.calls += 1
        return EmbeddingMetadata(
            vector=[0.01] * 768,
            model="nomic-embed-text:v1.5",
            dim=768,
            source_text=text,
            generated_at=datetime.now(timezone.utc),
        )


def _fake_crystallize(hypothesis, goal, critique, cfg):
    return "print('hello world')"


def _fake_run_sandboxed(code, cfg):
    return SandboxResult(
        status=SandboxStatus.SUCCESS,
        stdout="ok",
        stderr="",
        exit_code=0,
        artifacts={
            "result.txt": b"sample artifact bytes",
            "data.json": b'{"k": "v"}',
        },
    )


def _fake_call_reflector(hypothesis, goal, code, sandbox, cfg):
    return ReflectorScore(
        overall=0.8,
        elegance=0.8,
        creative_alignment=0.8,
        safety_risk=0.1,
        presence=0.8,
        reasoning="stub reflector",
    )


def test_enriched_artifacts_threaded_into_iteration(monkeypatch, tmp_path):
    """Iteration record must carry RichArtifact objects with embeddings."""
    monkeypatch.setattr("nova.core.loop.crystallize", _fake_crystallize)
    monkeypatch.setattr("nova.core.loop._run_sandboxed", _fake_run_sandboxed)
    monkeypatch.setattr("nova.core.loop.call_reflector", _fake_call_reflector)

    cfg = LoopConfig(dry_run=False, min_consideration_ms=0)
    embedder = FakeEmbedder()

    rec = _run_one_iteration(
        i=1,
        hypothesis="test hypothesis",
        goal="test goal",
        critique="",
        cfg=cfg,
        embedder=embedder,
    )

    assert rec.artifacts, "expected enriched artifacts on iteration record"
    assert len(rec.artifacts) == 2
    for art in rec.artifacts:
        assert isinstance(art, RichArtifact)
        assert art.name in {"result.txt", "data.json"}
        assert art.embedding is not None
        assert art.embedding.dim == 768
        assert len(art.embedding.vector) == 768


def test_enrichment_resilient_when_embedder_absent(monkeypatch):
    """Loop must not crash if no embedder is provided."""
    monkeypatch.setattr("nova.core.loop.crystallize", _fake_crystallize)
    monkeypatch.setattr("nova.core.loop._run_sandboxed", _fake_run_sandboxed)
    monkeypatch.setattr("nova.core.loop.call_reflector", _fake_call_reflector)

    cfg = LoopConfig(dry_run=False, min_consideration_ms=0)

    rec = _run_one_iteration(
        i=1,
        hypothesis="test",
        goal="test",
        critique="",
        cfg=cfg,
        embedder=None,
    )

    # Artifacts still produced, just without embeddings
    assert rec.artifacts
    for art in rec.artifacts:
        assert isinstance(art, RichArtifact)
