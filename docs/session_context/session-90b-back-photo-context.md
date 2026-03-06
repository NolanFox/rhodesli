# Session 90b — Back-of-Photo Feature Context (Added Mid-Flight)

**Added during**: Session 90b, after main work was mostly complete
**Origin**: User feedback with screenshot showing broken "Add a back image" on production
**PRD**: docs/prds/029_photo_back_and_media_groups.md

## User Feedback (Verbatim Summary)

1. **Back image upload is completely broken** — will not upload
2. **Test case**: `david_franco_collection_family_pic_front_120015134_1084541148609556_3704013770439882984_n.jpg` (front) + `david_franco_collection_family_pic_back_119989505_1084543308609340_1028494195630688538_n.jpg` (back). Both in `~/Downloads/rhodes_pics_further_testing/`
3. **Flip UX must look good** — "seem like the photo is flipping" (CSS 3D flip already exists in code at main.py:20500-20565)
4. **Initiation should be intuitive and easy to discover**
5. **Back photos saved with same collection/source/url as front** — editable
6. **Filter for front/back** on the photos browse page (`/photos` section)
7. **Database field** for front/back tracking
8. **Scalable data model**: "super photo ID with sub photo ID for each side" — future: album page scans with sub-crops
9. **Claude Chrome verification required**: upload back image, flip, flip back, verify filter, verify visual indicators
10. **Gemini OCR planned for later** — not this session
11. **Log all work and breadcrumb it** — linked to session 90b harness

## Screenshot from User

Shows photo page `/photo/e8b2bcc3e6000161` with:
- "Admin: Add a back image" section visible
- "Choose File" button + "Transcribe writing on back" text input + "Upload" button
- Photo is from "Jews of Rhodes: Family Memories & Heritage" collection
- 11 faces detected, 0 identified
- The upload does NOT work when tried

## Current Code State

### Back Image Upload Endpoint (app/main.py:23710)
```python
@rt("/api/photo/{photo_id}/back-image")
async def post(photo_id, file, back_transcription, sess):
    # Saves to raw_photos/ (local) or staging/back_images/ (production)
    # Sets metadata: {"back_image": back_filename}
    # Returns success message div
```

**Suspected issues**:
1. File may not be getting to R2 (production serves from R2, not local filesystem)
2. The `photo_url(back_image)` call at line 20701 may not resolve correctly for back images
3. No HTMX swap target — the upload response replaces the form but doesn't trigger page refresh to show flip button
4. Staging path `data/staging/back_images/` may not exist or not get processed

### Flip CSS (app/main.py:20500-20565)
- 3D perspective flip with `rotateY(180deg)` — well-designed
- 0.9s cubic-bezier timing
- Face overlays fade during flip
- Shadow lift effect
- Back side has warm photo-texture background

### Flip JS (app/main.py:21153)
```javascript
var flipBtn = e.target.closest('[data-action="flip-photo"]');
if (flipBtn) {
    var inner = document.getElementById('photo-flip-inner');
    inner.classList.toggle('is-flipped');
    // Updates button text
}
```

### Photo URL Resolution
- `photo_url()` from `app/utils.py` wraps `storage.get_photo_url()`
- For R2 mode: `{R2_PUBLIC_URL}/raw_photos/{filename}`
- Back images need to be in R2 `raw_photos/` to serve

## Implementation Plan

1. **Fix upload endpoint**: Ensure file reaches R2 (not just local/staging)
2. **Fix HTMX response**: After upload, swap in the flip-enabled photo view
3. **Add media_group fields**: To photo_index.json schema
4. **Add front/back filter**: To browse page filter bar
5. **Add visual indicators**: Badge on cards with back images, front/back label on photo view
6. **Add Supabase shadow write**: For media_group_id, media_role fields
7. **Test with Chrome**: Full upload + flip + filter workflow

## Files to Touch

- `app/main.py` — upload endpoint fix, browse filter, flip UX
- `app/photo_routes.py` — may have duplicate routes (extracted)
- `core/storage.py` — back image URL resolution
- `data/photo_index.json` — new fields
- `scripts/sql/` — Supabase schema additions
- `tests/` — back image upload tests
