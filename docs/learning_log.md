## Session 37 — 2025-XX-XX

**Closed:**
- Block A: environment.md committed (32764ad)
- Block B: .gitignore (1ec8275), MISSION + references (be0edf7),
  artifact.py Phase 9 schema (d4eef52), reflector.py model pin (509b63f)

**In progress:**
- Block C: loop.py three-voice JSON refactor — uncommitted, working tree dirty

**Lesson learned:**
Caught two regressions where manual edits accidentally pointed Reflector
base_url at Windows (172.23.224.1) instead of Mac (10.0.0.167), violating
AD-003. Both caught via `git diff` review before commit. Reinforces:
**always diff before staging when hand-editing infrastructure code.**

**Resume pointer:**
Review `git diff nova/core/loop.py | cat`, validate the three-voice JSON
flow + retry logic, commit, then proceed to Block D (Phase 9 shape
extraction) and Block E (Tutor Mode).

**Tech debt unchanged:** TD-001, TD-002, TD-003 all still open.

