# Session 85b Assessment: Compare Navigation + PRD-025 Gap Closure

**Date:** 2026-03-03
**Session:** 85b
**Predecessor:** Session 85 (v0.87.0)
**Version:** v0.87.1

## Shipped

- [x] **Phase 0: Orient** — Session files created, PRD-025 and session 85 assessment reviewed
  - Evidence: `.claude/current_session.txt` set to 85b, session log created

- [x] **Phase 1: Archive Photo → Compare** — New route + UI for comparing archive photos without re-upload
  - New `GET /api/compare/from-photo?photo_id=X&identity_id=Y` route
  - Per-face distance computation against reference person (same engine as vs-person)
  - Calibrated confidence scores + tier classification
  - Merge/Not Same admin actions on each face
  - Reference person context (existing top archive matches)
  - Shareable result saved to comparison_results.json
  - New `GET /api/compare/search-person-photo` for photo-scoped person search
  - `/compare?photo_id=X&person_id=Y` auto-loads comparison via HTMX
  - `/compare?photo_id=X` shows photo faces + person search
  - Evidence: 8 new tests, all passing (30 total compare tests)

- [x] **Phase 2: Navigation Links** — Compare actions on person/photo pages
  - Photo page: "Compare faces" link + "Compare Faces" button
  - Person page: "Compare with a photo" button (passes person_id param)
  - Evidence: `test_photo_page_has_compare_link`, `test_person_page_has_compare_link` PASS

- [x] **Phase 3: PRD-025 Gap Closure** — Reference context + merge/reject on shareable result page
  - Reference context section showing closest existing archive matches
  - Merge/Not Same admin action buttons on each match card
  - Evidence: 3 new tests PASS, browser verified in production

- [x] **Phase 4: Isaac Cohen E2E** — Full browser verification + shareable link
  - Compare URL: `/compare?photo_id=f86fdef4cd4051da&person_id=7a7effee-4372-4da4-af08-1feaa1a3beca`
  - Shareable link: `https://rhodesli.nolanandrewfox.com/compare/result/edc67864978f`
  - 9/9 browser verification checks PASS
  - Evidence: Screenshots in docs/screenshots/session-85b/

- [x] **Phase 5: Session Docs** — CHANGELOG, ROADMAP, assessment updated

## Production Bugs Fixed
1. **photo_registry=None** — `find_nearest_neighbors` crashed because from-photo/vs-person/result endpoints passed None. Fixed in 3 call sites.
2. **registry.identities private attribute** — 4 places used `registry.identities` (private `_identities`). Fixed to public API.
3. **Railway volume disk-full** — `_save_comparison_result` threw OSError. Made graceful with try/except + in-memory cache. Added auto_backup pruning at startup.

## Deferred

- **Railway volume space cleanup** — Root cause of disk-full not addressed. Volume needs manual cleanup or expansion in future ops session.
- **Stale test maintenance** — ~60 pre-existing failures in `test_skipped_focus.py`, 2 in `test_compare_intelligence.py`.

## Red Flags

- **P1: Railway volume disk full** — Comparison results can't persist to disk. In-memory cache works but results lost on redeploy. Needs ops attention.
- **P2: Pre-existing test failures** — Unrelated to this session but should be addressed.

## Key Decisions

- **Archive-to-compare uses HTMX lazy load** — When `/compare?photo_id=X` is visited, results load via `hx-get` on page load. Avoids duplicating logic and keeps compare page handler simple.
- **Separate search-person-photo endpoint** — From-photo flow uses `<a>` links for person selection, making results bookmarkable and shareable.
- **Graceful disk-full handling** — Comparison results saved to in-memory cache even when disk write fails, so the feature works without persistent storage.

## Next Session Should Verify

1. Railway volume space — check if startup cleanup freed enough space
2. Shareable link persistence across deploys (results stored in-memory may be lost)
3. Pre-existing test failures need cleanup session
