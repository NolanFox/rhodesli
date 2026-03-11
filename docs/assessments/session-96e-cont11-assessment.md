# Session 96e-cont11 Assessment

## Verdict
PASS with one residual low-risk exception preserved non-destructively.

- Required gates are green:
  - `pytest tests/ -x -q` → `4091 passed, 7 skipped`
  - `pytest rhodesli_ml/tests/ -x -q` → `566 passed`
- Local data audit is structurally clean:
  - `0` critical issues
  - `0` orphan faces
  - `0` duplicate face assignments
  - `0` missing identity face refs
  - `0` merge chains
  - `2` remaining face records without embedding artifacts
- Live deploy is current and healthy:
  - Railway deployment `49b4b3af-d47f-40b7-98d8-044398b4bee5` → `SUCCESS`
  - `/health` returned `200` with `1885` identities and `938` photos

## Findings Closed

| Finding | Status | Closure |
|-------|--------|---------|
| Structured-anchor merge regression | FIXED | `merge_identities()` now handles mixed anchor formats safely |
| App test gate red | FIXED | Full app suite now passes end-to-end |
| Force-state bypassed identity history | FIXED | forced state transitions now use append-only registry history |
| Approval/discovery flows bypassed identity history | FIXED | audited registry helpers now cover rename / candidate / negative mutations |
| Photo pages could silently lose faces when embeddings drifted from `photo_index.json` | FIXED | cache now preserves registry/photo-index face records even when bbox/embedding artifacts are missing |
| Full-suite ML flake in calibration training | FIXED | early stopping now requires meaningful `min_delta` improvement |
| Harness docs stale after cont10 | FIXED | cont11 assessment, delta artifact, session log, roadmap, backlog, changelog all updated |

## 124 Embeddings Follow-Up

InsightFace was run.

Evidence:
- prior session terminal history shows 23 source photos downloaded from R2, InsightFace loaded locally, and 130 embeddings generated
- `data/embeddings.npy` size increased in the earlier commit chain
- the audit moved from `124` missing embeddings to `2`

Why it happened:
- older ingest / repair runs left some face IDs in `photo_index.json` and `identities.json` without matching embedding rows
- re-running InsightFace was able to regenerate most of them, but 2 face IDs were not reproducible with the same detection artifacts
- root cause for the user-visible regression was deeper than embeddings: the app trusted embeddings as the photo-face source of truth, so any surviving registry-only face record disappeared from the photo page

What changed to prevent recurrence:
- photo pages now preserve the registry / `photo_index.json` face record even if the embedding or bbox artifact is missing
- the page shows an explicit archival-record note instead of silently dropping the face
- the ingest / audit path already catches orphan faces, duplicate assignments, merge chains, missing upload dates, and placeholder confirmations; this session added the missing UI/data-contract protection for artifact drift

## Remaining Exception

Two face records remain preserved without local embedding artifacts:

1. `inbox_a56c556100a9`
- Identity: `Caden Franco Sadis`
- Photo: `https://rhodesli.nolanandrewfox.com/photo/d5bc8746012a6da3`
- Person: `https://rhodesli.nolanandrewfox.com/person/4369c2f0-5c5e-43ff-9e47-1b6806a46531`
- Live state: page now shows `11 people detected · 10 identified`, surfaces the archival-record note, and includes Caden in the people strip

2. `inbox_e64c25fc88a7`
- Identity: `Unidentified Person df1a2b64`
- Photo: `https://rhodesli.nolanandrewfox.com/photo/92229cbf4ca92644`
- Person: `https://rhodesli.nolanandrewfox.com/person/df1a2b64-c88f-4b6f-83d2-52374cb269f6`
- Live state: page now shows `4 people detected · 0 identified` and surfaces the archival-record note instead of silently hiding the extra record

Interpretation:
- these are not active integrity failures anymore
- they are preserved archival face records awaiting manual judgment about whether they represent unreproducible real detections or historical false positives
- because they are now surfaced and documented, they are safe to leave in place without risking silent face loss

## Reversible Data Trail

Non-destructive data work is documented in:
- `docs/assessments/session-96e-cont11-local-audit-before.json`
- `docs/assessments/session-96e-cont11-local-audit-after.json`
- `docs/assessments/session-96e-cont11-local-delta.json`

Backup path:
- `data/backups/identities.json.20260311_033425_792917`

Current `data/identities.json` remains aligned with the backup-bearing repair pass.

Delta summary from `HEAD:data/identities.json` to current worktree data:
- `87` identities added, all merge-marked
- `922` existing identities changed
- `24` new identity-history events added:
  - `22` rename
  - `2` state_change
- `55` merge-chain repair breadcrumbs recorded in metadata
- `2` Netanel Menashe anchor refs quarantined non-destructively in metadata

## Final Confidence

I am confident the app is stable enough for the next upload validation pass on Rhodes and Fox Family.

What I am confident about:
- no active critical integrity issues remain in local data
- the test gates are green
- the live deploy is healthy
- the specific “losing faces” regression path is closed
- all data modifications from this closeout have an explicit backup and unwind trail

What is still worth validating manually:
- one new Rhodes upload
- one new Fox Family upload
- confirm both appear in the correct community and survive re-open / page refresh / people-strip rendering
