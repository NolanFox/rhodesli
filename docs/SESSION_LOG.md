# Session 96e-cont11 Log — Stability Closeout + Audit Trail
## Mission: close remaining regressions from cont10, verify data confidence, preserve a reversible audit trail, and make live testing safe
## Started: 2026-03-10
## Version: v0.97.9
## Assessment: docs/assessments/session-96e-cont11-assessment.md

### Phase 1: Close Outstanding Findings
- [x] Structured-anchor merge regression accounted for and fixed in shipped code
- [x] Force-state now records append-only history instead of mutating registry state directly
- [x] Approval / discovery mutations now record append-only identity history
- [x] Full app suite gate restored to green
- [x] Full ML suite gate restored to green
- [x] Harness docs reconciled with the true final state

### Phase 2: Photo-Face Investigation
- [x] Traced the Holocaust collage discrepancy to an embeddings-first cache contract bug
- [x] Confirmed `Caden Franco Sadis` still existed in registry and photo index despite being hidden from the photo page
- [x] Confirmed the wedding newspaper extra face record also survived in registry / photo index without current embedding artifacts
- [x] Updated photo pages to preserve registry / `photo_index.json` face records even when bbox / embedding artifacts are missing
- [x] Live URLs documented for both remaining archival face records

### Phase 3: Verification
- [x] Local audit: `0` critical, `0` orphan faces, `0` duplicate faces, `0` missing identity refs, `0` merge chains, `2` remaining archival face records
- [x] `pytest tests/ -x -q` → `4091 passed, 7 skipped`
- [x] `pytest rhodesli_ml/tests/ -x -q` → `566 passed`
- [x] Railway deployment `49b4b3af-d47f-40b7-98d8-044398b4bee5` → SUCCESS
- [x] `/health` → `200`, `1885` identities, `938` photos, ML ready
- [x] Live Holocaust collage page now shows `11 people detected · 10 identified` and includes Caden in the people strip
- [x] Live newspaper page now shows `4 people detected · 0 identified` and preserves the archival-record note

### Phase 4: Data Trail
- [x] Backup-bearing local data state preserved in `data/backups/identities.json.20260311_033425_792917`
- [x] Machine-readable before/after audit artifacts captured
- [x] Machine-readable delta artifact written: `docs/assessments/session-96e-cont11-local-delta.json`
- [x] No destructive deletes or blind overwrites performed during cont11 closeout

### Key Commits
- `6ea729f` `[codex] fix(photo): preserve archived face records`
- `f8ee973` `[codex] fix(ml): stabilize calibration early stopping`
- `76240a9` `[codex] fix(photo): polish archival face notice`
