# Session 86b Log — Route Extraction + Deferred UX Fixes
## Mission: Extract compare/estimate routes from main.py, fix UX-038/053/056/057
## Started: 2026-03-04
## Version: v0.89.0 → v0.90.0
## Predecessor: Session 86 (v0.89.0)

### Act 0: Browser-Verify Session 86 Features
- [x] Person page action bar (Timeline, Map, Tree, Connections, Compare) — PASS
- [x] Face overlay labels on photo page — PASS
- [x] Merged identity GET redirect — PASS

### Act 1: Route Extraction (compare + estimate)
- [x] app/compare_routes.py — 4,642 lines, all /compare/* and /api/compare/* routes
- [x] app/estimate_routes.py — 739 lines, /estimate and /api/estimate/* routes
- [x] app/main.py reduced from ~35,800 → 30,573 lines
- [x] Commit: a4d4d9c

### Act 2: UX-038 — Merged Identity POST Guard
- [x] `_check_merged_identity()` helper function
- [x] Guards on ~15 POST routes
- [x] Returns HX-Redirect to canonical identity
- [x] Commit: 5f999a5

### Act 3: UX-053/056/057 — Estimate Upload Polish
- [x] Photo preview in upload results
- [x] "Try Another Photo" + "Share Estimate" CTAs
- [x] Form auto-reset via hx-on::after-request
- [x] Commit: b082aae

### Act 4: Tests
- [x] 13 new tests (9 merged guard + 1 normal behavior + 3 estimate polish)
- [x] Commit: 25c5b5a

### Act 5: Browser Verification + Deploy Fix
- [x] /compare and /estimate 404 in production — root cause: FastHTML serve() duplicate module
- [x] Fix: serve(appname="app.main") + sys.modules registration
- [x] Commits: 134f4f8, a1f5295, 3a78615, 945551e, aeda008
- [x] All routes verified: /compare 200, /estimate 200
- [x] Estimate upload verified: photo preview + CTAs present
- [x] Merged identity redirect: 301 → canonical
- [x] Playwright screenshots saved to docs/screenshots/session-86b/

### Act 6: Assessment + Docs
- [x] Assessment written
- [x] CHANGELOG, BACKLOG, ROADMAP, SESSION_HISTORY, UX_ISSUE_TRACKER updated

### Red Flags
- Context compaction occurred (prior context). /clear between acts not followed.
- 58 pre-existing xdist ordering failures (not introduced by this session)
- Chrome extension unavailable — Playwright used for screenshots
