# Session 96e-cont12 Assessment

## Verdict
PASS.

This file is the canonical human-readable summary artifact for the cont12 closeout.
It is intentionally breadcrumbed to the machine-readable audit chain, the recovery
artifacts, the backlog follow-ups, and the lessons created from this incident.

- Local data audit is clean:
  - `0` critical issues
  - `0` orphan faces
  - `0` duplicate face assignments
  - `0` missing identity face refs
  - `0` merge chains
  - `0` missing upload dates
  - `0` missing embeddings
- Required gates are green:
  - `pytest tests/ -x -q` -> `4098 passed, 7 skipped`
  - `pytest rhodesli_ml/tests/ -x -q` -> `566 passed`
- Live is current and healthy:
  - Railway deployment `99170803-089c-4dc4-8299-b52fba96e5a9` -> `SUCCESS`
  - `/health` -> `200`, `1931` active identities, `938` photos, ML ready

## What Closed

| Area | Before | After | Closure |
|------|--------|-------|---------|
| Structural integrity | `157` orphan faces, `122` merge chains, `1` duplicate face, `2` ghost refs, `2` placeholder confirmed identities | `0` across all structural checks | Local registry/photo index reconciled non-destructively |
| Embedding coverage | `10` missing embeddings at cont12 baseline | `0` | Repaired `8` embeddings, including crop-matched recovery of the last `2` archival records |
| Production shadow drift | Supabase `3524` identities vs audited snapshot `3412` | Supabase `3412` identities | Pruned `112` stale identity rows after writing a checked-in recovery artifact |
| Live/test confidence | App suite previously red in this continuation | Full app + ML suites green | Timeline filter gate restored and deployed |

## 124 Missing Embeddings

Yes, InsightFace was run.

What happened across the full closeout:
- Earlier follow-up work downloaded `23` source photos from R2, ran InsightFace locally, and regenerated `130` embeddings. That reduced the missing-embedding count from `124` to `2`.
- This continuation then repaired the final gap:
  - `6` straightforward face repairs were re-embedded from source photos.
  - The last `2` archival records were matched back to current detections by crop correlation and then embedded.
- Final local audit now reports `missing_embeddings = 0`.

Evidence:
- `data/embeddings.npy` changed in the repair commits.
- `docs/assessments/session-96e-cont12-embedding-repair-report.json` records the exact repaired face IDs, source photos, detection scores, and the two archival crop matches.
- `docs/assessments/session-96e-cont12-local-audit-before.json`
- `docs/assessments/session-96e-cont12-local-audit-after-embedding-repair.json`
- `docs/assessments/session-96e-cont12-local-audit-final.json`

Why this occurred:
- durable face records in `identities.json` / `photo_index.json` outlived their embedding artifacts
- earlier repair/ingest paths were not consistently publishing refreshed `embeddings.npy`
- the UI had been trusting embedding-backed cache data too much, so artifact drift looked like face loss

What now prevents recurrence:
- staged production pushes now publish `embeddings.npy`
- photo pages preserve registry-backed face records even if artifacts drift
- the data integrity audit explicitly checks embedding coverage
- ingest protections from cont10/cont11 remain in place: upload dates, dedup safety, append-only history, batch orphan repair

## How The Data Became Fragile

This was not one bug. It was a stack of weak contracts that compounded:

1. Source-of-truth drift.
   - The project moved from JSON/volume data toward Postgres as source of truth, but some read/write paths still depended on shadow JSON, cache aliases, or bundle data.
   - That created split-brain behavior: different layers could all be "locally consistent" while disagreeing with each other.

2. Additive-only reconciliation.
   - Backfills and shadow syncs upserted rows into Supabase but did not prune stale rows.
   - That let obsolete identities survive in Postgres after the audited snapshot had already been corrected.

3. Incomplete write-path auditability.
   - Some routes changed identity state directly instead of using append-only registry history.
   - The data itself could look correct while the unwind trail was incomplete.

4. Artifact/data coupling.
   - Embeddings and crops are derivative artifacts, but the UI effectively treated them as canonical for photo-face rendering.
   - When artifacts drifted from registry records, faces appeared to vanish even though the archive record still existed.

5. Community + alias complexity.
   - Community rollout introduced more indirection: community scoping, cache IDs, canonical IDs, and shadow sync paths.
   - That raised the cost of any single inconsistent contract.

The architecture intent was right. What failed was enforcement during the transition: Postgres became important before every mutation, cache, audit path, and recovery path was fully Postgres-native and continuously checked for drift.

## Related Artifacts

- Summary + verdict:
  - `docs/assessments/session-96e-cont12-assessment.md`
- Session context:
  - `docs/session_context/session-96e-cont12-context.md`
- Machine-readable audits:
  - `docs/assessments/session-96e-cont12-local-audit-before.json`
  - `docs/assessments/session-96e-cont12-local-audit-after-structural.json`
  - `docs/assessments/session-96e-cont12-local-audit-after-embedding-repair.json`
  - `docs/assessments/session-96e-cont12-local-audit-final.json`
  - `docs/assessments/session-96e-cont12-embedding-repair-report.json`
- Recovery / unwind artifacts:
  - `docs/assessments/session-96e-cont12-supabase-prune-backup.json`
  - `docs/assessments/session-96e-cont12-supabase-prune-result.json`
- Follow-up backlog items:
  - `DATA-009` in `docs/BACKLOG.md`
  - `DATA-010` in `docs/BACKLOG.md`
- Lessons created from this incident:
  - Lessons `122`-`124` in `tasks/lessons/data-lessons.md`

## Reversible Data Trail

Production-affecting changes were preserved non-destructively:
- Live volume backups returned by `/api/sync/push`:
  - `identities.json.bak.1773237513`
  - `photo_index.json.bak.1773237513`
- Checked-in Supabase prune backup:
  - `docs/assessments/session-96e-cont12-supabase-prune-backup.json`
- Checked-in Supabase prune result:
  - `docs/assessments/session-96e-cont12-supabase-prune-result.json`
- Machine-readable audit chain:
  - `docs/assessments/session-96e-cont12-local-audit-before.json`
  - `docs/assessments/session-96e-cont12-local-audit-after-structural.json`
  - `docs/assessments/session-96e-cont12-local-audit-after-embedding-repair.json`
  - `docs/assessments/session-96e-cont12-local-audit-final.json`

The only destructive production operation was the Supabase prune of `112` stale identity rows, and that happened only after:
- a clean audited snapshot was written
- the stale rows were exported in full to a checked-in JSON artifact
- the live volume JSON backups were captured

## Residual Risk

I am comfortable calling the app stable enough for real tagging and upload validation now.

I am not claiming the risk is mathematically zero. The remaining systemic hardening work is operational:
- automated stale-row prune/reconcile tooling for Supabase shadow tables
- automated nightly cross-store drift reporting
- automated backup/restore drills instead of manual, session-driven recovery

Those are now breadcrumbed as backlog items rather than hidden unknowns.

## Lessons Created

- **Lesson 122**: canonical registry records must define face existence, not derivative artifacts
- **Lesson 123**: additive-only shadow sync is not reconciliation
- **Lesson 124**: production data repairs need machine-readable unwind artifacts before cleanup
