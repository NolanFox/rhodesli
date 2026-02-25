# Session 66 Worktree Results (Combined)

## Subagent A: Enrichment Pipeline Validation

### What Was Done

1. **Dry-Run Mode Added** to `scripts/run_combined_pipeline.py` — builds prompts and logs token counts without calling Gemini API
2. **Dry-Run on 10 Photos** (5 GEDCOM-linked, 5 unlinked):
   - Bare prompts: 419-461 tokens | Enriched: 592-4,200 tokens | GEDCOM context alone: 158-3,717 tokens
   - 4 of 5 enriched photos reach 400+ tokens, confirming AD-159
3. **5 Real Gemini API Calls** — total cost $0.06, all logged to gemini_api_calls table
4. **Bug Fix**: `_find_identity_for_face()` returned INBOX identities instead of CONFIRMED — fixed to prefer CONFIRMED state

| File | Change |
|------|--------|
| `scripts/run_combined_pipeline.py` | Added `--dry-run` flag |
| `rhodesli_ml/gedcom_context.py` | Fixed identity priority bug |
| `docs/analysis/enrichment_validation_66.md` | Full validation report |

## Subagent B: Portfolio ML Pipeline Writeup

Created `docs/portfolio/ml_pipeline_writeup.md` (134 lines) — technical writeup of the full ML pipeline for interview portfolio. Covers face detection, similarity calibration (AUC 0.9577), date estimation (CORAL), Gemini alignment with GEDCOM enrichment, and human-in-the-loop architecture.

## Subagent C: GEDCOM Admin UI

Enhanced `/admin/gedcom` with version management UI (AD-164):
- Version info panel, version history, re-enrichment queue display
- Upload/preview/apply/cancel flow for GEDCOM updates
- 25 tests in `tests/test_gedcom_admin.py`

| File | Change |
|------|--------|
| `app/main.py` | +333 lines for GEDCOM admin routes |
| `docs/ml/ALGORITHMIC_DECISIONS.md` | AD-164 entry |
| `tests/test_gedcom_admin.py` | 25 tests (286 lines) |
