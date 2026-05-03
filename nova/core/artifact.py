"""
Artifact schema for Phase 9 Imagination Engine.

Artifacts carry structural metadata enabling cross-domain resonance detection.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Any
if TYPE_CHECKING:
    from nova.core.embedder import NomicEmbedder
from enum import Enum
from datetime import datetime
# EmbeddingMetadata is canonical in nova.core.schemas (Pydantic).
# Re-exported here for backward-compatible imports.
from nova.core.schemas import EmbeddingMetadata



# Embedding model constants
NOMIC_EMBED_DIM = 768
NOMIC_MODEL_NAME = "nomic-embed-text:v1.5"
EMBED_SOURCE_MAX_CHARS = 2000  # Path B: truncate content for embedding


class ArtifactDomain(Enum):
    """Primary domain classification."""
    CODE = "code"
    AUDIO = "audio"
    VISUAL = "visual"
    TEXT = "text"
    DATA = "data"
    UNKNOWN = "unknown"


@dataclass
class ShapeDescriptor:
    """
    Structural shape extracted from artifact.
    
    These are domain-agnostic patterns that enable cross-domain matching.
    Examples: "repetition-with-variation", "negative-space", "compression"
    """
    primary: str                           # e.g., "layered-repetition"
    secondary: list[str] = field(default_factory=list)  # supporting shapes
    confidence: float = 0.0                # 0-1, how confident in extraction


@dataclass
class StructuralMetadata:
    """Domain-specific structural information."""
    
    # Code-specific
    ast_depth: Optional[int] = None
    cyclomatic_complexity: Optional[int] = None
    function_count: Optional[int] = None
    
    # Audio-specific (future)
    duration_s: Optional[float] = None
    frequency_range: Optional[tuple[float, float]] = None
    dynamic_range_db: Optional[float] = None
    
    # Visual-specific (future)
    dimensions: Optional[tuple[int, int]] = None
    color_palette_size: Optional[int] = None
    
    # Text-specific
    word_count: Optional[int] = None
    sentence_avg_length: Optional[float] = None
    
    # Generic
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RichArtifact:
    """
    Extended artifact with structural metadata for cross-domain resonance.
    
    Wraps raw artifact bytes with shape descriptors and taste anchors.
    """
    name: str
    content: bytes
    domain: ArtifactDomain
    
    # Structural analysis
    shape: Optional[ShapeDescriptor] = None
    structure: Optional[StructuralMetadata] = None
    
    # Taste alignment
    anchors: list[str] = field(default_factory=list)  # refs to references.md
    resonance_score: float = 0.0  # 0-1, alignment with taste
    
    # Geometric similarity (Block D)
    embedding: Optional[EmbeddingMetadata] = None
    
    # Provenance
    created_at: datetime = field(default_factory=datetime.now)
    iteration_id: Optional[str] = None
    
    @property
    def size_bytes(self) -> int:
        return len(self.content)
    
    def to_dict(self, include_vector: bool = False) -> dict:
        """
        Serialize for storage/API.
        
        Args:
            include_vector: If True, include full embedding vector.
                           Default False to keep log dumps lightweight
                           (768 floats ≈ 11KB JSON per artifact).
        """
        embedding_dict = None
        if self.embedding:
            embedding_dict = {
                "model": self.embedding.model,
                "dim": self.embedding.dim,
                "source_text": self.embedding.source_text,
                "generated_at": self.embedding.generated_at.isoformat(),
            }
            if include_vector:
                embedding_dict["vector"] = self.embedding.vector
        
        return {
            "name": self.name,
            "domain": self.domain.value,
            "size_bytes": self.size_bytes,
            "shape": {
                "primary": self.shape.primary,
                "secondary": self.shape.secondary,
                "confidence": self.shape.confidence
            } if self.shape else None,
            "anchors": self.anchors,
            "resonance_score": self.resonance_score,
            "embedding": embedding_dict,
            "created_at": self.created_at.isoformat(),
            "iteration_id": self.iteration_id
        }


def infer_domain(filename: str, content: bytes) -> ArtifactDomain:
    """Infer artifact domain from filename and content."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    
    code_exts = {"py", "js", "ts", "rs", "go", "c", "cpp", "h", "java"}
    audio_exts = {"wav", "mp3", "flac", "ogg", "aiff"}
    visual_exts = {"png", "jpg", "jpeg", "gif", "svg", "webp"}
    text_exts = {"txt", "md", "rst", "json", "yaml", "toml"}
    data_exts = {"csv", "parquet", "db", "sqlite"}
    
    if ext in code_exts:
        return ArtifactDomain.CODE
    if ext in audio_exts:
        return ArtifactDomain.AUDIO
    if ext in visual_exts:
        return ArtifactDomain.VISUAL
    if ext in text_exts:
        return ArtifactDomain.TEXT
    if ext in data_exts:
        return ArtifactDomain.DATA
    
    # Content-based fallback
    try:
        text = content.decode("utf-8")
        if "def " in text or "class " in text or "import " in text:
            return ArtifactDomain.CODE
        return ArtifactDomain.TEXT
    except UnicodeDecodeError:
        return ArtifactDomain.UNKNOWN


def extract_embedding_source(content: bytes, max_chars: int = EMBED_SOURCE_MAX_CHARS) -> str:
    """
    Path B: Extract truncated text for embedding.
    
    Decodes bytes with error tolerance, truncates to max_chars.
    Binary domains (audio/visual) will yield mostly empty/garbage strings —
    those should skip embedding at the call site.
    
    Future (Path A upgrade): Replace this with shape descriptor composition
    once Block C shape extraction is wired into enrich_artifact().
    """
    try:
        text = content.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    return text[:max_chars]


def enrich_artifact(
    name: str,
    content: bytes,
    embedder: Optional["NomicEmbedder"] = None,
) -> RichArtifact:
    """
    Convert raw artifact to RichArtifact with inferred metadata.

    If an embedder is provided, attempts to populate `embedding` via
    Path B (truncated text source). Embedding failure is non-fatal:
    embedding remains None and the loop continues.

    Shape extraction is deferred to Phase 9 full implementation.
    """
    domain = infer_domain(name, content)

    embedding: Optional[EmbeddingMetadata] = None
    if embedder is not None:
        source = extract_embedding_source(content)
        if source.strip():
            embedding = embedder.embed(source)
            # embed() returns None on failure; that's fine, field stays None

    return RichArtifact(
        name=name,
        content=content,
        domain=domain,
        shape=None,
        structure=None,
        anchors=[],
        resonance_score=0.0,
        embedding=embedding,
    )
