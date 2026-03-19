# Session 119 Assessment — ML Service End-to-End Verification

## Shipped
- [x] Phase 0: Orient — ML service connected, baseline tests pass — Evidence: browser screenshot, 2880 tests pass
- [x] Phase 1: Pre-warm — `/api/v1/warm` endpoint, `/api/admin/ml-warm` admin route, 180s timeout, event loop fix — Evidence: 4 commits, warm response `{"status":"warm","load_time_seconds":17.33}`
- [x] Phase 2: Upload — **FIRST real production upload through ML service** — Evidence: Railway logs `POST /api/v1/detect-and-embed → 200`, UI shows "14 faces extracted, 14 added to Inbox", 118 cross-batch matches
- [x] Phase 3: Embedding quality (adapted) — 3/3 real-world matches correct — Evidence: Fanny Burd #1 at 1.08, Irving Yanishefsky #1 at 1.13, Sarah→Edith sisters at 1.21
- [x] Phase 4: Performance — model load 17.33s, detection successful, known issues documented
- [x] Feedback logging — 10 items (FB-001 through FB-010), all with severity, root cause, BACKLOG IDs

## Deferred
- Phase 3 (cosine comparison): Couldn't do local-vs-cloud comparison because test photo was new, not previously processed locally. Adapted to real-world validation instead. BACKLOG: do formal cosine comparison in next upload session.
- AD-229 criteria: 1 of 4 criteria met. Need 2 more successful uploads + 24h uptime check + billing check. Next session.
- Phase 5 (harness outputs): Completing now.

## Red Flags
- **P0** FB-009: Confirm button silently fails for unidentified persons — blocks tagging workflow. Fix: 30 min, disable button when name is unidentified.
- **P1** Audit log schema mismatch: `'actor' column` not found in `audit_log` table — ~15 warnings per upload. Supabase schema cache stale or column missing.
- **P1** GEDCOM tree query timeout: Supabase statement timeout causing >1 min page loads. Needs index or query optimization.
- **P1** Upload page slowness: cascading from GEDCOM timeout.
- **P2** PostHog capture error: wrong argument count. Analytics not recording.
- **P2** Source URL not persisted from upload form (FB-007).
- **INFO** ML service restarts on every git push (both services redeploy). AD-229 24h uptime criterion needs deploy isolation (only redeploy ML service when ml_service/ files change).

## What Worked Well
- ML service detected 14 faces correctly on first real production request
- Cross-batch matching produced correct results immediately
- Family resemblance detection working (sisters, cousins)
- Warm endpoint eliminated first-request timeout risk
- Event loop fix ensures admin endpoints work reliably

## Next Session Should Verify
1. FB-009 fix (confirm button for unidentified persons)
2. Upload 2 more photos through ML service (AD-229 criterion: 3 successful uploads)
3. Check ML service uptime after 24h without deploys
4. Formal cosine similarity comparison (upload a photo that exists locally)
5. Source URL persistence fix (FB-007)
6. Audit log 'actor' column fix
