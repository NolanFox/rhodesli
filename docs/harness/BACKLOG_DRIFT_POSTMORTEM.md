# Post-Mortem: BACKLOG.md Documentation Drift

## What happened

`docs/BACKLOG.md` was created on 2026-02-08 as a comprehensive 481-line backlog with 120+ items, granular status tracking, and a prioritized execution plan. It was never updated after that initial commit. Meanwhile, `ROADMAP.md` was updated 9 times across 5 sessions (v0.10.0 through v0.14.1), tracking 50+ completed items with dates. The two files drifted by 6 versions and 237 tests (663 → 900).

## Root cause

**A (Missing rule) + B (Ambiguous reference)**

Evidence:

1. **CLAUDE.md line 7**: `For detailed specs on any item, see docs/BACKLOG.md` — this is a READ directive ("go look at it"), not an UPDATE directive ("keep it current").

2. **CLAUDE.md roadmap section** explicitly instructs: "When completing tasks, update ROADMAP.md: change `[ ]` to `[x]`, add date, move to Recently Completed." There is **no parallel instruction for BACKLOG.md**.

3. **Commit message pattern**: Every docs commit mentions "changelog, roadmap, lessons" or "roadmap, changelog, todo". BACKLOG.md was never part of the update pattern because the harness never asked for it.

4. **BACKLOG.md itself** says `tasks/todo.md` is the "authoritative backlog (superseded by this document)" at line 461 — yet `tasks/todo.md` was actually kept more current, suggesting the team naturally gravitated to the simpler file.

## Contributing factors

- **Token cost**: At 481 lines, BACKLOG.md is expensive to read and update. Sessions may have subconsciously avoided it.
- **Redundancy**: ROADMAP.md, CHANGELOG.md, and `tasks/todo.md` already covered the same information in different formats. BACKLOG.md was a fourth copy with no unique enforcement.
- **No verification**: No script or test checked whether BACKLOG.md matched ROADMAP.md. Drift was invisible until manually noticed.

## Timeline

- **2026-02-08 16:39** (commit `b3a4e8c`): BACKLOG.md created — v0.10.0, 663 tests
- **2026-02-08 17:02** (commit `869b706`): First ROADMAP.md update that should have also updated BACKLOG.md (keyboard nav, search)
- **2026-02-08 → 2026-02-10**: 9 ROADMAP.md updates, 0 BACKLOG.md updates
- **2026-02-10**: Gap identified — BACKLOG.md frozen at v0.10.0/663 tests while reality is v0.14.1/900 tests

## Prevention measures

1. **Explicit dual-update rule in CLAUDE.md**: "When completing ANY task, update BOTH ROADMAP.md and docs/BACKLOG.md"
2. **Verification script** (`scripts/verify_docs_sync.py`): Parses both files, reports items completed in ROADMAP but still OPEN in BACKLOG
3. **Automated test** (`tests/test_docs_sync.py`): Makes drift a test failure caught by `pytest tests/`
4. **Lesson #47 in tasks/lessons.md**: Documents this failure mode for future sessions
