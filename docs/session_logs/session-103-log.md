# Session 103 Log
Started: 2026-03-15

## Phase Checklist
- [x] Phase 0: Orient
- [x] Phase 1: Create ML Supabase tables
- [x] Phase 2: Run baseline clustering with tracking
- [x] Phase 3: Run reranker comparison
- [x] Phase 4: Community-scoped suggestions
- [x] Phase 5: Test gaps (TEST-003, TEST-004, OBS-003)
- [ ] Phase 6: P0 triage fixes (FB-168, FB-150)
- [ ] Phase 7: P1 triage fixes
- [ ] Phase 8: Deploy + browser verify
- [ ] Phase 9: Session closeout

## Health Check
- Production: OK (1902 identities, 941 photos, v0.99.5)
- ML pipeline: ready
- Supabase: ok

## Phase 1: Create ML Supabase Tables
- Created migration: `scripts/migrations/create_ml_run_tables.sql`
- Ran migration via psycopg2 — both tables created in Supabase
- Verified: schema matches spec (9 columns ml_runs, 10 columns ml_proposals)
- Test insert + delete confirmed working
- 9 new tests in `tests/test_ml_run_tables.py` — all pass
- Pre-existing failure: `test_browse_cards_use_unified_card` (unrelated)

## Phase 2: Run Baseline Clustering with Run Tracking
- Modified `scripts/cluster_new_faces.py`: added `create_ml_run()`, `write_proposals_to_supabase()`, `complete_ml_run()`
- Run creates ml_runs record at start, writes proposals to ml_proposals, completes run with summary
- Fire-and-forget pattern: tracking silently skips when Supabase not configured
- Dry-run results: 470 proposals (86 VERY HIGH, 384 HIGH), 42 zero-distance pre-grouped
- Fox family dominates: Charles Fox 165, Esther Burd Fox 101, Albert Fox 95, Roland Fox 66
- 11 new tests in `tests/test_cluster_ml_run_tracking.py` — all pass
- Results saved to `docs/ml/run_results/baseline_run_103.md`

## Phase 3: Reranker Shadow Comparison
- Trained longitudinal shadow reranker: best variant = `distance_only`
- Phase 2 gate FAILED: baseline top-1 recall already 99.17%, no room for improvement
- Ran clustering with `--scorer longitudinal-shadow`: 470 proposals (identical to baseline)
- Created `scripts/compare_ml_runs.py`: diff tool for proposals files or Supabase run_ids
- Comparison result: **Neutral** — reranker agrees with baseline on all 470 proposals
- 0 target changes, 0 tier changes, 0 score changes
- FB-147 (Big Leon false positives): 1 Leon proposal exists at distance 0.9455, not suppressed by reranker — needs community-scoped filtering instead
- Recommendation: Do NOT activate reranker until more age-gap labels exist
- 8 new tests in `tests/test_compare_ml_runs.py`
- Results: `docs/ml/run_results/reranker_comparison_103.md`

## Phase 4: Community-Scoped Suggestions
- Find-similar panel (`browse_routes.py`): fetches 20 neighbors, filters to same-community first (cross-community fills if < 5)
- Speed-run suggestions (`cluster_review_routes.py`): `_get_confirmed_identity_suggestions()` now accepts `community_slug`, ranks same-community confirmed identities first
- Cross-community badge (`main.py`): removed "From " prefix — shows "Fox Family Archive" not "From Fox Family Archive"
- 7 new tests in `tests/test_community_scoped_suggestions.py` — all pass
- 4331 app tests pass (3 pre-existing failures unchanged)
- Commit: 047558c

## Phase 5: Session 102 Test Gaps
- TEST-003: `test_rhodes_photo_excluded_from_fox_identity_set` + `test_cross_community_identity_included_when_faces_in_both` — verify community photo-derived identity sets prevent cross-community leakage
- TEST-004: 3 tests for `shadow_write_identities_batch` DATA-020 name protection guard — verifies Postgres real names never overwritten by "Unidentified Person NNN"
- OBS-003: Added `input_method` parameter to 6 speed-run routes (confirm-all, reject-all, skip, dismiss, save-name, merge) — conditionally passed through to `log_user_action()`
- 4 tests for input_method logging: records keyboard/button, omits when empty, source code verification
- 9 new tests total in `tests/test_session102_gaps.py`
- 4340 app tests pass (3 pre-existing failures unchanged)

## Phase 0: Orient
- Set current_session.txt to 103
- Read session context: ML pipeline execution + 18 triage items
- Deploy verified: healthy
- Session log created
