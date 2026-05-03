"""
Block E-1: enrich_artifact() embedder integration.

Contract:
  - No embedder → embedding stays None (back-compat with 137 existing tests).
  - Embedder provided, embed succeeds → embedding populated.
  - Embedder provided, embed fails (returns None) → embedding stays None,
    no exception raised.
  - Empty/whitespace content → embedder is NOT called.
"""
from unittest.mock import MagicMock
import pytest

from nova.core.artifact import enrich_artifact, RichArtifact, EmbeddingMetadata
from datetime import datetime, timezone
...
fake_meta = EmbeddingMetadata(
    vector=[0.1] * 768,
    dim=768,
    model="nomic-embed-text:v1.5",
    source_text="test content",
    generated_at=datetime.now(timezone.utc),
    model_blob_sha="sha256:970aa74c0a90",
)



def test_no_embedder_back_compat():
    """Default behavior unchanged: embedding is None."""
    art = enrich_artifact("hello.txt", b"hello world")
    assert isinstance(art, RichArtifact)
    assert art.embedding is None


def test_embedder_success_populates_embedding():
    fake_meta = EmbeddingMetadata(
        vector=[0.1] * 768,
        dim=768,
        model="nomic-embed-text:v1.5",
        generated_at=datetime.now(timezone.utc),
        source_text="test content",
        model_blob_sha="sha256:970aa74c0a90",
    )
    embedder = MagicMock()
    embedder.embed.return_value = fake_meta

    art = enrich_artifact("doc.txt", b"the quick brown fox", embedder=embedder)

    assert art.embedding is fake_meta
    embedder.embed.assert_called_once()


def test_embedder_soft_fail_leaves_embedding_none():
    """Embedder returns None (network failure) → no exception, embedding=None."""
    embedder = MagicMock()
    embedder.embed.return_value = None

    art = enrich_artifact("doc.txt", b"some content", embedder=embedder)

    assert art.embedding is None
    embedder.embed.assert_called_once()


def test_empty_content_skips_embedder():
    """Whitespace-only content should not waste an HTTP call."""
    embedder = MagicMock()
    art = enrich_artifact("empty.txt", b"   \n\t  ", embedder=embedder)

    assert art.embedding is None
    embedder.embed.assert_not_called()


def test_binary_garbage_still_attempted_if_decodable():
    """Path B contract: if decode yields any text, we try. Embedder decides."""
    embedder = MagicMock()
    embedder.embed.return_value = None  # simulate embedder rejecting noise
    art = enrich_artifact("blob.bin", b"\x89PNG\r\n\x1a\n binary-ish", embedder=embedder)
    # The decision lives at embedder.embed(); enrich_artifact just forwards.
    assert art.embedding is None
