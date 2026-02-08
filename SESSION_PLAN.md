# Session 3 Plan — Autonomous Stabilization

## Top 3 Existential Risks

1. **Merge direction (BUG-003) is ALREADY FIXED in code** — `resolve_merge_direction()` auto-corrects, name conflicts handled, undo exists. But there are NO direction-specific tests (`auto_correct_direction=False` in all existing merge tests). Risk: regression without test coverage.

2. **Lightbox navigation keeps breaking** — `photoNavTo()` uses DOM-bound listeners that die on HTMX swap. Fixed 3 times, needs event delegation pattern (permanent fix).

3. **Face count / collection stats mismatch** — BUG-002 and BUG-004 are UI trust bugs. Face count shows detection count (`len(faces)`) but overlays may be filtered. Collection stats computed inline in multiple places.

## Execution Order

### Phase 1: Merge Safety Tests (~20 min)
- Merge code is already implemented correctly
- Write comprehensive direction-specific tests (the gap)
- Verify undo_merge works end-to-end
- Update ROADMAP: mark BUG-003 as fixed
- Sequential (safety-critical)

### Phase 2: UI Trust Fixes (~25 min)
- 3 parallel subagents: lightbox, face count, collection stats
- Each writes regression test first, then implements fix

### Phase 3: Navigation & Search (~20 min)
- 2 parallel subagents: keyboard nav, instant search
- Event delegation pattern for all interactive elements

### Phase 4: Landing Page (~15 min)
- Landing page already exists at / (built in v0.10.0)
- Verify and enhance if needed

### Phase 5: Data Sync, Skip Hints, Ranking (~15 min)
- Admin export endpoint already exists
- Add skip resurfacing with ML hints
- Add relative identity ranking (confidence gap)

### Phase 6: Hardening & Docs (~15 min)
- Smoke tests, about page, docs refresh

## Parallelization Map

| Phase | Strategy | Rationale |
|-------|----------|-----------|
| 1 Merge Tests | Sequential | Safety-critical gap filling |
| 2 UI Fixes | 3 parallel subagents | Independent DOM fixes |
| 3 Nav/Search | 2 parallel subagents | Independent features |
| 4 Landing | Assess first | May already be done |
| 5 Sync/ML | Sequential | Interrelated |
| 6 Hardening | Sequential | Depends on prior work |

## Key Discovery: BUG-003 Already Fixed
The merge system in `core/registry.py` already has:
- `resolve_merge_direction()` (lines 255-344): Named identity always wins
- Name conflict detection with UI modal
- State promotion (max of target/source state)
- `merge_history` recording per-identity
- `undo_merge()` method (lines 557-650+)
- Design doc at `docs/design/MERGE_DESIGN.md` (563 lines, comprehensive)

The only gap: tests use `auto_correct_direction=False`, so direction logic is untested.
