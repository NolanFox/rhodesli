# PRD-029: Photo Back Images & Media Groups

**Status**: PARTIALLY SHIPPED (Session 90b). Upload + flip + transcription work. Remaining: media group API, Front/Back label, browse filter, card badges. Completion planned Session 91 Track D.
**Origin**: User feedback — back image upload broken, needs proper UX and data model
**Priority**: P1 — blocks contributor workflow

## Problem Statement

The "Add a back image" feature on photo pages is completely broken — uploads fail silently. The back-of-photo flip UX exists in CSS but has never worked end-to-end. As we grow the collection, we need a scalable data model that supports multi-image photo groups (front/back, album page scans with sub-crops, etc.).

## User Stories

1. Admin uploads a back-of-photo image → it saves, serves, and the "Turn Over" button appears
2. Any user clicks "Turn Over" → photo flips with 3D animation showing back
3. User clicks again → photo flips back to front
4. Admin browses photos → can filter by "Has back image" / "Front only"
5. Back image inherits collection/source/URL from front by default (editable)
6. Clear visual indicator shows whether viewing front or back

## Data Model

### photo_index.json changes
```json
{
  "photos": {
    "<photo_id>": {
      "path": "image.jpg",
      "media_group_id": "<photo_id>",  // Same as photo_id for front images
      "media_role": "front",            // "front" | "back" | "page_crop" | "detail"
      "related_media": [                // Other images in this group
        {"photo_id": "<back_photo_id>", "role": "back"}
      ],
      "back_image": "image_back.jpg",   // Legacy field, kept for compat
      "back_transcription": "...",
      ...existing fields...
    }
  }
}
```

### Supabase: photos table additions
- `media_group_id` UUID — groups related images (front+back share same group)
- `media_role` TEXT — 'front', 'back', 'page_crop', 'detail'
- `parent_photo_id` UUID NULLABLE — for back images, points to front

### Design Principles
- Every photo has a `media_group_id` (defaults to its own `photo_id`)
- Front images are the "primary" — they own the group
- Back images are stored as separate photo entries but linked via `media_group_id`
- Back images inherit collection/source/source_url from their front
- The back image file goes to `raw_photos/` and R2 `raw_photos/` (same as fronts)
- Future: album page crops would use `media_role: "page_crop"`

## API Routes

### Upload back image (fix existing)
`POST /api/photo/{photo_id}/back-image`
- Save file to raw_photos/ (local) or staging/back_images/ (production)
- Upload to R2 if in R2 mode
- Create back photo entry in photo_index.json with media_group linkage
- Set front photo's `back_image` field and `related_media`
- Return updated photo section via HTMX swap

### Get photo with media group
`GET /api/photo/{photo_id}/media-group`
- Returns all related media for a photo (front, back, etc.)

## UX Specification

### Flip Animation (existing CSS is good)
- 3D perspective flip with `rotateY(180deg)`
- Shadow lift during flip
- Face overlays fade during flip
- 0.9s cubic-bezier timing

### Flip Trigger
- "Turn Over" button in action bar (existing)
- Also: subtle hint text below photo when back exists
- Visual indicator: small "Front" / "Back" badge in corner during/after flip

### Photo Browse Filter
- New filter option in sort/filter bar: "All" | "Front only" | "Has back"
- Visual badge on photo cards that have back images (small flip icon)

### Admin Upload UX
- Current "Add a back image" section with file input
- After upload: page refreshes to show "Turn Over" button
- Transcription field preserved

## Implementation Steps

1. Fix the upload endpoint — ensure file saves to correct location and serves
2. Add R2 upload for back images (use boto3 like main upload pipeline)
3. Add media_group fields to photo_index.json schema
4. Add front/back filter to browse page
5. Add visual indicators (badges on cards, front/back label)
6. Verify with Claude Chrome end-to-end

## Test Plan

- Upload back image → verify file saved
- Navigate to photo → "Turn Over" button visible
- Click "Turn Over" → photo flips to back
- Click again → flips back to front
- Browse photos → filter by "Has back" works
- Back image serves correctly from R2 in production

## Out of Scope (this session)

- Gemini OCR of back writing (future)
- Album page crop workflow (data model supports it, no UI yet)
- Non-admin back image upload
