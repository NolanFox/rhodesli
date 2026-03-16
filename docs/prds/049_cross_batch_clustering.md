# PRD-049: Cross-Batch Clustering & Match Notifications

**Author:** Nolan Fox (requirements), Claude (spec)
**Date:** 2026-03-16
**Session:** 108 (analysis), 109 (implementation)
**Status:** Ready for implementation
**Predecessor:** Session 108 clustering analysis
**Context:** docs/session_context/session-108-clustering-analysis.md

## Problem Statement

When new photos are uploaded to an existing community, the ML pipeline detects faces and groups them within the upload batch (threshold 0.95). But it NEVER compares the new faces against existing faces in the archive. This means:

1. A person uploaded in batch 2 who appeared in batch 1 is never identified as the same person
2. The Proposals sidebar only shows matches against CONFIRMED identities — INBOX-to-INBOX matches are invisible unless you navigate to each identity
3. There's no notification when an upload produces matches
4. The "find this person" workflow (upload reference photo, see if they're in the archive) doesn't work

**Validated by:** James Fields case study (Session 108). 2 photos uploaded, 9 faces detected, zero matches surfaced despite Person 3474 being distance 0.87 from Person 28fa8bfa (well within grouping threshold).

## User Stories

1. **As an admin uploading photos**, I want new faces to be compared against ALL existing faces so that I'm told "3 of your faces may match existing people."
2. **As an admin reviewing proposals**, I want to see INBOX-to-INBOX matches (not just INBOX-to-CONFIRMED) so that I can identify people across unconfirmed photos.
3. **As an admin who confirmed a new identity**, I want the system to re-check existing faces against the newly confirmed anchor so that existing matches are surfaced.
4. **As an admin who made a bad merge**, I want to undo it completely and have monitoring catch compounding errors.

## Design

### Clustering Tiers (When It Runs)

| Trigger | Within-batch (auto-merge) | Cross-batch (proposals) |
|---------|--------------------------|------------------------|
| Initial upload (new community) | YES at 0.95 | Nothing to match against |
| Subsequent upload | YES at 0.95 | **NEW: YES against all existing faces** |
| Single photo upload | YES (limited by co-occurrence) | **NEW: YES against all existing faces** |
| Admin clicks Recluster | YES (re-run on all INBOX) | **NEW: YES full cross-batch** |
| After confirming an identity | No | **NEW: Re-match INBOX against new confirmed** |

### Match Confidence Tiers

| Tier | Distance | Action | UI Treatment |
|------|----------|--------|-------------|
| Very High | < 0.70 | Proposal + prominent notification | Red badge "Almost certain match", one-click merge |
| High | 0.70-0.95 | Proposal + notification | Orange badge "Likely match" |
| Moderate | 0.95-1.05 | Proposal only | Yellow badge in Proposals sidebar |
| Display-only | > 1.05 | Similar Identities panel | Visible on-demand, not proactive |

### No Auto-Merge for Cross-Batch

**Decision:** ALL cross-batch matches are proposals requiring human review. No auto-merge.

**Why:** Empirical data shows Charles Fox ↔ Roland Fox (father-son) at distance 0.50. Any auto-merge threshold would create false positives with family members. See AD-226 and session-108-clustering-analysis.md for threshold analysis.

### Notification System

After upload completes and cross-batch matching runs:

1. **In-app notification** (Notifications sidebar): "Your upload of [N photos] found [M possible matches] with existing people."
2. **Click-through**: notification links to a filtered Proposals view showing only matches from this upload.
3. **Email** (via Resend, if configured): Same message with top 3 matches previewed.

After admin confirms an identity and re-matching runs:

1. **In-app notification**: "[Person Name] was confirmed. [N new matches] found."

### Events & Audit Trail

Every cross-batch match generates:

**In `ml_runs` table:**
```
run_id, pipeline_type="cross_batch_matching",
config_json={threshold, community_id, triggered_by, upload_job_id},
status, result_summary={proposals_created, tier_breakdown},
duration_ms
```

**In `ml_proposals` table:**
```
proposal_id, run_id, source_identity_id, target_identity_id,
score (distance), calibrated_score, tier, status="pending",
match_type="cross_batch" (NEW field to distinguish from within-batch)
```

**In `audit_log` (for merges):**
```
action="MERGE", target_id, actor (admin email),
entry_data={source_id, distance, proposal_id, merge_type="manual_from_proposal"}
```

### Undo & Monitoring

**Undo:** Existing `undo_merge` endpoint + merge_history snapshots. No changes needed.

**Monitoring (new):**
- `/api/health/data` extended: report identities with > 10 faces (possible bad merge chain)
- Weekly digest: identities with highest internal face variance (possible mixed identity)
- Track undo rate as signal for threshold calibration

## Technical Design (SDD)

### New Code Paths

**1. Cross-batch matching function** (`core/cross_batch_matching.py` — new file)

```python
def find_cross_batch_matches(
    new_face_ids: list[str],
    identities: dict,
    face_data: dict,
    photo_registry: PhotoRegistry,
    threshold: float = 1.05,
    community_id: str = None,
) -> list[dict]:
    """
    Compare new faces against ALL existing identities (INBOX, PROPOSED, CONFIRMED).
    Returns proposals sorted by distance.

    Unlike find_candidate_matches() which only targets CONFIRMED,
    this matches against everything for comprehensive coverage.
    """
```

Key differences from existing `find_candidate_matches()`:
- Matches against ALL states (not just CONFIRMED)
- Community-scoped (only compare within same community)
- Returns match_type field ("cross_batch_vs_confirmed" or "cross_batch_vs_inbox")
- Respects co-occurrence blocks
- Deduplicates against existing proposals

**2. Wire into upload pipeline** (`app/upload_routes.py`)

After existing auto-cluster and grouping steps in `_background_ingest()`:

```python
# NEW: Cross-batch matching (Session 109, PRD-049)
if result.get("status") in ("success", "partial") and result.get("face_ids"):
    try:
        from core.cross_batch_matching import find_cross_batch_matches

        new_face_ids = result.get("face_ids", [])
        cross_matches = find_cross_batch_matches(
            new_face_ids, identities_data, face_data_dict,
            photo_registry, community_id=upload_community_id
        )

        if cross_matches:
            # Write to ml_proposals table
            # Create notification for uploader
            # Update proposals.json
    except Exception as e:
        logger.error(f"Cross-batch matching failed (non-fatal): {e}")
```

**3. Wire into confirm identity** (`app/identity_routes.py`)

After confirming an identity, trigger re-matching:

```python
# After registry.confirm_identity():
# Queue cross-batch re-match in background thread
def _post_confirm_rematch():
    confirmed_face_ids = identity.get("anchor_ids", [])
    # find_candidate_matches() already handles CONFIRMED targets
    # Just need to re-run and write new proposals
```

**4. Update admin recluster endpoint** (`app/sync_routes.py`)

Add cross-batch matching to the `/api/admin/recluster` endpoint:

```python
# Step 3 (NEW): Cross-batch matching
from core.cross_batch_matching import find_cross_batch_matches
cross_matches = find_cross_batch_matches(
    all_inbox_face_ids, identities_data, face_data_dict,
    photo_registry, community_id=community_id
)
results["cross_batch_matches"] = len(cross_matches)
```

**5. Notification creation** (`app/notifications.py` or existing notification system)

```python
def create_upload_match_notification(
    uploader_email: str,
    job_id: str,
    matches: list[dict],
    community_id: str,
):
    """Create in-app notification + optional email for upload matches."""
```

### Files Modified

| File | Change |
|------|--------|
| `core/cross_batch_matching.py` | NEW — cross-batch matching function |
| `app/upload_routes.py` | Add cross-batch step after grouping |
| `app/identity_routes.py` | Add post-confirm re-matching |
| `app/sync_routes.py` | Add cross-batch to recluster endpoint |
| `core/config.py` | Add CROSS_BATCH_THRESHOLD constant |
| `tests/test_cross_batch.py` | NEW — tests for cross-batch matching |

### Files NOT Modified

| File | Why |
|------|-----|
| `core/grouping.py` | Within-batch grouping unchanged |
| `core/identity_scoring.py` | Existing find_candidate_matches unchanged |
| `core/registry.py` | Merge logic unchanged (undo already works) |
| `app/main.py` | Sidebar counts already read proposals.json |

## Acceptance Criteria

- [ ] Upload 2 photos of the same person to Fox Family → proposals generated for the match
- [ ] Upload 1 photo of a person already in the archive → notification: "1 possible match"
- [ ] Confirm a James Fields face → other James Fields faces appear as proposals
- [ ] Admin recluster → cross-batch matches generated
- [ ] All matches logged to ml_runs + ml_proposals tables
- [ ] Undo a cross-batch merge → fully reversible
- [ ] Charles Fox ↔ Roland Fox (distance 0.50) → appears as proposal, NOT auto-merged
- [ ] Co-occurrence faces → not proposed for cross-batch merge

## Test Plan (James Fields Validation)

1. **Before implementation:** Document current state of James Fields identities
2. **After cross-batch wiring:** Run recluster → verify Person 3474 appears as proposal for Person 28fa8bfa
3. **After confirm wiring:** Confirm one James Fields face → verify other 7+ faces appear as proposals
4. **Verify no false positives:** Charles Fox and Roland Fox should NOT be auto-merged
5. **Verify undo:** Merge two James Fields faces → undo → both restored

## Out of Scope

- Automatic collage detection (future ML feature)
- GEDCOM-informed matching (family relationships as exclusion signal)
- Per-identity adaptive thresholds (ML-098 in BACKLOG)
- Real-time face comparison during upload preview

## References

- docs/session_context/session-108-clustering-analysis.md — Empirical data + screenshots
- docs/architecture/PARALLEL_AGENT_STRATEGY.md — Implementation parallelization
- docs/prds/048_same_photo_merge_override.md — Collage override (shipped Session 108)
- AD-226 — Cross-batch threshold decision (to be created)
- core/identity_scoring.py — Existing find_candidate_matches (reference implementation)
- core/grouping.py — Existing within-batch grouping (unchanged)
