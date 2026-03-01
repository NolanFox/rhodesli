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

## Session 81C: Tree Data Fix + Arrow Size + Supabase Sync
Started: 2026-03-01 ~14:00 EST | Completed: 2026-03-01 ~15:30 EST

### Issues Fixed
| Issue | Problem | Fix | Chrome Verified |
|-------|---------|-----|-----------------|
| 1 | Tree shows only 2-7 nodes (should show 17) | Fixed 21 truncated UUIDs in gedcom_matches.json, added gedcom_matches.json fallback to `_build_tree_adjacency()` and `_build_tree_person_lookup()`, synced 1240 rels + 56 matches to Supabase | YES -- 17 nodes confirmed |
| 2 | Photo cycling arrows 28px (below 44px WCAG) | Changed circle r=14 to r=22, font 14px to 18px | YES -- r=22 confirmed |
| 3 | Photo cycling works | Tested via D3 handler invocation: images change correctly | YES -- 3 different photos cycled |
| 4 | Expand/collapse works | Clicked Children button, nodes 17->22 | YES -- 5 new nodes added |

### Root Causes Discovered
1. **Truncated UUIDs**: 21 of 56 identity_id entries in gedcom_matches.json were only 8 chars
2. **Missing fallback**: Tree adjacency builder only used Supabase `gedcom_face_links` for xref mapping, not `gedcom_matches.json`
3. **Stale Supabase data**: Supabase had 1023 relationships (0 with GEDCOM xrefs), local had 1240 (1213 with xrefs)

### Data Pipeline Fix
- `gedcom_matches.json` and `relationships.json` are NOT in git deploy bundle
- They sync FROM Supabase at Railway startup
- Local changes must be pushed TO Supabase using `sync_gedcom_matches()` and `sync_relationships()`
- Fixed by syncing both to Supabase, then redeploying

## Session 81D: Final Chrome Verification Pass
Started: 2026-03-01 ~17:00 EST | Completed: 2026-03-01 ~17:30 EST

### Verification Results (13/13 PASS)
All session 81 features verified in production Chrome browser:
- Face labels, Leaflet map, tree (17 nodes/3 gen), photo cycling, expand/collapse
- Time slider (1860-2003, year display, track fill, photo scrubbing)
- Relationship hover labels (Spouse/Parent→Child + shared photo counts)
- Generation bands (Parents/Focal/Children)
- Line thickness (2-5 based on shared photos)
- Date estimate, location estimate, scene description, people cards

### Key Technical Findings
- Time slider: min=1860, max=2003, scrubPhotos cycles faces based on birth year + lifespan
- Connection lines: `<title>` elements provide native browser tooltips on hover
- Line widths: strokeWidth 2 (no shared), 2.75 (1 shared), 5 (4+ shared)
- Generation bands: 3 SVG rect+text pairs at 0.04 opacity

### No Bugs Found
No UX issues or regressions discovered during verification.

## Deferred to Session 82
1. ACT 5: Batch Gemini re-run with enhanced prompts (needs API key)
2. Location correction backend endpoint (form is placeholder)
3. Pre-existing test failures cleanup
4. Disconnected tree component rendering (JS `buildHierarchy` only walks focal person's connected component)
