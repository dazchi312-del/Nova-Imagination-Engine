# ADR-135: Single-writer constraint, HTTP boundary

**Status:** Accepted (2026-04-25)  
**Context:** SQLite on network filesystems corrupts. Two-node loop needs shared memory access.  
**Decision:** One process owns `episodes.db`. Other nodes use HTTP. DB file lives on M4 Pro local disk.  
**Consequences:**
- MemoryStore API must be HTTP-wrappable (no path leakage).
- Phase 1 runs single-node; Phase 1.5 adds the service.
- update/delete methods are forbidden by design.
