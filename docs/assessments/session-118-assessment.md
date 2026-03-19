# Session 118 Assessment — Codex Audit + ML Service Fix + Security Hardening

## Shipped

- [x] **Phase 0: ML Service Port Fix (CRITICAL)** — ML service had NEVER passed healthcheck in production due to hardcoded port 5002 vs Railway's dynamic PORT. Fixed Dockerfile CMD to use `${PORT:-5002}`. Also fixed image_size format mismatch (dict vs list). ML service now healthy for first time ever.
  Evidence: Railway deploy `835962f7` → SUCCESS. `/api/admin/ml-health` returns `{"status": "connected"}`. Screenshot verified.

- [x] **Phase 1: Codex Audit of Sessions 115-117** — Two Codex CLI audits completed:
  - ML service audit (partial — timed out): 4 findings (MEDIUM/LOW)
  - Community routing audit (complete): 1 HIGH finding (upload community override)
  - HIGH fix: Non-admin users can no longer override upload_community hidden field
  - 6 new tests (4 ML health endpoint, 2 upload safety)
  Evidence: `pytest tests/test_ml_service_detection.py tests/test_community_routing_safety.py` → 43 passed

- [x] **Phase 2: ML Health Endpoint** — `/api/admin/ml-health` admin-only endpoint returns ML service connection status, version, model state, uptime. Browser verified on production.
  Evidence: Screenshot shows `{"status": "connected", "ml_service": {"status": "ok", "version": "0.1.0"}}`

- [x] **Phase 3: Cross-Batch Verification** — Already wired in Session 109. Verified: `find_cross_batch_matches()` called in `_background_ingest()` with community_id, deduplication, and ml_runs/ml_proposals Supabase logging.
  Evidence: `grep "cross_batch" app/upload_routes.py` → 3 references at lines 1008, 1019, 1087

- [x] **Phase 4: AD-229 — ML Service Stability Evaluation** — Decision: DEFER removing local InsightFace. Stability criteria documented (24h uptime, 3 successful uploads, embedding similarity ≥0.999, billing ≤$5/mo).
  Evidence: `grep "AD-229" docs/ml/ALGORITHMIC_DECISIONS.md` → present

- [x] **Phase 5: HD-028 — Codex Strategy Evaluation** — Decision: MIXED VALUE. Adopt for security-sensitive scopes only (auth, data writes, cross-community). Not for routine use.
  Evidence: `grep "HD-028" docs/HARNESS_DECISIONS.md` → present

## Deferred

- **Phase 5 (post-work Codex audit of Session 118 changes)** — Skipped because findings from Phase 1 Codex audit were sufficient to evaluate the strategy. Running Codex again on the same session's code would add cost without new signal.
- **Local vs Cloud Detection Comparison** — Cannot run comparison because ML service `models_loaded: false` (lazy-loads on first real request). Need to upload a test photo to trigger first detection. Deferred to next upload batch.
- **TOOLS-002 Phase 5 implementation** — Correctly deferred per AD-229. Need 24h+ stability first.

## Red Flags

- **LOW**: Pre-existing flaky tests (test_confirmed_anchors_in_face_to_photo, test_photo_og_image_is_absolute_url, test_not_available_when_not_configured) — all pass in isolation, fail in parallel xdist. Ordering issue, tracked as BACKLOG-FLAKY-001.
- **LOW**: ML service `models_loaded: false` means the first upload will take 30-60s for model load. Timeout is 60s, which might be tight.
- **INFO**: Railway PORT=5002 set explicitly on ml-service to match ML_SERVICE_URL. If Railway removes env vars or resets config, this will break.

## Codex Strategy Evaluation Summary

| Metric | ML Audit | Community Audit |
|--------|----------|-----------------|
| Completed? | No (timed out) | Yes |
| Findings | 4 partial | 1 HIGH + 1 MEDIUM |
| False positives | 0 | 0 |
| Time | ~5 min | ~5 min |
| Real bugs caught | 0 new | 1 new (upload override) |
| Verdict | Low value | High value |

**Overall**: Use Codex for security-sensitive audits only. HD-028 documents the full decision.

## Next Session Should Verify

1. Upload a test photo to trigger first ML service detection — check Railway logs for `[ml-service]` prefix
2. ML service uptime >24h continuous
3. Embedding comparison: local vs cloud detection on same image
4. If stable: plan TOOLS-002 Phase 5 (remove local ML from Dockerfile)
