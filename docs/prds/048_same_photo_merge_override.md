# PRD-048: Same-Photo Merge Override for Collages

**Author:** Nolan Fox (requirements), Claude (spec)
**Date:** 2026-03-16
**Session:** 108b
**Status:** In Progress

## Problem Statement

The co-occurrence rule ("faces in the same photo cannot be the same person") produces false positives for:
- **Collage photos**: Multiple sub-photos assembled into one image file
- **Photos of photo albums**: Person in foreground + same person in a framed photo on the wall
- **Before/after composites**: Same person at different ages in one image
- **Photos with pictures on walls**: Person standing near a framed photo of themselves

The current implementation has NO override — the merge is blocked at UI level (disabled "Blocked" button) AND backend level (HTTP 409 from `validate_merge()`). This prevents legitimate identification work.

## User Story

> As an admin reviewing Similar Identities, I want to override the "same photo" merge block when I can see the match is a collage or composite image, so that I can correctly identify people who appear in multiple sub-photos within one image file.

## Requirements

### Must Have
1. **Override button** replaces "Blocked" button when admin wants to force-merge
2. **Confirmation step** — cannot accidentally override; requires explicit acknowledgment
3. **"Same photo" warning remains prominent** — the indicator never disappears
4. **Audit trail** — override is logged with reason and actor
5. **Backend support** — merge endpoint accepts override parameter

### Must Not
- Auto-override without explicit human action
- Remove the co-occurrence indicator from the UI
- Change the default behavior (block is still default)
- Allow non-admin users to override

## UX Design

### Current Flow (blocked)
```
[Similar Identity Card]
  Person 1c8c316f  65% match  Dist: 0.84
  "Seen together in 1 photo"
  [Compare] [Blocked ❌] [Not Same]
```

### New Flow (override available)
```
[Similar Identity Card]
  Person 1c8c316f  65% match  Dist: 0.84
  ⚠️ "Seen together in 1 photo"
  [Compare] [Override ⚠️] [Not Same]
```

Clicking "Override ⚠️" opens a confirmation:
```
┌─────────────────────────────────────────┐
│  ⚠️ Same Photo Override                 │
│                                         │
│  These faces appear in the same photo:  │
│  [photo thumbnail]                      │
│  filename.jpg                           │
│                                         │
│  This is usually blocked because two    │
│  faces in the same photo are different  │
│  people. Override ONLY if this is a:    │
│                                         │
│  ○ Collage / composite image            │
│  ○ Photo of a photo album              │
│  ○ Photo with picture on wall          │
│  ○ Other (same person, different crop)  │
│                                         │
│  [Cancel]  [Confirm Override & Merge]   │
└─────────────────────────────────────────┘
```

### Key UX Decisions
1. **"Override" not "Merge"** — the button label signals this is non-standard
2. **Radio selection required** — forces the admin to classify WHY they're overriding
3. **Photo thumbnail shown** — so admin can visually verify it's a collage
4. **Amber warning color** — distinct from green "Merge" button
5. **Reason logged** — stored in merge history for audit

## Technical Design

### Backend Changes
1. **`validate_merge()` in `core/registry.py`**: Add `allow_co_occurrence: bool = False` parameter
2. **`merge_identities()`**: Pass through `allow_co_occurrence` to `validate_merge()`
3. **Merge endpoint in `app/identity_routes.py`**: Accept `override_co_occurrence=true` + `override_reason` in POST body
4. **Audit**: Store override reason in merge history metadata

### Frontend Changes
1. **`neighbor_card()` in `app/main.py`**: Replace disabled "Blocked" button with "Override ⚠️" for admins
2. **HTMX confirmation modal**: New partial endpoint for the override confirmation dialog
3. **Override POST**: Include `override_co_occurrence=true&override_reason=collage` in merge request

### Grouping Pipeline
- `group_inbox_identities()` does NOT get override capability — only human-initiated merges

## Co-Occurrence Preview Visualization (FB-008, Session 135c)

### Problem

The Override button (shipped Session 108b) uses a browser `confirm()` dialog — a plain
text prompt with no visual context. The admin cannot see WHICH photo has the co-occurrence
or verify the face detections before committing to an override merge. This forces blind
decisions on a safety-critical action.

### New Endpoint

`GET /api/identity/{target_id}/co-occurrence-preview/{neighbor_id}`

Returns an HTML partial showing:
- The shared photo (max-width 400px) with both face bounding boxes highlighted
- Target face: amber highlight ring
- Neighbor face: indigo highlight ring
- Photo filename below image
- Two buttons: "Cancel" (dismiss preview) + "Confirm Override & Merge" (execute merge)

Implementation reuses face overlay rendering from `_compare_photo_with_overlays` pattern
in compare_routes.py. Uses `find_shared_photo_filename()` (already exists) to locate the
co-occurring photo.

Auth: admin-only (`_check_admin`).

### Override Button Change

Replace `hx_confirm` browser dialog with HTMX two-step flow:

1. First click on "Override" → `hx_get` loads preview panel (slide-down below the button)
2. Preview panel shows: photo thumbnail + face highlights + filename
3. "Cancel" dismisses panel, "Confirm Override & Merge" executes the POST merge

This gives the admin visual confirmation before committing.

### Acceptance Criteria

- [ ] Preview endpoint returns photo HTML for co-occurring identities
- [ ] Preview endpoint returns 404 for non-co-occurring identities
- [ ] Non-admin cannot access preview endpoint
- [ ] Override button uses `hx_get` (not `hx_confirm`) to load preview
- [ ] Preview shows both face bounding boxes with distinct colors
- [ ] "Confirm Override & Merge" in preview executes the merge POST
- [ ] Override reason preserved in merge audit trail

---

## Out of Scope
- Automatic collage detection (future ML feature)
- Contributor-level override (admin only)
- Batch override (one at a time)

## Acceptance Criteria
- [ ] "Override ⚠️" button appears instead of "Blocked" for admin users
- [ ] Clicking "Override" shows confirmation with reason selection
- [ ] Merge succeeds with override, logged in merge history
- [ ] "Seen together" warning still visible after override option appears
- [ ] Non-admin users still see "Blocked" (no override)
- [ ] Backend rejects override without reason parameter
- [ ] Test coverage for override flow
