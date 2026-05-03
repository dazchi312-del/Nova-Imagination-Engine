# Phase 9 Closeout — Persistence Boundary Consolidation

**Status:** Closed
**Commit:** `42198de`
**Date:** 2026-05-03

---

## 1. Context

Phase 9 was scoped as the scaffolding pass for shape extraction: introduce
`ShapeDescriptor` and `StructuralMetadata`, prepare the loop to consume them,
defer live AST extraction to Phase 10.

What it became, in practice, was a persistence-layer consolidation. The shape
work is still scaffolded (see §7), but the bulk of the phase was spent
removing a serialization fork that would have poisoned every downstream
phase.

## 2. The Drift

Two serialization paths had grown in parallel:

- `to_dict()` methods on the in-memory dataclasses (`RichArtifact`,
  `IterationRecord`), inherited from pre-Pydantic days.
- `IterationRecordV1` in `nova/core/schemas.py`, the canonical Pydantic model.

Both could write JSON. Neither was authoritative. Records on disk were a
silent mix depending on which code path produced them. No test caught it
because both paths produced valid-looking JSON.

This was invisible in the test suite and would have remained invisible until
some Phase 10+ consumer hit a field that only one path emitted.

## 3. Decision — Path A

Strict Pydantic boundary. Specifically:

- Dataclasses remain in-memory only. No serialization methods on them.
- `nova/core/schemas.py` is the **only** module that defines persisted shape.
- All disk writes route through Pydantic models.
- `to_dict()` methods removed from `RichArtifact` and `IterationRecord`.

The alternative (Path B: make dataclasses authoritative, delete schemas.py)
was rejected because Pydantic gives us validation, versioning, and a clean
migration story for free.

## 4. The Shim

`_write_iteration` in `nova/core/loop.py` is the single translation point.
It accepts the in-memory `IterationRecord` dataclass, constructs an
`IterationRecordV1`, and writes the validated JSON. Internal code never sees
the v1 model; external storage never sees the dataclass.

This is the boundary. Phase 10+ extends `IterationRecordV1` (or introduces
`V2`); it does not add new write paths.

## 5. Path α — Legacy Records

35 pre-v1 records exist on disk from earlier smoke runs. Decision: preserve,
do not migrate.

- `scripts/replay_schema_check.py` classifies each record as `OK` (v1),
  `LEGACY` (no schema_version), or `FAILURE` (malformed).
- New writes are strict v1.
- Legacy records remain readable for forensics; they will not be retroactively
  rewritten.

If a future phase needs uniform historical data, write a one-shot migration
script. Do not soften the write path.

## 6. Verification

- Full suite: **132/132 passing**.
- Live iteration: `nova --max-iterations 1 --experiment-id schema_v1_verify_001`
  produced `iter001_record.json` with `schema_version: 1` and 20 schema-aligned
  top-level keys.
- Replay check: OK count incremented 2 → 3, legacy count unchanged at 35,
  zero failures.

The shim is empirically validated against the live persistence path, not just
unit tests.

## 7. Deferred to Phase 10+

`ShapeDescriptor` and `StructuralMetadata` remain as dataclasses in
`artifact.py`. They have no live consumers yet. They will migrate to Pydantic
when Phase 10 wires AST extraction into `loop.py` and they begin appearing in
persisted records.

Migrating them now would be speculative; migrating them when they have a
consumer is mechanical.

## 8. Lessons

The dual-path drift was caught because the workflow forced eyes on every
diff: terminal-only editing, raw `git log`, no IDE-mediated abstraction over
the file system. An IDE that auto-formats and hides whitespace would have
made the parallel `to_dict` paths look like noise.

Schema boundaries are cheap to enforce when there is one. They are
catastrophic to retrofit when there are many. Phase 9 paid that cost early.

