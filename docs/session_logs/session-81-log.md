# Session 81 Log — Connected App: Tree, Map, Location, Face Labels

Started: 2026-03-01
Prompt: docs/prompts/session-81-prompt.md
Assessment: docs/assessments/session-81-assessment.md
Version: v0.83.0 → v0.83.2

## State at Start
- Version: v0.82.1
- Tests: ~2933 (2395 app + 538 ML)
- Branch: main
- Identities: 775 total, 60 confirmed
- GEDCOM matches: 56 confirmed

## Sub-Sessions

| Sub-Session | Focus | Commits | Key Outcome |
|---|---|---|---|
| **81** | Core features (Acts 1-5 + deferred) | 18 | Tree nav, face labels, location UX, GEDCOM prompts, viz |
| **81B** | Browser verification fixes | 6 | Face prefix fix, Leaflet polling, subtree logic |
| **81C** | Data consistency + WCAG | 2 | 21 truncated UUIDs fixed, 44px arrows, Supabase sync |
| **81D** | Final verification gate | 0 | 13/13 Chrome verification PASS |

## Phase Checklist
- [x] ACT 1: Photo→Tree Smart Navigation — 34 tests (`tests/test_tree_navigation.py`)
- [x] ACT 2: Face Labels + Map Navigation — 15 tests (`tests/test_face_labels_map.py`)
- [x] ACT 3: Location UX — 22 tests (`tests/test_location_ux.py`)
- [x] ACT 4: GEDCOM-Enriched Location Prompts — 15 tests (gedcom_context + gemini_extraction)
- [x] ACT D1: Matilda GEDCOM Fix — 9 tests (`tests/test_gedcom_match_consistency.py`)
- [x] ACT D2: Relationship Visualization — 10 tests (`tests/test_tree_api.py`)
- [x] ACT D3: Browser Verification of Session 80 — 12/12 PASS
- [ ] ACT 5: Batch Gemini Re-run — DEFERRED (no API key locally)

## Issues Found in Browser Verification (81B)

### Issue 1: "Face N:" Prefix on Identified Faces
- **Found**: Chrome showed "Face 2: Victoria Capuano Capeluto" instead of just the name
- **Root cause**: `Span(f"Face {i}: ", ...)` at line 1770
- **Fix**: Removed prefix span (commit `daa8c0d`)

### Issue 2: Leaflet Map Blank (Grey Tiles)
- **Found**: Map container rendered but tiles didn't load
- **Root cause A**: Script inside `<details>` didn't execute (Lesson 90)
- **Root cause B**: `DOMContentLoaded` doesn't fire on HTMX swaps (Lesson 91)
- **Fix**: Moved script outside `<details>`, polling-based CDN check + `map.invalidateSize()`

### Issue 3: Tree Missing People (7 nodes instead of 17)
- **Found**: Photo fb6a846971b30f4b showed truncated tree
- **Root cause**: 21 truncated UUIDs in `gedcom_matches.json` + `if pid in lookup` filter
- **Fix**: Full UUID resolution, xref fallback in tree builders, removed filter (81C)
- **Result**: 7 → 17 nodes

### Issue 4: Arrow Touch Targets Too Small (28px)
- **Found**: Photo cycling arrows below WCAG 44px minimum
- **Fix**: Radius 14→22, font-size 14→18px (81C)

## Lessons Documented
- Lesson 90: Script tags inside `<details>` don't execute reliably
- Lesson 91: Leaflet CDN loading requires polling, not DOMContentLoaded
- Lesson 92: Subtree computation must include ALL photo people, even disconnected
- Lesson 93: Verify API response data matches what JS consumer expects
- Lesson 94: Wait for deploy completion before Chrome verification — 502 corrupts JS state
- Lesson 95: Stale JS closure state after fetch failures — fresh page navigation required
- Lesson 96: Multi-layered pipeline bugs require iterative fix-verify cycles

## Algorithmic Decisions
- AD-192: GEDCOM-Enriched Location Prompting (residential history, children birth places, spouse events)
- AD-193: Photo Location Data Model and UX (lat/lng, confidence, Leaflet maps)

## Deferred Work
- ACT 5: Batch Gemini re-run with enhanced prompt (needs API key)
- Location correction backend endpoint (placeholder form exists)
- Disconnected tree component rendering (JS only renders focal connected component)

## Final Verification (81D) — 13/13 PASS
| # | Feature | Status |
|---|---------|--------|
| 1 | Face labels (names, clickable links) | PASS |
| 2 | Leaflet map (NYC, OSM/CARTO tiles) | PASS |
| 3 | Tree rendering (17 nodes, 3 generations) | PASS |
| 4 | Photo cycling arrows (44px) | PASS |
| 5 | Expand/collapse buttons | PASS |
| 6 | Time slider (1860-2003) | PASS |
| 7 | Hover labels (Spouse, Parent→Child) | PASS |
| 8 | Generation bands | PASS |
| 9 | Line thickness (shared photos) | PASS |
| 10 | Date estimate | PASS |
| 11 | Location estimate + map | PASS |
| 12 | Scene AI description | PASS |
| 13 | People in photo cards | PASS |

## Test Results
- Final: 3917 total (3366 app + 551 ML)
- New tests: ~97 across 6 test files
- Pre-existing flake: `test_correction_flow_updates_source` (e2e, unrelated)
