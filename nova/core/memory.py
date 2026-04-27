"""
nova/core/memory.py — The Memory Facade.
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterator, Optional

from nova.core.episode import Episode
from nova.core.episodic import EpisodicStore

# The "Truth" location
_DEFAULT_PATH = Path.home() / "nova" / "data" / "episodic.db"
_store: Optional[EpisodicStore] = None

def _get_store() -> EpisodicStore:
    """The Lazy Hit: Initializes only when needed."""
    global _store
    if _store is None:
        _store = EpisodicStore(_DEFAULT_PATH)
    return _store

def set_store(store: Optional[EpisodicStore]) -> None:
    """The Injection Port: Crucial for isolated testing."""
    global _store
    _store = store

def remember(kind: str, content: str, context: Optional[dict] = None) -> Episode:
    """Entry: Record an experience."""
    ep = Episode(kind=kind, content=content, context=context or {})
    _get_store().append(ep)
    return ep

def recall(hash_val: str) -> Optional[Episode]:
    """Exit: Retrieve by fingerprint."""
    return _get_store().get(hash_val)

def recall_kind(kind: str) -> Iterator[Episode]:
    return _get_store().by_kind(kind)

def recall_since(timestamp: str) -> Iterator[Episode]:
    return _get_store().since(timestamp)
