# Session 85 Context: Compare Fix — Isaac Cohen Use Case

## Origin
Claude Benatar (community member) sent a group family photo via Facebook Messenger asking
Nolan to "see if you can find a match with this picture" against Isaac Cohen. The current
Compare feature is broken — uploaded photos don't persist to the archive, the result page
shows only a flat list of "Unlikely match" labels without the uploaded photo visible, and
the UX makes it impossible to do what Claude asked: "compare this photo's faces against
a specific known person."

## The Real Use Case (Claude Benatar → Nolan, March 2 2026)
1. Claude has a family photo with 5 people (2 men, 3 women)
2. Isaac Cohen is a confirmed identity in the archive
3. Claude wants to know: "Is Isaac Cohen one of the men in this photo?"
4. Expected flow: Upload photo → Select Isaac Cohen → See per-face match scores
5. Actual flow: Upload photo → See a confusing list of "Unlikely match" results for ALL
   archive faces → No way to search for Isaac Cohen specifically → Photo doesn't save

## Test Image
- Path: `~/Downloads/claude_rhodesli_feedback/isaac_cohen_potential_4c9141db-13ec-4e7c-b9f9-ec65d6f63338.jpeg`
- Contents: Group photo, 5 people (2 men standing, 3 women seated), black & white
- Dimensions: 584x678px, 38KB JPEG

## Current State of Compare (from code review)

### What Works
- Upload + face detection pipeline (SSE streaming, progress indicators)
- Archive embedding comparison (cosine similarity)
- Result storage to comparison_results.json (fixed in Session 83a, AD-198)
- Multi-face selector (when >1 face detected, user picks which to compare)
- Pair compare (/compare/pair) for two-photo side-by-side
- Auto-queue to pending_uploads.json for admin review (AD-182)
- Calibrated confidence scoring via SimilarityCalibrator

### What's Broken / Missing
1. **Uploaded photo NOT shown on result page** — only in OG tags, not rendered in body
2. **No way to compare upload against a SPECIFIC person** — shows matches against ALL
   archive faces, can't filter to "show me how this face matches Isaac Cohen"
3. **Photos don't save to Rhodesli archive** — uploads go to `uploads/compare/` directory,
   not to main photo index. "Does NOT SAVE to Rhodesli" per Nolan.
4. **Result page is a flat list** — no uploaded photo visible, no face selection,
   no context about which face in a multi-face photo was compared
5. **No Find Similar context** — can't see how the compare score ranks vs. Isaac Cohen's
   existing similar faces from the archive
6. **"64 identified people" count** is stale (now 65 per admin sidebar)
7. **All matches show "Unlikely match"** — calibration may be off, or the threshold
   tiers need adjustment for the compare context

### Key Code Locations
- `/compare` page: `app/main.py:16161`
- Upload handler: `app/main.py:17009` (`POST /api/compare/upload`)
- Result page: `app/main.py:17846` (`GET /compare/result/{result_id}`)
- Save upload: `app/main.py:16927` (`_save_compare_upload()`)
- Save result: `app/main.py:17826` (`_save_comparison_result()`)
- Queue for admin: `app/main.py:16898` (`_queue_compare_upload_for_review()`)
- Tests: `tests/test_compare.py` (25 tests)
- Compare pair: `app/main.py:18246` (`GET /compare/pair`)

### Relevant Decisions
- AD-117: Three-tier compare architecture
- AD-182: Auto-queue uploads to admin review
- AD-187: Async batch processing (no real-time GPU)
- AD-198: SSE handler now saves results (Session 83a fix)
- PRD-016: Compare Faces Redesign (IN PROGRESS)
- PRD-021: Multi-Photo Compare (IN PROGRESS)

## Screenshots (from Nolan, March 2 2026)
1. **Messenger conversation**: Claude Benatar's original request
2. **/compare page**: Upload form with "Search Archive" button, person search below
3. **/compare uploading**: Photo selected, SSE progress stages visible
4. **/compare/result/28f18514d9d3 (top)**: Flat list, all "Unlikely match", no uploaded photo
5. **/compare/result/28f18514d9d3 (bottom)**: "Unknown" entries with broken crops, share button, response form
6. **Isaac Cohen's Find Similar**: Admin view shows Dist 1.22 matches (all "Low"), good reference for comparison

## Key Insight from Screenshots
Isaac Cohen's Find Similar panel (screenshot 6) shows his nearest archive neighbors at
distance 1.22 with "Low" confidence. If the uploaded photo truly contains Isaac Cohen,
the compare result should show a LOWER distance (stronger match) than 1.22 for at least
one face. But the current compare result page (screenshot 4) shows all "Unlikely match"
without distances — making it impossible to tell if any face actually matched well.

## Design Direction
The compare page should support two primary flows:
1. **"Who is in this photo?"** — Upload photo, compare ALL faces against archive (current flow, needs polish)
2. **"Is [Person X] in this photo?"** — Upload photo, select a known person, see per-face scores ranked against that person (NEW)

Flow 2 is what Claude Benatar actually wanted. It should:
- Show the uploaded photo with face bounding boxes
- Show the selected person's crop for reference
- Show per-face match scores against that specific person
- Show how those scores compare to the person's existing top matches (Find Similar context)
- Allow saving the photo to the archive if admin approves

## Predecessor
- Session 84: Unified face cards + Find Similar panel (DD-006)
- Session 83a: Compare result storage fix (AD-198), Display Name (AD-196)
- Session 77: Compare rebuild with pair compare, auto-queue (AD-181/182)
