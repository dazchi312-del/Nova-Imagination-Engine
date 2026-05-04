"""
Pluggable extractor protocol for structural shape analysis.

Extractors consume artifact bytes and produce (ShapeDescriptor, StructuralMetadata).
They must be pure: no I/O, no mutation of inputs, deterministic for a given input.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from nova.core.schemas import ShapeDescriptor, StructuralMetadata


@dataclass
class ExtractionResult:
    """Bundle returned by an extractor. Either field may be None on partial extraction."""
    shape: Optional[ShapeDescriptor]
    structure: Optional[StructuralMetadata]


@runtime_checkable
class BaseExtractor(Protocol):
    """
    Strategy contract for structural extraction.

    Implementations should be pure and side-effect-free. The loop's _safe_extract
    helper handles exceptions, so extractors may raise on malformed input — but
    should prefer returning a partial ExtractionResult when extraction is merely
    incomplete rather than impossible.
    """

    name: str  # short identifier, e.g., "python_ast"

    def supports(self, filename: str, content: bytes) -> bool:
        """Return True if this extractor can process the given artifact."""
        ...

    def extract(self, filename: str, content: bytes) -> ExtractionResult:
        """Run extraction. May raise; caller is responsible for safety wrapping."""
        ...
