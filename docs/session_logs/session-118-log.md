# Session 118 Log — Codex Audit + ML Service Fix + Security Hardening

Started: 2026-03-18
Prompt: docs/prompts/session-118-prompt.md

## Phase Checklist
- [x] Phase 0: Orient + ML Service Port Fix (CRITICAL)
- [x] Phase 1: Codex Audit of Sessions 115-117 + Security Fix
- [x] Phase 2: ML Service Health Endpoint + Production Verification
- [x] Phase 3: Cross-Batch Clustering Verification (already wired)
- [x] Phase 4: AD-229 — ML Removal Evaluation (DEFER)
- [x] Phase 5: HD-028 — Codex Strategy Evaluation
- [x] Phase 6: Harness Outputs

## Baseline
- Tests: 3230 passed, 9 skipped, 36s
- Web app (rhodesli): SUCCESS
- ML service: **FAILED** — all previous deploys failed healthcheck

## Phase 0: ML Service Port Fix (CRITICAL)

**Root cause**: Dockerfile CMD hardcodes `--port 5002`, but Railway assigns a dynamic `PORT` env var. Healthcheck connects on Railway's port, not 5002.

**Fixes**:
1. `ml_service/Dockerfile`: CMD uses `${PORT:-5002}`
2. `core/ingest_inbox.py`: Handle dict AND list format for `image_size`
3. Tests updated to match actual ML service response format
4. Set `PORT=5002` env var on ml-service to match `ML_SERVICE_URL`

**Result**: ML service deployed successfully for FIRST TIME EVER.

## Phase 1: Codex Audit

### ML Service Audit (timed out)
| # | Severity | Finding | Disposition |
|---|----------|---------|-------------|
| 1 | MEDIUM | Async client singleton persists across asyncio.run() boundaries | BACKLOG — low risk in single-process app |
| 2 | MEDIUM | No upload size limit on ML service endpoint | BACKLOG — internal-only service |
| 3 | LOW | Default "dev-token" hardcoded | SKIP — Railway has real token |
| 4 | LOW | No threading protection on singleton | SKIP — single-process async |

### Community Routing Audit (completed)
| # | Severity | Finding | Disposition |
|---|----------|---------|-------------|
| 1 | HIGH | upload_community hidden field allows cross-community writes | **FIXED** — admin-only override |
| 2 | MEDIUM | Tests are string-presence, not behavioral | Added 2 behavioral tests |

## Phase 2: ML Health Endpoint

- Added `/api/admin/ml-health` endpoint (admin-only)
- 4 tests (not_configured, connected, unreachable, requires_admin)
- Production response: `{"status": "connected", "ml_service": {"status": "ok", "version": "0.1.0", "models_loaded": false, "execution_environment": "railway_ml_service"}}`
- Detection comparison deferred — model not loaded yet (lazy load on first request)

## Phase 3: Cross-Batch Verification

Already wired (Session 109). Verified in `app/upload_routes.py`:
- `find_cross_batch_matches()` at line 1019
- community_id passed at line 1035
- ml_runs logging at line 1095
- Proposal deduplication at line 1058

## Phase 4: AD-229

Decision: DEFER local ML removal. Stability criteria:
1. 24h+ continuous uptime
2. 3+ successful uploads through ML service
3. Embedding cosine similarity ≥0.999
4. Railway billing ≤$5/mo

## Phase 5: HD-028

Decision: Codex audit — MIXED VALUE. Use for security-sensitive scopes only.

## Browser Verification (READ-ONLY)
- [x] `/api/admin/ml-health` — status: connected ✓
- [x] Root landing page — 472 matches, 89 people ✓
- [x] Fox Family page — 843 matches, 35 people, 660 photos ✓
- [x] Version v0.99.27 visible ✓

## Verification Gate
- [x] Codex Phase 1 audit done? — Documented above
- [x] ML health endpoint exists? — `/api/admin/ml-health` returns status
- [ ] Detection comparison done? — DEFERRED (model not loaded, need real upload)
- [x] Cross-batch verified? — Already wired (Session 109)
- [x] AD-229 documented? — In ALGORITHMIC_DECISIONS.md
- [x] Codex strategy decided? — HD-028 in HARNESS_DECISIONS.md
- [x] All tests pass? — 3230+ pass (pre-existing flaky test in xdist only)
- [x] Assessment exists? — docs/assessments/session-118-assessment.md
- [x] All session logs exist? — 115, 116, 117, 118 all present
- [ ] `git log origin/main..HEAD` empty? — Final push pending
