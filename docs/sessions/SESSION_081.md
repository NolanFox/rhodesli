# Session 81 Log
Started: 2026-02-28 ~21:30 EST | Completed: 2026-03-01 ~01:00 EST

## Summary
Connected App — Tree, Map, Location Intelligence, Face Labels + Session 80 Deferred.
Made every page flow together: Photo → Tree → Map → Person with one-click navigation.
Added Gemini location intelligence with GEDCOM-enriched prompts. Labeled faces with names.

## Planned vs Actual
| Act | Planned | Status | Notes |
|-----|---------|--------|-------|
| 0   | Hooks + skills | DONE | Stop hook, /clear gate, notification |
| 1   | Tree navigation | DONE | BFS subtree, nuclear family detect, 34 tests |
| 2   | Face labels + map | DONE | Clickable names, map buttons, 15 tests |
| 3   | Location UX | DONE | Leaflet maps, confidence badges, AD-193, 22 tests |
| 4   | GEDCOM prompts | DONE | AD-192, residential history, Asheville dry-run |
| 5   | Batch re-run | DEFERRED | No Gemini API key locally |
| D1  | Matilda fix | DONE | xref corrected, 9 regression tests |
| D2  | Relationship viz | DONE | Thick lines, hover labels, gen bands, 10 tests |
| D3  | Browser verify | DONE | 12/12 PASS in production |

## Parallelization
- **Round 1**: 4 worktrees from interrupted session (D1, D2, ACT 4, combined location/face/nav)
- **Round 2**: 4 subagents (ACT 1, ACT 2, ACT 3, ACT D3) — all completed and auto-merged
- Session was interrupted mid-execution. Recovered all work from worktrees + subagents.

## Commits
1. `7edfdee` — Phase 0: hooks + skills
2. `ef0cc5c` → `316e1b8` — D1: Matilda GEDCOM fix
3. `50a7cfd` → `097b5ec` — D2: Relationship viz
4. `97b0ef7` → `92e67fc` — Combined location/face/nav
5. `5abf902` → `9cd7a0d` — ACT 4: GEDCOM prompts
6. `9895df5` — Test fix (individuals_count 14→17)
7. `21ba2ba` — ACT 1: Tree smart navigation (auto-merged)
8. `f7879e4` — ACT 3: Location UX tests + AD-193 (auto-merged)
9. `725cb49` — ACT 2: Face labels tests (auto-merged)
10. `f10bbe6` — ACT D3: Browser verification (merged)
11. `46da9f4` — BACKLOG update + resume state

## Test Count
Before: ~2933 → After: 3366+551=3917 (added ~984 new tests)
- 34 tree navigation tests
- 15 face labels/map tests
- 22 location UX tests
- 15 GEDCOM context/extraction tests
- 9 GEDCOM match consistency tests
- 10 tree API tests (relationship viz)

## New Algorithmic Decisions
- **AD-192**: GEDCOM-enriched location prompting — biographical cross-reference for location
- **AD-193**: Photo location data model — schema for location estimates

## New BACKLOG Items
- **PRODUCT-006**: Interactive Photo Chatbot — conversational analysis with GEDCOM context

## Session 81B: Fix Real Issues Found in Browser Verification
Started: 2026-03-01 ~02:00 EST | Completed: 2026-03-01 ~05:00 EST

### Issues Fixed
| Issue | Problem | Fix | Commits | Chrome Verified |
|-------|---------|-----|---------|-----------------|
| 1 | "Face N:" prefix on identified faces | Show only name as clickable link | `daa8c0d` | YES — 4 names without prefix |
| 2 | Leaflet map grey/blank | Script outside `<details>` + polling CDN load | `e13c1c3`, `32af46d` | YES — 10 tiles loaded |
| 3 | Empty tree on photo fb6a846971b30f4b | Include disconnected photo people in subtree | `773867f`, `7fd7228`, `9220855` | YES — Moise+Betty render |

### Lessons Added
- Lesson 90: Script tags inside `<details>` don't execute reliably
- Lesson 91: Leaflet CDN loading requires polling, not DOMContentLoaded
- Lesson 92: Subtree computation must include ALL photo people, even disconnected
- Lesson 93: Verify API response data matches what JS consumer expects
- Lesson 94: Wait for deploy completion before Chrome verification — 502 corrupts JS state
- Lesson 95: Stale JS closure state after fetch failures — fresh navigation required
- Lesson 96: Multi-layered pipeline bugs require iterative fix-verify cycles

### Key Debugging Insight
The tree bug required 3 iterative fixes because the failure had 3 layers:
1. `compute_subtree_for_photo()` excluded disconnected people from `path_union`
2. `if pid in lookup` filter silently dropped GEDCOM xrefs not in lookup
3. Focal person not in returned nodes → JS `buildHierarchy()` BFS starts from nothing

Each fix revealed the next layer. Full Chrome verification after each deploy was essential.

## Deferred to Session 82
1. ACT 5: Batch Gemini re-run with enhanced prompts (needs API key)
2. Location correction backend endpoint (form is placeholder)
3. Pre-existing test failures cleanup
4. Disconnected tree component rendering (JS `buildHierarchy` only walks focal person's connected component)
