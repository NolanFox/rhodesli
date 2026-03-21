# Session 129 Log — Interactive Feedback + Performance + Data Integrity Crisis
Started: 2026-03-21
Mode: interactive
Prompt: docs/prompts/session-129-prompt.md

## Phase Checklist
- [x] Phase 0: Orient + Launch
- [x] Track A: Feedback Collection — 20 items logged (FB-001 through FB-020)
- [x] Track B: Performance — cache headers + async JSON backup shipped
- [x] Track C: Community Scoping Bug Fix — 7 tests, community param on focus card
- [ ] Track D: Observability Audit — DEFERRED
- [x] Track E: Antigravity Monitor — merged, test fix applied
- [x] Phase 1: Merge Track B + C Results — all merged to main
- [x] CRITICAL: Data integrity investigation — identity_overrides root cause found and fixed
- [x] Phase 2: Session End — assessment, CHANGELOG, ROADMAP, deploy

## Baseline
- Tests: 3550 passed (36.66s)
- Version: v0.99.38

## Final
- Tests: 3573 passed (34.19s)
- Version: v0.99.39
- Commits: 15

## Critical Finding: identity_overrides Corruption

### Timeline
1. Feb 22 (Session 59C): `identity_overrides` table created as JSON→Supabase sync mechanism (AD-135)
2. Mar 17 (Session 112): Postgres made source of truth (PRD-051) — but override loading left in `load_from_postgres()`
3. Mar 17-21: Bug invisible because both tables updated in same `save_registry()` path
4. Mar 21 (Session 129): Repair script merged Esther's duplicates by writing to `identities` table only → stale override with 83 faces overwrote correct 112 on next load
5. Mar 21: Root cause found by deep investigation agent — `identity_overrides` applied via `dict.update()` which clobbered correct anchor_ids
6. Mar 21: Fix deployed — override loading removed, 5 structural invariant tests added

### Impact
- 36 faces silently dropped across 4 identities
- 2,279 of 2,369 overrides were stale
- Esther Burd Fox: 83 shown instead of 112
- 9th occurrence of split-brain data pattern (Lesson 153)

### Fix
- Removed override loading from `load_from_postgres()` (core/registry.py)
- Removed `sync_identity_overrides()` from `save_registry()` (app/main.py)
- 5 structural tests that fail if override layer is re-introduced
- Verified: Esther shows 112 faces on production post-deploy

## Data Repairs
- Esther Burd Fox: merged d4f29ffb (29) into 65207728 (83) → 112 anchors. Verified on production.
- Robert Mattatia: merged 142a164e (1) into b9f41a3b (1) → 2 anchors. Verified on production.
- Duplicate name prevention: `confirm_identity()` and `rename_identity()` now check for existing CONFIRMED names. 9 tests.

## Other Work Shipped
- Community scoping fix (Track C): Focus mode stays in community after actions. 8 tests.
- Performance (Track B): 30-day Cache-Control on photos/static, CachedStaticFiles, async JSON backup.
- Antigravity mobile UX: 44px touch targets, text-sm minimum, overflow-x hidden, micro-interactions.
- Test fix: stale assertion (To Review → New Matches).
- 20 feedback items logged (FB-001 through FB-020).

## Feedback Summary
See docs/feedback/session-129-feedback.md for full details.
- 4 P0 items (3 FIXED, 1 root cause identified)
- 5 P1 items (all BACKLOG)
- 7 P2 items (all BACKLOG)
- 4 P3 items (all BACKLOG)
- Root cause chain: FB-016 (photo_faces ID mismatch) → FB-002, FB-003, FB-006, FB-010

## Next Session (130)
Deep data integrity audit + structural prevention. See docs/prompts/session-130-prompt.md.
