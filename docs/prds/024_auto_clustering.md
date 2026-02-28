# PRD-024: Two-Tier Auto-Clustering Pipeline

**Status**: SHIPPED (Session 76a, v0.79.0)
**AD Reference**: AD-179 (Two-Tier Auto-Clustering at Upload Time)
**Implementation**: `core/auto_cluster.py`
**Tests**: `tests/test_auto_cluster.py` (37 tests)

---

## Problem

Inbox faces accumulate without matching to confirmed identities. With 775 identities
(60 confirmed, 472 inbox, 215 skipped), manual review of every unresolved face is
impractical. The existing `cluster_new_faces.py` pipeline produces 400+ manual
review items with no prioritization.

## Solution

A two-tier automatic clustering pipeline that runs after face detection during upload
(or as a backfill on existing data). Faces are classified by Euclidean distance to
the nearest confirmed identity cluster using best-linkage (min distance to any anchor).

### Tier 1 -- Auto-Add (distance < 0.85)

High-confidence matches added automatically as `candidate_ids` on the target confirmed
identity. Uses `provenance="model"` so admin must still confirm. The threshold 0.85
is well below p25=0.88 of the same-person pair distribution, giving near-zero
false positive risk.

### Tier 2 -- Suggest (0.85 <= distance < 1.10)

Moderate-confidence matches surfaced on the Discoveries page for admin review. The
upper bound 1.10 covers the bulk of the same-person distribution (mean=1.01,
std=0.19). Admin can accept (promotes to candidate) or reject (logs negative signal).

### Dedup Pass

Before distance-based clustering, an exact face_id dedup pass removes inbox
identities whose faces already appear in confirmed clusters. An inbox identity
is only deduped if ALL its face_ids exist in a single confirmed identity.

## Data Flow

```
Upload --> Detect Faces --> Generate Embeddings --> Auto-Cluster
                                                      |
                                          +-----------+-----------+
                                          |           |           |
                                       Dedup      Tier 1       Tier 2
                                     (merge)   (auto-add)   (suggest)
                                          |           |           |
                                          v           v           v
                                     merged_into  candidate_id  Discovery
                                                                  page
                                          |           |           |
                                          +-----------+-----------+
                                                      |
                                              Admin Review
                                                      |
                                          +-----------+-----------+
                                          |                       |
                                       Confirm                 Reject
                                    (anchor_id)            (negative_id)
                                          |                       |
                                          v                       v
                                    Ground truth           ML signal
                                    for training        for recalibration
```

## Threshold Validation

Thresholds validated against 982 same-person pairs from confirmed identities:

| Statistic | Value |
|-----------|-------|
| Mean      | 1.01  |
| Std Dev   | 0.19  |
| p5        | 0.70  |
| p25       | 0.88  |

Backfill results on 775 identities: 0 Tier 1 (all close matches already confirmed
by admin), 7 Tier 2 suggestions, 652 no match.

## Active Learning

Every auto-cluster action and admin decision is logged to `data/discovery_log.json`:

```json
{
  "face_id": "inbox_abc123",
  "target_identity_id": "uuid-...",
  "distance": 0.82,
  "tier": 1,
  "action": "auto_clustered",
  "user_decision": "confirmed",
  "user_decision_timestamp": "2026-02-28T..."
}
```

Confirm/reject signals feed back to similarity calibration (AD-149/150) and
threshold recalibration. As more ground truth accumulates, thresholds can be
tightened or loosened based on actual false positive/negative rates.

## Key Design Decisions

1. **candidate_ids, never anchor_ids** -- Gatekeeper pattern preserved. Auto-clustered
   faces require admin confirmation before becoming ground truth anchors.
2. **provenance="model"** -- Distinguishes ML assignments from human decisions.
   `provenance="human"` always takes priority per AD-006.
3. **Best-linkage distance** -- Min distance to any face in the cluster, not centroid.
   Heritage photos span decades; centroid averaging destroys signal (AD-001).
4. **Thread-safe logging** -- Discovery log uses a threading.Lock + atomic write
   (temp file + os.replace) for concurrent upload safety.

## Acceptance Criteria

- [x] Dedup pass identifies and merges exact face_id duplicates
- [x] Tier 1 auto-adds faces with distance < 0.85 as candidates
- [x] Tier 2 surfaces faces with 0.85 <= distance < 1.10 on Discoveries page
- [x] All actions logged to discovery_log.json
- [x] Admin can confirm/undo Tier 1 and accept/reject Tier 2 from Discoveries
- [x] Backfill script processes all existing unresolved faces
- [x] Pipeline wired into upload flow (process_uploads.py step 5)

## Out of Scope

- Per-identity adaptive thresholds (future: use within-cluster variance)
- Automatic anchor promotion (always requires human confirmation)
- Cross-archive clustering (single-community only)
- Real-time re-clustering on identity merge/reject (batch-only)

## Files

| File | Purpose |
|------|---------|
| `core/auto_cluster.py` | Core clustering logic (398 lines) |
| `scripts/backfill_auto_cluster.py` | CLI tool for batch processing |
| `scripts/process_uploads.py` | Upload pipeline (step 5 integration) |
| `tests/test_auto_cluster.py` | 37 unit tests |
| `tests/test_session76a.py` | Integration + threshold tests |
| `data/discovery_log.json` | ML audit trail (production) |
