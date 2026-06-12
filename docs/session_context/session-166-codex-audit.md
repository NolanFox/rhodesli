# Session 166 — Codex Post-Execution Audit

**Auditor**: Codex CLI v0.139.0 (gpt-5.5, xhigh)
**Agent type**: Independent (fresh context)
**Scope**: app/supabase_data.py (log_gemini_call filter), app/estimate_routes.py
(operator/experiment_id), scripts/run_combined_pipeline.py (GEDCOM loader 164 fix),
scripts/multimodel_photo_estimate.py (finalize write path)
**Date**: 2026-06-12

## Findings & disposition

| ID | Sev | Finding | Disposition |
|----|-----|---------|-------------|
| 1 | P1 | `finalize()` never verifies the artifact/candidate belongs to the CLI `photo_id` — a typo could overwrite another photo's rows | **FIXED** — meta.json `photo_id` guard, refuses to write on mismatch |
| 2 | P1 | `finalize()` replaced the entire `date_labels.data`/`photo_locations.data` JSONB, erasing existing enrichment (event_context, visible_text, human corrections) | **FIXED** — read-merge-write (`{**existing, **entry}`), mirrors the production reanalyze route |
| 3 | P1 | `load_gedcom_data()` read canonical GEDCOM rows without `community_id` filter — composite community keys mean cross-community gedcom_id collisions | **FIXED** — `.eq("community_id", "rhodesli")` on the 4 community-scoped GEDCOM tables, matching the main app readers. Verified context unchanged (4876 chars, Meyer+Reva present) |
| 4 | P2 | `_GEMINI_API_CALLS_COLUMNS` global not cleared by `reset_client()`; empty-table case can't discover schema | **FIXED** — `reset_client()` clears it. Empty-table case falls back to full insert (best-effort, original behavior); production table is non-empty |
| 5 | P2 | Unknown locations persisted as `(0.0, 0.0)` "Null Island" | **FIXED** — `finalize()` only writes lat/lng when geocoding resolves; else writes `location_name` only |
| 6 | P3 | Shallow `dict(gemini_config)` could mutate a caller-owned nested `_lineage` | **FIXED** — `copy.deepcopy` |

**Verdict**: 0 P0. All 3 P1 + both P2 + the P3 fixed. Codex confirmed operator/
experiment_id threading correct and ran the focused tests (60 passed).

## Value assessment
STRONG — caught two real data-integrity risks in the new finalize() write path
(full-document overwrite + cross-community GEDCOM leak) that the focused unit
tests did not cover, consistent with the repo's repeat-offender data-integrity
failure mode. Would we have found #2/#3 ourselves? #2 eventually (on a photo
with prior enrichment); #3 unlikely without the community-key context.
