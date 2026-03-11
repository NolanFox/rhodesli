# Session 98 Log

**Date:** 2026-03-11  
**Worktree:** `/private/tmp/rhodesli-session-98-gedcom`  
**Branch:** `codex-session-98-gedcom`  
**Context:** `docs/session_context/session-98-context.md`  
**Prompt:** `docs/prompts/session-98-prompt.md`

## Session Setup

- Kept PRD-038 planning as Session 97.
- Opened a separate Session 98 worktree for GEDCOM mirror/import hardening.
- Explicit user guardrails recorded:
  - do not interfere with Session 96 on `main`
  - do not conflict with Session 97 prompt-lineage work
  - keep every data mutation non-destructive and Claude-auditable
  - preserve everything in the GEDCOM, not only thin person rows

## Repo And Data Audit

- Raw GEDCOM audit against:
  - `~/Downloads/gedcom_20260224/Fox_Capeluto_Fogel_Waldorf Family Tree.ged`
  - `~/Downloads/gedcom_20260311/Fox_Capeluto_Fogel_Waldorf Family Tree.ged`
- March 11 export counts confirmed:
  - `21,944` individuals
  - `6,722` families
  - `803` sources
  - `668` media objects
  - `30,154` top-level records
- Verified the export contains repeated names, notes, citations, media refs,
  Ancestry custom tags, and family/event structure that the previous importer
  dropped.

## Implementation Work Completed

### 1. Rich GEDCOM parsing

- Extended `rhodesli_ml/importers/gedcom_parser.py` dataclasses to preserve:
  - names
  - notes
  - citations
  - media refs
  - custom tags
  - raw records
- Added `rhodesli_ml/importers/gedcom_rich.py`:
  - raw line parser
  - top-level record grouper
  - exact raw text preservation
  - structured node-tree preservation
  - tolerant handling of malformed non-structural lines

### 2. Canonical snapshot + diff model

- Added `rhodesli_ml/importers/gedcom_snapshot.py`.
- Snapshot bundle now covers:
  - individuals
  - events
  - families
  - sources
  - media objects
  - relationships
  - raw records
- Fixed diff noise by removing `line_number` fields from serialized raw nodes.

### 3. Rekey / merge safety

- Added `rhodesli_ml/importers/gedcom_matching.py`.
- Detects high-confidence removed-to-current individual redirects.
- Supports:
  - rekey redirects
  - merge redirects
  - redirect-chain resolution for app and ML consumers

### 4. Importer hardening

- Reworked `scripts/import_gedcom_version.py` to use the rich snapshot model.
- Added:
  - per-entity diffing
  - redirect detection summary
  - append-only redirect writes
  - richer change-log coverage
- Fixed two correctness bugs:
  - baseline bootstrap now supersedes all legacy current GEDCOM rows
  - new rows are staged with `is_current = false`, old rows are superseded, and
    only then are replacement rows activated, which keeps the importer
    compatible with unique current-row indexes

### 5. Supabase schema package

- Added `scripts/supabase_migration_003_gedcom_rich_mirror.sql`.
- Migration includes:
  - richer GEDCOM payload columns
  - new `gedcom_families`, `gedcom_sources`, `gedcom_media_objects`,
    `gedcom_records`
  - `gedcom_entity_redirects`
  - refreshed `current_gedcom_*` views

### 6. App and UX updates

- `app/admin_routes.py`
  - rich GEDCOM preview counts
  - per-entity diff summary
  - sample changes
  - redirect summary
  - apply blocked when required schema tables are missing
- `app/page_routes.py`
  - tree now uses current Supabase GEDCOM edges as authoritative GEDCOM graph
  - `data/relationships.json` acts as manual overlay
- `app/relationship_routes.py`
  - loads richer GEDCOM person data
  - resolves linked GEDCOM ids through redirect lineage
  - surfaces alternate names / extra facts / source counts
- `scripts/run_combined_pipeline.py`
  - hydrates richer GEDCOM rows from Supabase
  - resolves redirected GEDCOM ids before building ML context

## Artifacts Added

- `docs/assessments/session-98-gedcom-diff-report.json`
- `docs/assessments/session-98-gedcom-audit.md`
- `docs/assessments/session-98-supabase-preimport-state.json`
- `docs/analysis/session-98-gedcom-research.md`
- `docs/verification/session-98-rollout-checklist.md`
- `rhodesli_ml/importers/gedcom_rich.py`
- `rhodesli_ml/importers/gedcom_snapshot.py`
- `rhodesli_ml/importers/gedcom_matching.py`
- `scripts/audit_gedcom_diff.py`
- `scripts/supabase_migration_003_gedcom_rich_mirror.sql`

## Verification

- Passing targeted suites after the final importer/snapshot fixes:
  - `pytest rhodesli_ml/tests/test_gedcom_parser.py rhodesli_ml/tests/test_gedcom_rich.py rhodesli_ml/tests/test_gedcom_matching.py tests/test_gedcom_versioning.py tests/test_gedcom_admin.py tests/test_combined_pipeline.py tests/test_tree_api.py tests/test_tree_navigation.py -q`
  - result: `185 passed`
- Regenerated the normalized GEDCOM diff report after removing raw-node
  line-number noise.
- After merging the committed Session 97 branch into Session 98, reran the
  combined GEDCOM + lineage + calibration verification slice:
  - `323 passed`

## Audit Outcome

- Normalized diff still shows broad record churn, but the high-signal breakdown
  is now understandable:
  - `311` individuals with direct person-fact edits
  - `473` individuals with citation/media-reference edits
  - `718` modified events after normalization
  - `6` high-confidence removed-to-current redirect candidates
- Full narrative recorded in `docs/assessments/session-98-gedcom-audit.md`.

## Pending Closeout Work

- Live Supabase migration/import was preflighted but not executed from this
  environment because direct Postgres access failed and no `exec_sql` RPC is
  available on the project.
- Session 98 branch was pushed as `origin/codex-session-98-gedcom` after
  merging the committed `codex-session-97-impl` branch state.
- Final main-branch merge and worktree cleanup are blocked until the active
  Session 96 and Session 97 worktrees are no longer dirty.
- Final merge choreography must still respect user order:
  `96 -> 97 -> 98`.
