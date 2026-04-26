# ADR-134: Two-tier memory architecture

**Status:** Accepted (2026-04-25)  
**Context:** Reflector context saturates if fed raw episode history.  
**Decision:** Tier 1 (episodes) is immutable, append-only SQLite. Tier 2 (beliefs + deltas) is derivable from Tier 1.  
**Consequences:**
- Tier 1 schema changes require migration discipline.
- Tier 2 can be dropped and rebuilt at any time.
- `rebuild_beliefs_from_episodes()` is mandatory from Phase 2 day 1.
- Schema frozen after first 10 episodes.
