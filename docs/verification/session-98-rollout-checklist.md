# Session 98 Rollout Checklist

## Goal

Apply the Session 98 GEDCOM rich-mirror schema and import the March 11 GEDCOM
without destructive edits.

## Execution Result

Executed successfully on 2026-03-11.

- additive migration applied
- live import applied as GEDCOM version `7`
- current mirror counts match the March 11 GEDCOM export
- existing `gedcom_face_links` verified: `0` unresolved against current GEDCOM individuals
- final live state recorded in `docs/assessments/session-98-supabase-postimport-state.json`

## Preconditions

1. Session 96 changes are already on `main`.
2. Session 97 prompt-lineage changes are already merged or rebased in.
3. Supabase SQL execution is available from the operator environment.
4. `.env` contains:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_DB_PASSWORD` or equivalent direct SQL access

## Artifacts To Review First

1. `docs/assessments/session-98-gedcom-audit.md`
2. `docs/assessments/session-98-gedcom-diff-report.json`
3. `docs/assessments/session-98-supabase-preimport-state.json`
4. `docs/analysis/session-98-gedcom-research.md`

## Apply Steps

1. Execute the additive migration:

```sql
scripts/supabase_migration_003_gedcom_rich_mirror.sql
```

2. Run a dry-run import:

```bash
source /Users/nolanfox/rhodesli/venv/bin/activate
python scripts/import_gedcom_version.py \
  --file "$HOME/Downloads/gedcom_20260311/Fox_Capeluto_Fogel_Waldorf Family Tree.ged"
```

3. Verify:
- `schema_ready` is `true`
- `missing_tables` is empty
- entity summaries and redirect summary look plausible

4. Execute the versioned import:

```bash
source /Users/nolanfox/rhodesli/venv/bin/activate
python scripts/import_gedcom_version.py \
  --file "$HOME/Downloads/gedcom_20260311/Fox_Capeluto_Fogel_Waldorf Family Tree.ged" \
  --execute \
  --notes "Session 98 rich GEDCOM mirror bootstrap"
```

5. Verify post-import state:
- `gedcom_versions` now has an applied rich-mirror version
- `current_gedcom_individuals`, `current_gedcom_events`,
  `current_gedcom_relationships`, `current_gedcom_families`,
  `current_gedcom_sources`, `current_gedcom_media_objects`,
  `current_gedcom_records` all return expected counts
- `/admin/gedcom` preview no longer reports missing schema tables
- linked people pages still show GEDCOM context
- tree pages reflect current Supabase GEDCOM edges

## Rollback Posture

- The schema migration is additive.
- The import path is append-only with `is_current` flags.
- Pre-import live state is recorded in
  `docs/assessments/session-98-supabase-preimport-state.json`.

If a rollback is needed after the first live import, do not delete rows.
Restore the pre-import current state with an explicit SQL/admin rollback step,
then record that rollback as a new audited operation.

For Session 98 specifically:
- pre-import state is in `docs/assessments/session-98-supabase-preimport-state.json`
- post-import state is in `docs/assessments/session-98-supabase-postimport-state.json`
