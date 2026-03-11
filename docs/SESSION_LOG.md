# Session 96e-cont12 Log — Production Reconciliation + Root Cause Closeout
## Mission: finish the data audit, reconcile live state safely, preserve a reversible unwind trail, and explain how the archive became fragile
## Started: 2026-03-11
## Version: v0.97.10
## Assessment: docs/assessments/session-96e-cont12-assessment.md

### Phase 1: Local Baseline
- [x] Baseline audit captured in `docs/assessments/session-96e-cont12-local-audit-before.json`
- [x] Baseline confirmed structural drift: `157` orphan faces, `122` merge chains, `1` duplicate face, `2` ghost refs, `10` missing embeddings
- [x] Earlier cont11 findings remained closed; cont12 focus narrowed to data/state reconciliation

### Phase 2: Local Structural Repair
- [x] Local registry/photo index reconciled to `3412` identities and `938` photos
- [x] Structural checks closed: `0` orphan faces, `0` duplicate faces, `0` missing identity refs, `0` merge chains
- [x] Structural post-state captured in `docs/assessments/session-96e-cont12-local-audit-after-structural.json`

### Phase 3: Embedding Repair
- [x] Confirmed InsightFace had been run in the earlier continuation and had already reduced `124` missing embeddings to `2`
- [x] Repaired `8` embeddings in cont12, including crop-matched recovery of the final `2` archival records
- [x] Embedding repair report written: `docs/assessments/session-96e-cont12-embedding-repair-report.json`
- [x] Final local audit now reports `0` missing embeddings

### Phase 4: Production Reconciliation
- [x] Audited snapshot written to Supabase: `3412` identities, `938` photos
- [x] Same audited snapshot written to live volume via `/api/sync/push`
- [x] Live backup filenames captured:
  - `identities.json.bak.1773237513`
  - `photo_index.json.bak.1773237513`
- [x] Detected additive-only shadow drift in Supabase: `112` stale identity rows persisted after upsert
- [x] Exported stale rows to checked-in artifact: `docs/assessments/session-96e-cont12-supabase-prune-backup.json`
- [x] Pruned `112` stale Supabase identity rows only after the backup artifact existed
- [x] Post-prune result captured in `docs/assessments/session-96e-cont12-supabase-prune-result.json`

### Phase 5: App Reliability
- [x] Staged production pushes now publish `embeddings.npy`
- [x] Canonical photo metadata preferred during same-day upload sorting / alias resolution
- [x] Timeline person filter now excludes people with zero visible dated photos under the current filters
- [x] Full app suite gate restored on the deployed head

### Phase 6: Verification
- [x] `python scripts/data_integrity_audit.py --data-dir data/ --json` -> `0` structural issues, `0` missing embeddings
- [x] `pytest tests/ -x -q` -> `4098 passed, 7 skipped`
- [x] `pytest rhodesli_ml/tests/ -x -q` -> `566 passed`
- [x] Railway deployment `99170803-089c-4dc4-8299-b52fba96e5a9` -> `SUCCESS`
- [x] `/health` -> `200`, `1931` active identities, `938` photos, ML ready
- [x] Live photos page and photo partials rechecked after reconciliation
- [x] Lessons `122`-`124` added for canonical-vs-derivative data contracts, stale-row reconciliation, and backup-first production repair

### Key Commits
- `0e78426` `[codex] fix(photos): prefer canonical alias metadata`
- `08ece79` `[codex] fix(pipeline): publish embeddings with staged uploads`
- `65747b1` `[codex] data(audit): reconcile production-backed integrity gaps`
- `839caa6` `[codex] fix(timeline): keep person filter timeline-backed`
