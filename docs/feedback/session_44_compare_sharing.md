# Session 44 Feedback: Compare Faces Redesign + Sharing Design System

**Date:** 2026-02-17
**Source:** Admin review + competitive research + user testing observations

---

## Compare Faces Issues

### CF-01: Upload buried below 46 face thumbnails (CRITICAL)
- Upload section is at bottom of page, below entire face grid
- Most users won't scroll that far — upload is the primary action
- **Fix:** Move upload to top, above the fold

### CF-02: Face grid overwhelming as primary UI
- 46 thumbnails in a grid with no context is disorienting
- Users don't understand the grid's purpose
- **Fix:** Collapse grid into expandable "Search by Person" section

### CF-03: Match labels misleading at lower confidence
- "Identity Matches — Very likely the same person" shown at 57-63%
- Users reported: "If Big Leon is 'very likely' at 57%, what does that mean?"
- Erodes trust in the system
- **Fix:** Calibrate labels: 85%+ Very likely, 70-84% Strong, 50-69% Possible, <50% Unlikely

### CF-04: No clear CTA after finding a match
- After seeing results, user doesn't know what to do next
- No "Share this comparison" or "Name this person" or "Try another"
- **Fix:** Add contextual action buttons below results

### CF-05: Uploaded photos lost after comparison
- One-time use, can't come back to previous comparison
- **Fix:** Auto-save uploads, create permalink for results

### CF-06: No sharing for comparison results
- Can't send someone "look at this comparison"
- **Fix:** /compare/result/{id} pages with OG tags

### CF-07: Two modes not distinguished clearly enough
- Session 42 added numbered sections but still confusing
- **Fix:** Upload-first layout makes the primary mode obvious

---

## Sharing System Issues

### SH-01: Sharing inconsistent across site
- Some pages have share buttons, some don't
- OG tags present on most pages but not all
- share_button() only works with photo_id, not arbitrary URLs

### SH-02: OG tags not using absolute URLs consistently
- Some pages may have relative og:image URLs
- Facebook/WhatsApp won't fetch relative URLs

### SH-03: No unified sharing component
- share_button() exists but is photo-specific
- Need generalized version for any page/entity

---

## Research Sources

### Competitive Face Comparison Tools
- FacePair, ToolPie, ProFaceFinder, VisageHub, Amazon Rekognition
- All follow: two upload slots → Compare button → percentage result
- Upload ALWAYS above the fold
- Privacy messaging common

### Web Sharing Best Practices
- Web Share API for mobile, clipboard for desktop
- OG tags MUST use absolute URLs
- Place share buttons at natural completion points
