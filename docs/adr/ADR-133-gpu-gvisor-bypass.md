# AD #133 — GPU access requires gVisor bypass

**Status:** Accepted
**Date:** 2026-04-25
**Session:** Project Nova S29
**Related:** AD #132 (gpu_enabled reporting)

## Context

The sandbox uses gVisor (runsc) as its default runtime to interpose
syscalls and provide a user-space kernel boundary. The NVIDIA container
runtime is required for GPU passthrough. These two runtimes are mutually
exclusive at the docker run layer — only one can be selected per container.

## Decision

When gpu_access=True, the sandbox swaps runsc for the nvidia runtime and
injects --gpus all. When gpu_access=False, runsc remains the runtime.

The runtime_used field on the result dataclass reflects the actual runtime
selected (nvidia or runsc), not the requested one.

When the GPU path is taken, emit a structured log line:
gpu_path_taken runtime=nvidia gvisor=disabled

## Rationale

GPU workloads are a deliberate, opt-in escalation. Callers asking for
gpu_access are accepting the tradeoff. Logging the bypass makes the
security posture auditable after the fact.

## Consequences

GPU-enabled runs lose gVisor syscall interposition. The remaining
hardening layers still apply:

- network=none
- cap-drop=ALL
- no-new-privileges
- read-only filesystem
- user=65534 (nobody)
- cpu/memory/pids resource limits

This is a reduced but non-trivial isolation envelope. Non-GPU runs retain
full gVisor protection.
