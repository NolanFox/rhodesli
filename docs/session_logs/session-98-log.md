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
- `docs/assessments/session-98-supabase-postimport-state.json`
- `docs/analysis/session-98-gedcom-research.md`
- `docs/analysis/session-98-gedcom-schema-qa.md`
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
- Final integrated verification on `/private/tmp/rhodesli-main-integration`:
  - `pytest tests/test_gedcom_versioning.py -q` → `34 passed`
  - `pytest tests/test_gedcom_routes.py -q` → `44 passed`
  - `make test-fast` → `2680 passed, 7 skipped`
  - `pytest tests/ -x -q` → `4130 passed, 21 skipped`
  - `pytest rhodesli_ml/tests/ -x -q` → `588 passed, 2 skipped`

## Audit Outcome

- Normalized diff still shows broad record churn, but the high-signal breakdown
  is now understandable:
  - `311` individuals with direct person-fact edits
  - `473` individuals with citation/media-reference edits
  - `718` modified events after normalization
  - `6` high-confidence removed-to-current redirect candidates
- Full narrative recorded in `docs/assessments/session-98-gedcom-audit.md`.

## Live Outcome

- Applied additive Supabase migration and completed a successful live import as
  GEDCOM version `7` (`05ffeee9-4ae2-4d97-aaaa-fa8a45fb1ca7`).
- Live current-state counts now match the March 11 export mirror:
  - `21,944` individuals
  - `41,526` events
  - `146,592` relationships
  - `6,722` families
  - `803` sources
  - `668` media objects
  - `30,154` raw records
- Existing `gedcom_face_links` were verified after the live import:
  - `67` rows with a GEDCOM id
  - `0` unresolved against current GEDCOM individuals
- `gedcom_entity_redirects` remains empty in production because no live linked
  GEDCOM id required redirect repair after the bootstrap import.

## Hardening After Apply

- Identified and fixed a bootstrap edge case:
  - first-time versioned imports previously skipped redirect detection
  - importer now runs conservative redirect detection during bootstrap too
  - regression coverage added in `tests/test_gedcom_versioning.py`
- Identified and fixed a memory footgun:
  - change-log rows were accumulated in memory before insertion
  - importer now streams change-log writes in bounded batches

## Deploy Closeout

- Initial `main` deploy for commit `7a65091` failed on Railway at startup because
  the image copied a curated subset of `rhodesli_ml/`, while the app now imports
  additional runtime modules such as `rhodesli_ml.active_learning`.
- Fixed with commit `7e4046e` (`[codex] fix(deploy): package full ml runtime`)
  by copying `rhodesli_ml/` wholesale and relying on `.dockerignore` to exclude
  tests, notebooks, checkpoints, and local virtualenv state.
- Railway production deployment `2dbb0a2f-3373-4929-b3df-552134710c9d` reached
  `SUCCESS` after the packaging fix.
- Production verification after deploy:
  - `GET /health` returned `200` on `2026-03-12`
  - homepage HTML returned successfully
  - GitHub Actions run `22981172101` completed `success`
- Startup logs also exposed a legacy-schema warning for
  `audit_log.target_type`. Session 98 closed that compatibility gap with a
  fallback in `app/supabase_data.py` plus regression coverage in
  `tests/test_supabase_migration.py`.
- Startup logs also exposed a non-fatal backup warning because
  `scripts/init_railway_volume.py` was executed from `/app/scripts` without
  first bootstrapping the project root for `core/` imports. Session 98 fixed
  that bootstrap path and added regression coverage in
  `tests/test_deploy_safety_gate.py`.
- The final closeout pass also fixed an unrelated fast-suite flake in
  `tests/test_session_82e_features.py`: the test now selects a routeable photo
  page instead of assuming the first cache id is renderable under xdist.

## User Q&A Captured

- Session 98 design questions and answers are recorded in:
  - `docs/analysis/session-98-gedcom-schema-qa.md`
- That artifact captures:
  - brittleness/runtime concerns
  - small-file versus large-memory explanation
  - update-versus-new-tree distinction
  - stable-ID versus rekey/merge lineage handling
  - multi-community / multi-tree future direction
  - Melanie Strauss / Roland Fox style cross-community cases
