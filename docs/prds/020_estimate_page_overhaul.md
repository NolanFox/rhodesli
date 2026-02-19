# PRD-020: Estimate Page Overhaul

**Status:** Draft
**Created:** 2026-02-19 (Session 50)
**Related:** PRD-018 (Year Estimation Tool V1), AD-092-096 (date estimation)

## Problem Statement

The /estimate page (shipped in Session 46 as a tab on /compare) has significant UX issues observed during community sharing:

1. Every photo shows "0 faces" under thumbnails (data not connected)
2. Page loads all 271 photos at once (extremely slow)
3. No photo upload capability (core missing feature for a "tool")
4. "No detailed evidence available" for most photos (evidence display broken)
5. Only accessible through Compare tab (no standalone navigation)
6. No way to correct or update AI estimates
7. No search, filter, or pagination

## Vision

Estimate = standalone "Photo Date Detective" tool. Upload a photo, get a date with evidence. The evidence display ("1920s Marcel wave hairstyle, hand-tinted coloring typical of Rhodes studios") is the wow factor that makes people share the tool.

## Requirements

### P0 — This Session (Session 50)

1. **Fix face count display** — Show actual face count from photo data, not hardcoded "0 faces"
2. **Paginate photo grid** — 24 photos per page with "Load More" button (HTMX)
3. **Standalone /estimate route** — Add "Estimate" to top nav as its own item
4. **Upload a photo** — Drag-and-drop zone, JPG/PNG <10MB
   - Show existing date_labels.json data if available
   - If no data: "No AI estimate yet — check back soon"
   - Loading state while processing
5. **Improve results display** — Prominent estimate with evidence categories

### P1 — Future Session

6. Search/filter by collection, date range
7. **Date correction flow** — "Know the date?" → text input → saves to pending_date_corrections.json → admin approval (Gatekeeper pattern)
8. Deep CTAs: "View in archive", "Help identify people", "Explore this era"

### P2 — Future

9. Separate nav items for Estimate and Compare (currently tabs → should be distinct pages)
10. Auto-run Gemini on uploaded photos when API key is configured

## Key Design Insight

The "How we estimated this" evidence display is the primary differentiator. When Gemini identifies "Marcel wave hairstyle typical of 1920s Rhodes studios, hand-tinted coloring, sepia-toned cabinet card format" — that's what makes people share. Evidence must be prominently displayed, never hidden.

## Technical Notes

- Face count source: `len(pm.get("face_ids", []))` from `_photo_cache`
- Date labels: `data/date_labels.json` loaded by `_load_date_labels()`
- Upload pattern: mirror Compare's upload with `_save_compare_upload()` adapted for estimate
- Pagination: HTMX `hx-get` with page offset parameter
- Evidence: from `date_labels.json` → `subject_ages`, `scene_analysis`, `estimated_year`

## Out of Scope

- Gemini API calls (documentation/config only this session)
- PRD-015 face alignment implementation
- Batch upload processing
