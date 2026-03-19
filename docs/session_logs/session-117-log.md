# Session 117 Log — Wire Upload Pipeline to ML Service (TOOLS-002 Phase 3)

**Started:** 2026-03-18
**Predecessor:** Session 116 (ML Service Deployment)
**Prompt:** docs/prompts/session-117-prompt.md
**Context:** docs/session_context/session-117-context.md

## Baseline Metrics
- App tests: 3211 passed, 29s
- ML service tests: 9 passed

## Phase Checklist
- [x] Phase 1: ML Service Detection Wrapper — detect_faces() with fallback, 10 tests
- [ ] Phase 2: ML Run Logging — deferred (Supabase client in background thread)
- [x] Phase 3: Deploy — pushed, auto-deploy triggered
- [x] Phase 4: Harness Outputs — assessment, changelog, roadmap

## What Was Built

### detect_faces() Wrapper (core/ingest_inbox.py:386-465)
- Checks `MLServiceClient.is_configured` (feature flag via ML_SERVICE_URL)
- If configured: calls ML service, transforms response to PFE format via create_pfe()
- On any error: falls back to local extract_faces()
- Handles async/sync boundary (background thread context)
- Logs "[ml-service]" for service calls, WARNING for fallbacks

### Call Site Change (core/ingest_inbox.py:780)
- `process_single_image()` now calls `detect_faces()` instead of `extract_faces()`
- One-line change, everything downstream unchanged

## Test Counts
- Before: 3211 app tests
- After: 3231 app tests (+20: 10 ML service detection + 10 ML client)

## Known Gaps (for Session 118)
- ML run logging not integrated into detect_faces() (needs Supabase client in thread)
- No end-to-end production verification (ML service never tested with real upload)
- No health monitoring endpoint on web app for ML service
- Async/sync boundary untested in Railway runtime

## Verification Gate
- [x] detect_faces() exists
- [x] process_single_image uses detect_faces
- [x] Fallback works (tested)
- [x] Transform produces PFE format (tested)
- [x] All tests pass (3231)
- [x] Assessment exists
- [x] CHANGELOG v0.99.27
- [x] ROADMAP updated
- [x] git log origin/main..HEAD empty
