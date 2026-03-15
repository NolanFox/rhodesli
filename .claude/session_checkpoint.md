# Session 103 Checkpoint — Phase 3 Complete

## What was done
- Trained longitudinal shadow reranker via `scripts/evaluate_longitudinal_shadow.py --force-save`
  - Best variant: `distance_only` — temporal/kinship features added noise
  - Phase 2 gate FAILED: baseline already at 99.17% top-1, no age-gap improvement
  - Artifact saved to `rhodesli_ml/artifacts/longitudinal_shadow/` (model.joblib + manifest.json)
- Ran clustering with `--scorer longitudinal-shadow --dry-run`: 470 proposals, identical to baseline
- Created `scripts/compare_ml_runs.py`:
  - Compares two proposals files or two Supabase run_ids
  - Outputs: target changes, added/removed proposals, tier changes, score deltas
  - Markdown formatted output with assessment
- Comparison result: **Neutral** — 0 changes across all 470 proposals
- FB-147 analysis: 1 Big Leon proposal at distance 0.9455, not affected by reranker
  - Cross-community false positives need community-aware filtering, not reranking
- 8 new tests in `tests/test_compare_ml_runs.py` — all pass
- Report: `docs/ml/run_results/reranker_comparison_103.md`

## Key files changed
- `scripts/compare_ml_runs.py` — new comparison script
- `tests/test_compare_ml_runs.py` — 8 tests
- `docs/ml/run_results/reranker_comparison_103.md` — comparison report
- `rhodesli_ml/artifacts/longitudinal_shadow/` — trained model artifact
- `evaluation/baselines/longitudinal_shadow_report.json` — training metrics
- `docs/session_logs/session-103-log.md` — phase 3 marked done

## Key findings
- Reranker gate does NOT pass — baseline is too strong for improvement
- `distance_only` variant won (temporal features don't help at 99 confirmed identities)
- FB-147 requires community-scoped filtering in Phase 4, not reranking
- All reranker scores >0.91 (high confidence agreeing with baseline)

## Pre-existing test failures (not introduced by this phase)
- `test_browse_cards_use_unified_card` — noted in Phase 1
- `test_browse_cards_have_profile_link` — same class
- `test_identified_badge_has_title_attribute` — unrelated UX test

## Next phase
- Phase 4: Community-scoped suggestions
