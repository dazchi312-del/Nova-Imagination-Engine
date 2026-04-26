# AD #132 — Pragmatic gpu_enabled reporting (Option B)

**Status:** Accepted (retroactive)
**Date:** 2026-04-25
**Session:** Project Nova S29
**Related:** AD #133 (GPU requires gVisor bypass)

## Context

execute_sandboxed() accepts a gpu_access: bool parameter. The result
dataclass exposes gpu_enabled: bool. Question: what does gpu_enabled
report on each return path?

## Decision

gpu_enabled reports the requested gpu_access for paths where a
container launch was attempted:

- SUCCESS / OOM / ERROR -> gpu_enabled = gpu_access
- TIMEOUT -> gpu_enabled = gpu_access
- EXCEPTION (during docker run) -> gpu_enabled = gpu_access

Early returns report False:

- BLOCKED (policy rejection)
- SYNTAX_ERROR (pre-launch parse failure)
- DOCKER_MISSING (preflight failure)

## Rationale

"Was GPU access attempted?" is the question callers actually need answered.
A timeout or runtime error during a GPU-enabled run is still a GPU-enabled
run from the caller's perspective. Early returns never reached the runtime,
so reporting False is honest.

## Consequences

Six return sites in sandbox.py must follow this pattern. Verified against
lines 86, 177, 204, 218, 280, 287, 295, 322 (8 hits across construction
and reads).
