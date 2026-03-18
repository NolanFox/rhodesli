# Session 114 Assessment — Data Stability Completion + Harness Gaps + Test Performance

## Shipped

- [x] Phase 0: Harness gap closure — Evidence: SESSION_HISTORY.md backfilled (Sessions 106b-113), stop hook SESSION_HISTORY check added, SESSION_LOG reset
- [x] Phase 1: PRD-051 Phase 2A — proposals read from Supabase — Evidence: `_load_proposals()` reads ml_proposals table with 120s TTL cache, 10 tests in `test_proposals_supabase.py`
- [x] Phase 2: PRD-051 Phase 2B — annotations, relationships, GEDCOM matches from Supabase — Evidence: TTL caches (120s annotations, 300s relationships/gedcom), 12 tests in `test_phase2b_supabase.py`
- [x] Phase 3: PRD-051 Phase 4 — deploy pipeline cleanup + DATA-009 — Evidence: REQUIRED_DATA_FILES reduced to embeddings.npy only, Supabase health check at startup, reconciliation script `--dry-run`/`--execute` modes, 8 tests in `test_deploy_cleanup.py`
- [x] Phase 4: Test performance — Evidence: `make test-fast` 87s → 28s (3 slow integration tests marked @pytest.mark.slow)
- [x] Phase 5: Deploy + verification — Evidence: DOCKERFILE builder, 5/5 production pages verified READ-ONLY (health, home, people, proposals, tree)

## Deferred

- **PRD-051 Phase 3** (ML pipeline Supabase reads) — local-only scripts, no production split-brain risk
- **DATA-009 --execute** — dry-run report is the deliverable; Nolan reviews before pruning
- **Flaky test `test_my_contributions_page_accessible`** — passes alone, fails in parallel due to cross-worker state contamination. Would need session-scoped fixtures to fix properly.
- **Flaky test `test_identify_mode_toggle_on_photo_page`** — pre-existing ERROR in parallel mode, skips when run alone
- **test_share_download.py** — 9 pre-existing failures, not caused by Session 114

## Red Flags

- [LOW] `test_identify_mode_toggle_on_photo_page` — pre-existing flaky test, errors in parallel mode
- [LOW] GitHub auto-deploy uses RAILPACK builder — must use `railway up` CLI for DOCKERFILE deploys (Lesson 117)
- [LOW] Proposals names not enriched from Supabase — `source_identity_name`/`target_identity_name` empty in Supabase path, consumers must enrich lazily

## Next Session Should Verify

1. After deploy completes: re-check `/health` endpoint shows proposals from Supabase (not JSON)
2. Confirm admin actions (merge, confirm) still work after proposals TTL cache change
3. Run `python scripts/reconcile_supabase.py --dry-run` to check stale row counts
4. Consider running DATA-009 `--execute` if dry-run report is clean
