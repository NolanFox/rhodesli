# PRD-040: Batch Cluster Validation

**Status:** Draft
**Author:** Session 100f
**Date:** 2026-03-14
**Source:** FB-13 (Session 100e triage feedback)

## Problem Statement

After uploading a large photo collection (e.g., 636 Charlie Fox photos), the ML pipeline produces hundreds of INBOX identity clusters. Most are valid (same person grouped correctly). The current speed-run mode reviews one cluster at a time — too slow for pure validation when most clusters are correct.

Users need a way to validate clusters in bulk: see all INBOX clusters at a glance, deselect the bad ones, and confirm the rest in one action.

## Target Users

1. **Nolan (admin)** — Power user triaging 200+ Fox Family clusters
2. **Claude Benatar (contributor)** — Non-technical user who may help with identification after clusters are validated and named

## User Flow

### Entry Point
Admin sidebar: "Batch Validate" link in the cluster review section, or accessible from `/c/{slug}/admin/cluster-batch`.

### Step 1: View INBOX Grid
- Page loads showing all INBOX identity cards in a grid
- Sorted by face count descending (high-confidence clusters first)
- Each card shows:
  - Representative face crop (largest/best quality), sized at minimum 80×80px
  - Face count badge (e.g., "44 faces")
  - Small identity ID text
  - Checkbox overlay (top-left corner), checked by default
- Filter bar at top: face count threshold buttons (All, 2+, 5+, 10+), community dropdown
- "Select All" / "Deselect All" toggle
- Count badge: "N of M selected"

### Step 2: Review and Deselect
- Admin scrolls through the grid, deselecting any bad clusters (mixed faces, garbage detections)
- Clicking a card toggles its selection state
- Cards can be expanded to show all face crops (click to enlarge)

### Step 3: Batch Confirm
- "Confirm Selected (N)" button at bottom (sticky footer)
- On click: all selected identities are confirmed:
  - `candidate_ids` moved to `anchor_ids`
  - `state` set to `CONFIRMED`
  - `log_user_action("BATCH_CONFIRM", ...)` called for each
- After confirm: summary panel shows results ("42 clusters confirmed, 1,247 total faces")
- Link to continue: "Name these people →" (goes to speed-run enrichment mode for confirmed-but-unnamed)

### Step 4: (Future) Name & Link
Not in this PRD. Confirmed clusters with no name show as "Unidentified Person NNN" until the enrichment flow (Phase 3) is used.

## Acceptance Criteria

1. GET `/c/{slug}/admin/cluster-batch` renders a grid of all INBOX identities for the community
2. Cards show face crop, face count, checkbox (checked by default)
3. Face count filter buttons work (All, 2+, 5+, 10+)
4. Select All / Deselect All toggles all checkboxes
5. "Confirm Selected (N)" count updates as selections change
6. POST `/api/cluster-review/batch-confirm` accepts `identity_ids[]` list
7. Each confirmed identity: candidates → anchors, state → CONFIRMED
8. `log_user_action("BATCH_CONFIRM")` called per identity with identity_id, face_count, mode, admin
9. Summary shown after confirm with count and total faces
10. Community scoping: only shows identities from the current community's photos
11. Page is admin-only (returns 401/403 for non-admins)

## Out of Scope

- Naming clusters in batch (separate enrichment flow)
- GEDCOM linking from batch view
- Undo batch confirm (use existing undo infrastructure from speed-run)
- Pagination (222 clusters is manageable in a single grid — revisit if >500)
- Drag-to-select or multi-select gestures

## Data Model Changes

None. Uses existing `IdentityRegistry` confirm flow (same as speed-run confirm-all).

## Technical Notes

- Route lives in `app/cluster_review_routes.py`
- Reuse `_get_crop_url_for_face()` for face crops
- Community scoping via `_main_mod._get_community(req)` pattern
- JS: vanilla event delegation for checkbox state, per UI scalability rules
