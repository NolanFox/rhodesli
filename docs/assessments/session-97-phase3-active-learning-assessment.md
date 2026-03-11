# Session 97 Phase 3 Assessment

**Date:** 2026-03-11  
**Scope:** Offline active-learning queue plus reversible pair-label review  
**Status:** Implemented and live-artifacted

## Outputs

- `rhodesli_ml/active_learning.py`
- `scripts/build_active_learning_queue.py`
- `app/cluster_review_routes.py`
- `data/active_learning_queue.json`
- `docs/assessments/session-97-phase3-queue-report.json`

## What Landed

- Offline queue builder that mines reviewable face pairs without putting heavy ML in request paths
- Diversity gate:
  - max 2 items per target identity in the first batch of 10
  - prioritizes boundary, ambiguous, tail, and alternative-candidate slices
- Review UI integration inside `/admin/upload-review`
- Calibration-style label persistence for queue actions:
  - local current-state cache
  - audit-log mirror
  - reversible label path
  - Supabase `calibration_pairs` upsert when available

## Live Result

`python scripts/build_active_learning_queue.py --output data/active_learning_queue.json --report-output docs/assessments/session-97-phase3-queue-report.json`

Produced:

- queue size: `20`
- candidate pool inspected: `5619`
- first-batch max per identity: `2`
- diversity gate pass: `true`
- underrepresented / hard-slice share: `1.0`

## Decision

Keep the queue enabled in the review surface.

Reason:

- it satisfies the Phase 3 diversity constraint on the live snapshot
- it keeps labels non-canonical and reversible
- it does not change canonical identities unless an admin separately confirms or rejects a proposal

## Residual Limits

- Local-only active-learning labels are cached in `active_learning_labels.json`; if Supabase is unavailable, explicit export or merge is still needed before local recalibration consumes them.
- Queue quality still depends on the current unresolved-face pool. As more Fox-family data lands, regenerate the artifact instead of reusing the old queue.
