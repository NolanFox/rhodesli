# Session 81B Assessment — Fix Real Issues Found in Browser Verification
**Date**: 2026-03-01 | **Predecessor**: Session 81

## Shipped

### Issue 1: Face Analysis Labels — "Face N:" Prefix Removed
- [x] Identified faces show ONLY the name as a clickable link (no "Face N:" prefix) — Evidence: commit `daa8c0d`
- [x] Unidentified faces still show "Face N" fallback — Evidence: `app/main.py` face analysis section
- [x] Chrome verified on photo 746dd11e5b4d86a1 — "Anita Capeluto Franco", "Nace Capeluto", "Victoria Capuano Capeluto", "Selma Capeluto" all without prefix

### Issue 2: Leaflet Map Rendering Fixed (4 iterations)
- [x] Iteration 1: Moved `<script>` outside `<details>` element — Evidence: commit `e13c1c3` (Lesson 90)
- [x] Iteration 2: Global DOMContentLoaded + dynamic script loading — Evidence: commit `32af46d` (Lesson 91)
- [x] Chrome verified: 10 map tiles loaded, map fully rendered on photo page

### Issue 3: Family Tree — Empty Tree on Photo fb6a846971b30f4b
- [x] Fix 1: Focal person fallback when filtered out — Evidence: commit `773867f`
- [x] Fix 2: Removed `if pid in lookup` filter from multi-person subtree path — Evidence: commit `7fd7228` (Lesson 93)
- [x] Fix 3: Include ALL disconnected photo people in subtree computation — Evidence: commit `9220855` (Lesson 92)
- [x] Chrome verified: Moise Capeluto's tree renders with Betty Capeluto as child
- [x] Victoria Capeluto's tree still works (3-generation rendering confirmed)

### Lessons Documented
- [x] Lesson 90: Script tags inside `<details>` don't execute reliably — Evidence: `tasks/lessons/ui-lessons.md`
- [x] Lesson 91: Leaflet CDN loading requires polling, not DOMContentLoaded — Evidence: `tasks/lessons/ui-lessons.md`
- [x] Lesson 92: Subtree computation must include ALL photo people, even disconnected — Evidence: `tasks/lessons/ui-lessons.md`
- [x] Lesson 93: Verify API response data matches what JS consumer expects — Evidence: `tasks/lessons/ui-lessons.md`
- [x] Lesson 94: Wait for deploy completion before Chrome verification — Evidence: `tasks/lessons/deployment-lessons.md`
- [x] Lesson 95: Stale JS closure state after fetch failures — Evidence: `tasks/lessons/ui-lessons.md`
- [x] Lesson 96: Multi-layered pipeline bugs require iterative fix-verify — Evidence: `tasks/lessons/harness-lessons.md`

## Red Flags

### LOW: Disconnected components in tree JS
- `buildHierarchy()` in family-tree.js only renders the focal person's connected component. For photo fb6a846971b30f4b, Moise's component (2 people) renders but the disconnected Victoria family (7 people) is invisible despite being in the API response.
- **Impact**: Tree appears small (2 nodes) when photo has 9 identified people across 2 families
- **Fix**: JS-side enhancement to render multiple disconnected components. Future session.

### LOW: Pre-existing e2e flake
- `tests/e2e/test_discovery_layer.py::test_correction_flow_updates_source` — same as session 81

## Deferred
- Disconnected tree component rendering (JS enhancement) — BACKLOG candidate
- Location correction backend endpoint (placeholder from session 81)
- Gemini batch re-run with enhanced prompts (needs API key)

## Next Session Should Verify
1. Tree renders correctly for photos with people from multiple disconnected families
2. Leaflet maps still rendering after any CSS/layout changes
3. Face labels still correct after any face analysis code changes

## Commits (6 total)
1. `daa8c0d` — fix: remove Face N prefix + fix Leaflet map rendering
2. `e13c1c3` — fix: move Leaflet map script outside `<details>` element
3. `32af46d` — fix: use global DOMContentLoaded + dynamic script load for Leaflet
4. `773867f` — fix(tree): focal person fallback when filtered out of nodes
5. `7fd7228` — fix(tree): remove lookup filter from multi-person subtree path
6. `9220855` — fix(tree): include disconnected photo people in subtree computation
