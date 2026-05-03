# nova/core/embedder.py
"""
Nomic embedder client for Project Nova.

Talks to Ollama-hosted nomic-embed-text:v1.5 over HTTP.
Sync httpx.Client to match loop.py's execution model.
Soft-fails: returns None on error, never raises into the loop.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from nova.core.artifact import (
    EMBED_SOURCE_MAX_CHARS,
    EmbeddingMetadata,
    NOMIC_EMBED_DIM,
    NOMIC_MODEL_NAME,
    extract_embedding_source,
)

logger = logging.getLogger(__name__)

# Lattice default: Mac orchestration node
DEFAULT_NOMIC_HOST = os.getenv("NOMIC_HOST", "http://192.168.100.2:11434")
DEFAULT_TIMEOUT_S = float(os.getenv("NOMIC_TIMEOUT_S", "10.0"))


class NomicEmbedder:
    """
    Sync HTTP client for Ollama's /api/embed endpoint.

    Soft-fail contract: embed() returns None on any failure
    (network, timeout, dim mismatch, malformed response).
    Caller is expected to log and continue; embedding is enrichment,
    not a gate on loop progression.
    """

    def __init__(
        self,
        host: str = DEFAULT_NOMIC_HOST,
        model: str = NOMIC_MODEL_NAME,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        client: Optional[httpx.Client] = None,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        # Allow injection for testing (MockTransport)
        self._client = client or httpx.Client(timeout=timeout_s)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "NomicEmbedder":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def embed(
        self,
        text: str,
        max_chars: int = EMBED_SOURCE_MAX_CHARS,
    ) -> Optional[EmbeddingMetadata]:
        """
        Embed text via Ollama. Returns None on any failure.

        Truncates input to max_chars before sending (Path B contract).
        """
        if not text or not text.strip():
            logger.warning("embedder.embed called with empty text; skipping")
            return None

        source = extract_embedding_source(
            text.encode("utf-8") if isinstance(text, str) else text,
            max_chars=max_chars,
        )
        url = f"{self.host}/api/embed"
        payload = {"model": self.model, "input": source}


        t0 = time.perf_counter()
        try:
            resp = self._client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            logger.warning("nomic embed timeout after %.1fs", self.timeout_s)
            return None
        except httpx.HTTPError as e:
            logger.warning("nomic embed HTTP error: %s", e)
            return None
        except ValueError as e:
            logger.warning("nomic embed JSON decode error: %s", e)
            return None

        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or not embeddings:
            logger.warning("nomic returned malformed response: %r", type(embeddings))
            return None

        vector = embeddings[0]
        if not isinstance(vector, list) or not vector:
            logger.warning("nomic returned malformed embedding: %r", type(vector))
            return None

        if len(vector) != NOMIC_EMBED_DIM:
            logger.warning(
                "nomic dim mismatch: got %d, expected %d",
                len(vector),
                NOMIC_EMBED_DIM,
            )
            return None

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        logger.info("nomic embed ok: %d dims in %.1fms", len(vector), elapsed_ms)

        return EmbeddingMetadata(
            vector=vector,
            model=self.model,
            dim=len(vector),
            source_text=source,
            generated_at=datetime.now(timezone.utc),
        )
