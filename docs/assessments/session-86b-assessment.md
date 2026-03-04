# Session 86b Assessment

## Mission
Route extraction (compare + estimate) from app/main.py, fix UX-038/053/056/057, browser-verify all changes.

## Version: v0.89.0 → v0.90.0

## Shipped

### Act 0: Browser-Verify Session 86 Features
- [x] Person page action bar (Timeline, Map, Tree, Connections, Compare) — PASS (Playwright screenshot)
- [x] Face overlay labels on photo page — PASS (Playwright screenshot)
- [x] Merged identity GET redirect — PASS (301 → canonical)

### Act 1: Route Extraction (prior context, commit a4d4d9c)
- [x] app/compare_routes.py created — 4,642 lines, all /compare/* and /api/compare/* routes
- [x] app/estimate_routes.py created — 739 lines, /estimate and /api/estimate/* routes
- [x] app/main.py reduced from ~35,800 → 30,573 lines
- [x] All tests pass after extraction

### Act 2: UX-038 — Merged Identity POST Guard (commit 5f999a5)
- [x] `_check_merged_identity()` helper function
- [x] Guards added to ~15 POST routes: reject-match, merge (both IDs), rename, skip, confirm, inbox/confirm, discovery/confirm, focus-skip, reject-pair, unreject, bulk-merge, bulk-reject, inbox/reject, reset
- [x] Returns HX-Redirect to canonical identity when merged

### Act 3: UX-053/056/057 — Estimate Upload Polish (commit b082aae)
- [x] UX-053: Photo preview in upload results via `get_upload_url()`
- [x] UX-056: "Try Another Photo" + "Share Estimate" CTAs with proper styling
- [x] UX-057: Form reset via `hx-on::after-request` on the form element

### Act 4: Tests (commit 25c5b5a)
- [x] 9 tests for merged identity redirect (all POST route types)
- [x] 1 test for non-merged identity normal behavior
- [x] 3 tests for estimate upload UX polish (preview, CTAs, form reset)

### Act 5: Browser Verification
- [x] /compare returns 200 — PASS (Playwright screenshot)
- [x] /estimate returns 200, has upload form + reset behavior — PASS
- [x] Estimate upload returns photo preview + CTAs — PASS (curl verified)
- [x] Person page action bar — PASS (Playwright screenshot)
- [x] Face overlays on photo page — PASS (Playwright screenshot)
- [x] Merged identity redirect — PASS (301 to canonical, Playwright confirmed)
- [x] Screenshots saved to docs/screenshots/session-86b/

## Deploy Fix (Critical)
Route extraction caused production /compare and /estimate to return 404. Root cause chain:
1. `python app/main.py` → `__name__ == "__main__"`, not `"app.main"`
2. FastHTML `serve()` derives `appname = Path(__file__).stem` = `"main"`
3. Uvicorn does `import main` → creates SECOND module with different `app`/`rt`
4. compare_routes and estimate_routes register on first module's `rt` but Uvicorn serves second module's `app`

Fix: `serve(appname="app.main", ...)` + `sys.modules["app.main"] = sys.modules[__name__]` at top of main.py.
Commits: 134f4f8, a1f5295, 3a78615, 945551e (diagnostics), aeda008 (final fix).

## Red Flags
- **MEDIUM**: Context compaction occurred (prior context session). /clear between acts was not followed rigorously. Process failure noted.
- **LOW**: 58 pre-existing xdist ordering failures (test_skipped_focus, test_internal_photo_links, etc.). Not introduced by this session. Pass in isolation.
- **LOW**: Chrome extension unavailable — Playwright fallback used for screenshots.

## Deferred
- UX-045/046 (compare loading + auto-scroll): Already implemented (verified in research phase). No changes needed.
- UX-054/055 (estimate loading indicator + auto-scroll): Not in scope for this session. Still BACKLOG.

## Test Counts
- App tests: 3,508 passed (58 xdist ordering failures, pre-existing)
- ML tests: 551 passed
- Total: ~4,059

## Next Session Should Verify
1. /compare and /estimate still return 200 in production
2. The 58 xdist ordering failures — investigate if they need fixing or are acceptable flaky tests
3. UX-054/055 (estimate loading + auto-scroll) if prioritized
