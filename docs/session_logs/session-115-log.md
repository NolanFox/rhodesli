# Session 115 Log — Community Routing Safety + ML Service Extraction Phase 1

**Started:** 2026-03-18
**Predecessor:** Session 114 (Data Stability Completion)
**Prompt:** docs/prompts/session-115-prompt.md
**Context:** docs/session_context/session-115-context.md

## Baseline Metrics
- App tests: 3167 passed, 7 skipped, 35s
- ML tests: TBD (not changed this session)
- ML service tests: 9 passed (new)
- ML run logger tests: 18 passed (new)

## Phase Checklist
- [x] Phase 0: Orient + Baseline — session files set, baseline recorded
- [x] Phase 1: Community Routing Audit + Hardening — 120+ routes audited, 27 safety tests
- [x] Phase 2: ML Service Skeleton — FastAPI app + detect endpoint + Dockerfile + 9 tests
- [x] Phase 3: ML Run Provenance Schema + Migration — 4 new columns, run logger, 18 tests
- [x] Phase 4: AD + Documentation Updates — AD-228, CHANGELOG, ROADMAP
- [ ] Phase 5: Deploy + Production Verification
- [ ] Phase 6: Harness Outputs

## Phase 1 Audit Results

### Route Classification Summary
| Category | Count | Guard |
|----------|-------|-------|
| Admin-only | ~95 | `_check_admin()` |
| Login-only | 5 | `_check_login()` |
| Token-only (sync) | 5 | `_check_sync_token()` |
| Intentionally public | 5 | None (by design) |
| Not implemented | 2 | Returns 501 |

### Top 5 Findings
1. `/api/compare/upload` — No auth, admin auto-ingest path. Mitigated: admin session check.
2. `/api/annotations/guest-submit` — No rate limiting. Low risk: writes pending_unverified.
3. `/api/compare/result/{id}/respond` — No auth. Writes comparison response data.
4. `/api/upload/stream` — No auth SSE endpoint. Writes temp files only.
5. `/api/estimate/upload` — No auth. Triggers Gemini API (cost). Rate limiting recommended.

### Upload Path Community Assignment (VERIFIED SAFE)
- Form carries hidden `upload_community` field from page render
- POST handler checks: (1) form field override, (2) `is_community_explicit()`, (3) middleware default
- Non-admin uploads go to moderation queue
- Admin uploads use correct community from form field

## Phase 3 Migration Status
- SQL file: `scripts/migrations/alter_ml_runs_add_provenance.sql`
- **NOT YET APPLIED** — Supabase direct DB connection failed (pooler hostname issue)
- Must run in Supabase SQL Editor
- Logger handles missing columns gracefully (returns None)

## Test Counts
- Phase 0 baseline: 3167 passed
- After Phase 1: 3192 passed (+25 community safety)
- After Phase 2: 3196 passed (+4 app tests from ML client)
- After Phase 3: 3214 passed (+18 ML run logger)
- ML service: 9 passed (separate suite)

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
- [ ] git log origin/main..HEAD is empty
