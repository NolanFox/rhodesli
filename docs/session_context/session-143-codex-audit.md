# Session 143 Codex Audit

**Auditor**: Codex CLI v0.117.0 (o4-mini)
**Agent type**: Independent (fresh context)
**Scope**: All Session 143 code changes (6 app files, 3 test files, 1 script)
**Date**: 2026-03-28

## Findings

### P1: Transient Supabase failures become sticky empty caches
- **Files**: app/main.py (_load_date_labels, _load_birth_year_estimates), app/page_routes.py (_load_photo_locations)
- **Issue**: Non-TTL loaders cache `{}` on Supabase failure. Subsequent requests return cached empty forever — UI stays blank until restart.
- **Action**: FIXED. Return `{}` without caching on failure. Next request retries Supabase.
- **Verification**: Codex reproduced in venv with fail-then-success sequence. Fix confirmed.

### P2: Batch location_evidence not rendered
- **Files**: scripts/batch_gemini_for_person.py, app/main.py
- **Issue**: Batch stores rich location in `location_evidence` dict, plain string in `location_estimate`. Template only reads `location_estimate`, losing visual_evidence and biographical_evidence.
- **Action**: FIXED. Template now reads `location_evidence` dict as fallback for evidence text.

### P2: Test fixtures don't match real batch output format
- **Files**: tests/test_ai_analysis_rendering.py, tests/test_no_json_fallback.py
- **Issue**: Test BATCH_LABEL fixture uses dict `location_estimate` (old format) but batch script now writes string. Also no_json_fallback behavioral tests cover only 3 of 7 loaders.
- **Action**: DEFERRED — existing tests still catch regressions. Test fixture update and expanded coverage for 143b.

## Assessment
- **Value**: STRONG — P1 cache poisoning would have caused production outages on transient Supabase blips. Would not have caught this through manual testing.
- **Would we have found this ourselves?** The cache poisoning: unlikely without explicit failure-mode testing. The location_evidence gap: possibly during browser verification.
