"""
Logic Skeleton Spike — comparison harness.

Runs three FizzBuzz variants through:
  1. PythonASTExtractor  -> structural shape divergence
  2. Embedding model     -> semantic similarity (cosine)

Hypothesis: embeddings cluster all three as near-identical (same task,
same tokens), while shape metrics diverge sharply (loop vs. recursion
vs. comprehension).
"""
from __future__ import annotations

import itertools
from typing import Dict

from nova.core.extractors.python_ast import PythonASTExtractor
from nova.experiments.skeleton_spike.samples import VARIANTS


def extract_all() -> Dict[str, dict]:
    extractor = PythonASTExtractor()
    out = {}
    for name, src in VARIANTS.items():
        result = extractor.extract(f"{name}.py", src.encode("utf-8"))
        out[name] = {
            "shape": result.shape,
            "structure": result.structure,
        }
    return out


def print_shape_table(extracted: Dict[str, dict]) -> None:
    print("\n=== STRUCTURAL SHAPE ===")
    print(f"{'variant':<12} {'primary':<20} {'depth':<6} {'cc':<4} {'fn':<3} {'cls':<3}")
    print("-" * 56)
    for name, data in extracted.items():
        s, st = data["shape"], data["structure"]
        print(f"{name:<12} {s.primary:<20} {st.ast_depth:<6} "
              f"{st.cyclomatic_complexity:<4} {st.function_count:<3} {st.class_count:<3}")


def print_embedding_table(extracted: Dict[str, dict]) -> None:
    """Optional: requires sentence-transformers."""
    try:
        from sentence_transformers import SentenceTransformer, util
    except ImportError:
        print("\n[embedding skipped: sentence-transformers not installed]")
        return

    model = SentenceTransformer("all-MiniLM-L6-v2")
    names = list(VARIANTS.keys())
    embs = model.encode([VARIANTS[n] for n in names], convert_to_tensor=True)

    print("\n=== EMBEDDING COSINE SIMILARITY ===")
    print(f"{'pair':<28} {'cosine':<8}")
    print("-" * 38)
    for a, b in itertools.combinations(range(len(names)), 2):
        sim = float(util.cos_sim(embs[a], embs[b]))
        print(f"{names[a]:<12} <-> {names[b]:<12} {sim:.4f}")


if __name__ == "__main__":
    extracted = extract_all()
    print_shape_table(extracted)
    print_embedding_table(extracted)
