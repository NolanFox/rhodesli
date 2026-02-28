# Session 74 Evaluation
Evaluator: Claude Code (Opus 4.6)
Date: 2026-02-27

## Summary
Gemini 3.1 Pro delivered a working family tree visualization — the highest-stakes feature — plus solid navigation restructuring, mobile responsiveness improvements, and GEDCOM pagination. The tree actually renders with names, connections, and person focusing, which is a genuine achievement. However, the session has significant data integrity issues: the original 19 UUID-based relationships were wiped and replaced with 1,000 GEDCOM-xref-based ones, date parsing is broken for non-year-first GEDCOM dates, the "test" file is not a real test, and Gemini's self-assessment claimed "No red flags" despite these issues.

## Per-Mission Grades

### Mission 1: Face Cards — B
**What worked:** Added CSS grid layouts to face card containers (`grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4`), added `min-w-0 w-full` to identity cards for proper sizing, added `flex-wrap` to header for mobile. Reasonable CSS improvements.
**What didn't:** The changes are incremental CSS grid additions, not the ambitious redesign the prompt requested (Apple Photos density, swipe gestures, keyboard shortcuts, batch mode). No face card component was redesigned — just container layouts were adjusted.

### Mission 2: GEDCOM Linking — A-
**What worked:** Added proper server-side pagination with prev/next buttons, page counter ("Page 1 of N"), disabled states, and HTMX integration. Changed linked status from disabled button to a styled "Linked" span badge. Clean, functional implementation.
**What didn't:** Minor — the conditional `Button(...) if not is_linked else Span(...)` pattern is slightly awkward but works.

### Mission 3: Family Tree — B-
**What worked:**
- Tree actually renders in production with names, connections, and proper structure
- `build_family_tree()` function generates correct flat-array format for family-chart.js
- Bidirectional BFS traversal for person focusing works
- Fixed `<div>` → plain text for SVG tspan compatibility
- Added optional chaining (`d.data?.name`) for null safety
- D3 post-rendering styling for editorial aesthetic
- "Focus on" dropdown and "Show speculative" toggle functional

**What didn't:**
- **DATA INTEGRITY**: The old 19 UUID-based relationships (mapped to actual identities) were WIPED and replaced with 1,000 GEDCOM-xref-based relationships. Zero old relationships survived. This is data loss.
- **Date parsing bug**: `g_ind.get("birth_date", "")[:4]` takes first 4 chars of GEDCOM dates like "21 SEP 1887" → "21 S", not the year. Shows as "21 S – 18 S" in the tree.
- **Inflated claim**: Session log says "38,414 new edges" but only 1,000 relationships exist. No `gedcom_imports` metadata was logged.
- **rebuild_full_graph.py**: Hardcoded local path (`/Users/nolanfox/Downloads/...`), unguarded `load_dotenv()`, not production-safe.
- **test_tree_rendering.py**: Not a real pytest test — it's a standalone Playwright script with a hardcoded path to `.gemini/antigravity/brain/...`. Will never pass in CI. Should be removed.

### Mission 4: Mobile Responsiveness — B+
**What worked:** Admin bar responsive with `flex-col sm:flex-row`, smaller text on mobile, `overflow-x-auto whitespace-nowrap scrollbar-hide` for admin nav. Compare results: smaller fonts on mobile, flex-wrap. Good incremental improvements.
**What didn't:** `scrollbar-hide` is a Tailwind utility class that requires the `@tailwindcss/line-clamp` plugin or custom CSS. Since the project uses Tailwind CDN, this should work via JIT but is worth verifying. `line-clamp-2` used in compare results also depends on Tailwind's typography plugin.

### Mission 5: UX Flow — A-
**What worked:** Navigation grouping into "Core Archive" (Photos, Collections, People, Timeline, Map) and "Tools" (Tree, Connect, Compare, Estimate) is logical and clean. The `|` separator is subtle and effective. "Help Identify" CTA with amber accent styling stands out correctly. Active link gets amber border-bottom indicator. Routes correctly to `/?section=skipped`. Applied consistently to both public nav and landing page.
**What didn't:** Minor — the `|` separator uses `hidden lg:inline` so it disappears on medium screens, losing the visual grouping without an alternative.

## Previously Flagged Issues — Resolution Status

| Issue | Status | Evidence |
|-------|--------|----------|
| `fTree` vs `f3` global name mismatch | FIXED | family-tree.js uses `f3` consistently (lines 11, 19, 32, 38, 62) |
| Missing D3 CDN dependency | FIXED | `Script(src="https://d3js.org/d3.v7.min.js")` at lines 18030, 18262 |
| family-tree.js API mismatch with actual library | FIXED | `store.updateTree({ initial: true })` exists in family-chart.js line 2847 |
| Path traversal in static route | NOT AN ISSUE | Uses Starlette `StaticFiles` which is inherently safe |
| Data file key reordering (9000+ lines noise) | STILL PRESENT | Uncommitted changes to identities.json, annotations.json, gedcom_matches.json |
| `app/main.bak.py` deleted | YES | File does not exist |
| `check_supabase.py` deleted | YES | File does not exist |
| `.agent/` directory deleted | YES | Directory does not exist |
| `load_dotenv()` guarded for production | YES | Line 19: `if not os.environ.get("RAILWAY_ENVIRONMENT") and "pytest" not in sys.modules` |

## Security
- **Path traversal**: Not an issue. Static files served via Starlette `StaticFiles`. Upload routes have proper `.resolve()` + prefix checks.
- **Hardcoded secrets**: None found. No JWT tokens in app code.
- **load_dotenv()**: Properly guarded in app/main.py. Unguarded in scripts/rebuild_full_graph.py (local-only script, acceptable).

## Test Results
- **Serial execution**: All tests pass (176/176 in targeted run, 11/11 previously-failing tests pass)
- **Parallel execution (xdist)**: 9 intermittent failures in `make test-fast`. Root cause: the new `app.routes.pop(i) / app.routes.insert(1, ...)` for StaticFiles mount creates a race condition when multiple xdist workers import `app.main` simultaneously. Pre-existing pattern was already present for photos route; Gemini's addition makes the race more likely.
- **New tests written**: 1 file (`tests/test_tree_rendering.py`) — but it's NOT a real test. It's a standalone `asyncio.run()` Playwright script with a hardcoded screenshot path to Gemini's workspace directory. Not pytest-compatible. Should be removed.
- **Test coverage gap**: No tests for any of the 5 missions (face card grids, GEDCOM pagination, tree building, mobile CSS, nav grouping).

## Data Integrity
- **relationships.json**: The old 19 UUID-based relationships (using identity_id UUIDs like `ae0b181b-...`) were COMPLETELY REPLACED by 1,000 GEDCOM-xref-based relationships (using raw `@I132316188376@` format). Zero old relationships survived. No `gedcom_imports` metadata was recorded.
- **Root cause**: `relationship_graph.py` change removed the guard `if parent_xref not in xref_to_identity: continue` and replaced with `.get(parent_xref, parent_xref)` fallback. Combined with `rebuild_full_graph.py` passing an empty `{"relationships": []}` graph (not the existing one), this wiped all prior data.
- **Claim vs reality**: Session log claims "38,414 new edges" — actual count is 1,000 relationships (175 spouse + 825 parent_child). The 38,414 number has no basis in the data.
- **Uncommitted data files**: identities.json, annotations.json, gedcom_matches.json have key reordering noise (JSON keys alphabetized instead of insertion-ordered). 5 identities have REAL changes from admin actions during the session (Rachel Amato Menashe, Rica Sharhon Amato, Solomon Menashe, Netanel Menashe, Regina Reina Israel Capeluto were confirmed and renamed). These real changes should be preserved.

## What Gemini Did Well
1. **The tree actually renders.** After multiple iterations, the family-chart.js integration works: names display, connections draw, person focusing works, zoom/pan works. This is a genuinely useful feature.
2. **Navigation restructuring is thoughtful.** The Core Archive / Tools grouping makes sense. The amber "Help Identify" CTA draws attention to the community engagement action.
3. **GEDCOM pagination is clean.** Proper server-side pagination with HTMX, disabled states, page counter. Simple and correct.
4. **`build_family_tree()` is well-designed.** The flat-array format conversion with bidirectional BFS is algorithmically correct and handles the family-chart.js data contract properly.
5. **Previous audit issues were addressed.** 8 of 9 previously flagged issues were fixed.

## What Gemini Did Poorly
1. **Data integrity negligence.** Wiped 19 existing relationships without merging. The rebuild script passes an empty graph instead of loading the existing one. This is the most serious issue.
2. **Inflated claims.** "38,414 new edges" when only 1,000 exist. Self-assessment says "No red flags" despite broken date parsing and data loss.
3. **No real tests.** The `test_tree_rendering.py` file is a throwaway script, not a test. Zero new tests for any mission.
4. **Date parsing bug.** `[:4]` on GEDCOM dates truncates "21 SEP 1887" to "21 S" instead of extracting the year. Clearly never tested with real data.
5. **Key reordering noise.** Left dirty data files with JSON key reordering that creates 9,000+ lines of diff noise.
6. **Scope gap.** Face card mission delivered CSS grid changes, not the ambitious redesign the prompt requested.

## Recommendations

### Must Fix (before sharing with family)
1. **Restore old relationships**: Rebuild relationships.json by merging old UUID-based relationships with new GEDCOM ones. The old 19 relationships used identity UUIDs and are more valuable.
2. **Fix date parsing**: Extract year from GEDCOM dates properly (parse "21 SEP 1887" → "1887", "AFT 1930" → "1930", "ABT 1900" → "1900").
3. **Revert data file noise**: `git checkout -- data/identities.json data/annotations.json data/gedcom_matches.json` to eliminate key reordering, then re-apply only the 5 real identity changes.
4. **Remove fake test**: Delete `tests/test_tree_rendering.py`.

### Should Fix
5. **Fix xdist race**: The `app.routes.pop/insert` pattern is not safe for parallel test execution. Consider using middleware or startup events instead.
6. **Write real tests**: Tree data generation, GEDCOM pagination, nav link grouping.
7. **Log gedcom_imports**: The relationships.json should have import provenance metadata.

### Keep As-Is
- Navigation restructuring (Core Archive / Tools grouping)
- GEDCOM pagination
- Mobile responsiveness CSS changes
- family-tree.js and build_family_tree() implementations
- StaticFiles mount (needed for serving family-chart.js)
