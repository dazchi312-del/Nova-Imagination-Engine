# Logic Skeleton Spike — Results

**Date**: 2025-01-XX  
**Commit at run**: f023e4b  
**Hypothesis**: Embeddings capture semantic identity; AST shape captures
structural identity. The two are orthogonal and both are needed for
retrieval by analogy.

## Method

Three FizzBuzz implementations (`imperative`, `recursive`, `functional`)
processed through:
1. `PythonASTExtractor` → `ShapeDescriptor` + `StructuralMetadata`
2. `sentence-transformers/all-MiniLM-L6-v2` → cosine similarity

All three variants produce identical output for n ∈ [1, 15].

## Results

### Structural Shape

| variant | primary | ast_depth | cyclomatic | fn | cls |
|---|---|---|---|---|---|
| imperative | small-functional | 5 | 5 | 1 | 0 |
| recursive  | small-functional | 4 | 6 | 1 | 0 |
| functional | small-functional | 1 | 5 | 1 | 0 |

### Embedding Cosine Similarity

| pair | cosine |
|---|---|
| imperative ↔ recursive  | 0.9106 |
| imperative ↔ functional | 0.8848 |
| recursive  ↔ functional | 0.9029 |

Mean similarity: **0.899**, range: **0.026**.

## Findings

1. **Thesis confirmed.** Embeddings cluster the three variants tightly
   (all pairs > 0.88) while shape metrics diverge cleanly. The two
   signals are orthogonal.

2. **`ast_depth` is the strongest discriminator** in this sample
   (5 / 4 / 1). The 5× spread between imperative and functional is
   structurally unambiguous.

3. **`cyclomatic_complexity` captures the recursion base case**
   (recursive = 6 vs. others = 5). Useful as a secondary signal.

4. **`primary` label is uninformative** — all three collapse to
   `"small-functional"`. The categorical taxonomy needs refinement,
   or `primary` should be treated as a coarse pre-filter while
   `StructuralMetadata` carries the discriminative load.

## Implications for Phase 10

- ✅ **Proceed with shape as a first-class index alongside vectors.**
- ⚠️ **Refine `ShapeDescriptor.primary` taxonomy** — current labels are
  too coarse to be useful in isolation.
- 🎯 **Retrieval by analogy is viable**: query for high vector
  similarity AND high shape distance to surface alternative
  implementations of similar concepts.

## Next Steps

1. Phase 10 Step 3: integrate `_safe_extract` into `artifact.py` and
   `_write_iteration` in `loop.py`.
2. Phase 10 Step 4: extend `replay_schema_check.py` with
   `OK_NO_SHAPE` / `OK_WITH_SHAPE` distinction.
3. Future: dual-index retrieval prototype (vector ∩ shape).
