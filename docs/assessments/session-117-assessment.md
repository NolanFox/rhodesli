# Session 117 Assessment — Wire Upload Pipeline to ML Service (TOOLS-002 Phase 3)

## Shipped

- [x] **Phase 1: ML Service Detection Wrapper** — `detect_faces()` in `core/ingest_inbox.py` tries ML service first, falls back to local. Transforms response to PFE format via `create_pfe()`. One-line call site change in `process_single_image()`. 10 tests.
  Evidence: `pytest tests/test_ml_service_detection.py -v` → 10 passed. `make test-fast` → 3231 passed.

## Deferred

- **Phase 2: ML Run Logging in Detection** — The detection wrapper logs to Python logging but doesn't write to `ml_runs` table yet. Needs Supabase client in background thread context. Low priority — the wrapper works, logging is a monitoring enhancement.

## Red Flags

- **LOW**: Pre-existing flaky test `test_front_label_on_photo_with_back` fails intermittently in parallel mode. Not caused by this session.

- **LOW**: The async-to-sync bridge in `detect_faces()` handles both running loop and no-loop cases, but hasn't been tested in Railway's actual runtime environment. First upload on production will be the real test.

## Next Session Should Verify

1. **Upload a test photo** on production and check Railway logs for `[ml-service]` log messages
2. **Compare detection results** between ML service and local to confirm identical embeddings
3. **Monitor Railway costs** — two services running 24/7 on hobby plan

## Metrics

| Metric | Before | After |
|--------|--------|-------|
| App tests | 3211 | 3231 (+20 this session: 10 detection + 10 client) |
| Detection paths | 1 (local only) | 2 (ML service + local fallback) |
| Code change in ingest_inbox.py | 0 lines modified | 1 line changed (call site), 75 lines added (wrapper) |
