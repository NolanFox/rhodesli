# Session 96e-cont12 Context

## Goal
Take the stabilization work from cont10/cont11 all the way to a trustworthy
closeout: finish the data audit, reconcile production safely, preserve a full
unwind trail, and explain exactly how the archive became fragile.

## User Requirements
- Keep all data handling non-destructive and reversible.
- Record every material data change in a clear, durable trail.
- Keep commits small and push them so progress is visible.
- Confirm whether InsightFace was really run for the `124` missing embeddings.
- Make sure community work did not introduce more hidden regressions.
- Do not call the session done until every known finding is either fixed or
  explicitly accounted for.

## What This Continuation Found
- The code-side findings from cont11 were real and were closed there:
  - merge dedup regression on structured anchors
  - append-only history bypasses
  - photo-face loss when embeddings drifted
  - app-suite failure
- The remaining work in cont12 was data/state reconciliation:
  - local baseline audit still showed structural issues and embedding gaps
  - production volume JSON, production Postgres, and local audited data were not perfectly aligned
  - Supabase still contained stale identity shadow rows after corrective upserts

## Root Cause Model
- The system became fragile because several contracts were only partially
  enforced during the JSON -> Postgres -> community expansion transition.
- Durable records existed in more than one place:
  - local JSON / Railway volume JSON
  - Supabase/Postgres shadow tables
  - derived artifacts such as crops and embeddings
- Not every repair path updated every layer.
- Some consumers then trusted derivative artifacts or stale shadow rows more
  than the audited registry payload.

This produced a pattern of "drift without obvious breakage":
- a page could render
- the primary data file could look reasonable
- yet another layer still carried stale rows or missing artifacts

## Data Work Performed

### Local Structural Reconciliation
- Started from `docs/assessments/session-96e-cont12-local-audit-before.json`
- Closed:
  - `157` orphan faces
  - `1` duplicate face assignment
  - `122` merge chains
  - `2` missing identity face refs
  - `2` placeholder confirmed identities
- Result:
  - `docs/assessments/session-96e-cont12-local-audit-after-structural.json`

### Embedding Repair
- Verified earlier session work had already reduced `124` missing embeddings to `2`.
- Re-ran local repair logic on the remaining gap.
- Repaired `8` embeddings total in cont12:
  - `6` direct repairs from source images
  - `2` archival crop matches:
    - `inbox_a56c556100a9`
    - `inbox_e64c25fc88a7`
- Evidence:
  - `docs/assessments/session-96e-cont12-embedding-repair-report.json`
  - `docs/assessments/session-96e-cont12-local-audit-after-embedding-repair.json`
  - `docs/assessments/session-96e-cont12-local-audit-final.json`

### Production Reconciliation
- Wrote the audited `3412` identities / `938` photos snapshot to Supabase.
- Wrote the same audited snapshot to the live Railway volume via `/api/sync/push`.
- Captured live volume backup filenames:
  - `identities.json.bak.1773237513`
  - `photo_index.json.bak.1773237513`
- Detected that Supabase still held `112` stale identity rows because the
  shadow write process was additive-only.
- Exported those stale rows in full to:
  - `docs/assessments/session-96e-cont12-supabase-prune-backup.json`
- Pruned the stale rows only after the checked-in backup artifact existed.
- Recorded the post-prune state in:
  - `docs/assessments/session-96e-cont12-supabase-prune-result.json`

## Verification
- Local final audit:
  - `3412` identities
  - `938` photos
  - `2640` indexed faces
  - `2852` embeddings
  - `0` missing embeddings
  - `0` structural integrity failures
- Tests:
  - `pytest tests/ -x -q` -> `4098 passed, 7 skipped`
  - `pytest rhodesli_ml/tests/ -x -q` -> `566 passed`
- Live:
  - Railway deployment `99170803-089c-4dc4-8299-b52fba96e5a9` -> `SUCCESS`
  - `/health` -> `200`, `1931` active identities, `938` photos

## Count Clarification
- Postgres load logs and snapshot counts use total stored identity rows:
  - `3412`
- `/health` uses `registry.list_identities()`, which excludes merged-away rows:
  - `1931`
- This difference is expected after the reconciliation and is no longer a sign
  of drift.

## What Prevents Regression Now
- Append-only identity history is back on the important mutation paths.
- Photo UI now preserves registry-backed face records even if artifacts drift.
- Staged uploads publish embeddings instead of leaving production behind.
- Batch data audit is now a required confidence tool, not an optional cleanup.
- The cont12 machine-readable artifacts make this repair reversible and reviewable.

## Remaining Hardening Work
- Automate shadow-table prune/reconcile instead of relying on manual session work.
- Add nightly cross-store drift reports.
- Finish automated backup/restore operations so recovery is routine, not heroic.

## User Feedback Captured
- The user was primarily worried about:
  - silent face loss
  - regressions introduced by community work
  - poor auditability of dismissed/non-face decisions
  - having enough confidence to start large-scale tagging in both communities
- The user explicitly preferred reversible data work with a checked-in recovery
  artifact over silent destructive cleanup.
