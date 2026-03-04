# Session 86b — Route Extraction + Deferred UX Fixes
Started: 2026-03-04
Version: v0.89.0 → v0.90.0
Detailed log: docs/session_logs/session-86b-log.md
Assessment: docs/assessments/session-86b-assessment.md

## Summary
- Extracted compare routes (4,642 lines) and estimate routes (739 lines) from app/main.py
- app/main.py reduced from ~35,800 to ~30,573 lines
- UX-038: POST operations on merged identities redirect to canonical (~15 routes)
- UX-053/056/057: Estimate photo preview, CTAs, form reset
- Critical deploy fix: FastHTML serve() appname parameter prevents duplicate module import
- Browser verification: 6/6 PASS (Playwright)
- 13 new tests. ~4,059 total.

## Commits
1. a4d4d9c - refactor(app): extract compare + estimate routes from main.py
2. 5f999a5 - fix(identity): UX-038 — POST operations on merged identities redirect to canonical
3. b082aae - fix(estimate): UX-053/056/057 — photo preview, CTAs, and form reset on upload
4. 25c5b5a - test: session 86b — merged identity redirect, estimate upload polish
5. 134f4f8 - fix(deploy): add project root to sys.path for route module imports
6. a1f5295 - fix(deploy): register __main__ as app.main to prevent duplicate module
7. 3a78615 - fix(deploy): unconditional sys.modules registration
8. 945551e - debug(deploy): add diagnostic logging (temporary)
9. aeda008 - fix(deploy): pass appname to serve() to prevent duplicate module import
10. 47ad865 - docs(session): session 86b final docs + assessment

## Deploy Fix Root Cause
FastHTML `serve()` derives `appname = Path(__file__).stem` = `"main"`.
Uvicorn does `import main` which imports app/main.py as a SECOND module
with different app/rt objects. Extracted routes register on first module's
rt but Uvicorn serves second module's app → 404.
Fix: `serve(appname="app.main")` + `sys.modules["app.main"]` registration.

## Red Flags
- Context compaction occurred (prior context). /clear between acts not followed.
- 58 pre-existing xdist ordering failures (not introduced by this session)
- Chrome extension unavailable — Playwright used for screenshots
