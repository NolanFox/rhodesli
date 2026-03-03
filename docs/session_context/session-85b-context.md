# Session 85b Context: Compare Navigation + PRD Gap Closure

## Origin
Nolan reviewed session 85 output and identified gaps against PRD-025 spec. Additionally,
the user wants the ability to compare existing archive photos/people without re-uploading,
and navigation from person/photo pages into compare.

## Predecessor
- Session 85 (v0.87.0): Unified upload pipeline, vs-person comparison, confidence bars
- Assessment: docs/assessments/session-85-assessment.md

## Nolan Feedback (2026-03-03, post-session 85)

### Feedback 1: Archive-to-Compare Navigation
"Is there already a URL to compare photo /photo/f86fdef4cd4051da to Isaac Cohen?"
The answer is NO — the vs-person flow requires an upload job_id. Existing archive photos
cannot be compared against a specific person without re-uploading. This is a critical gap.

### Feedback 2: Person/Photo → Compare Navigation
"There should be a simple way to get from a person or photo page to compare."
Currently only generic /compare links exist. No contextual "compare this face" or
"compare this person" actions from person/photo pages.

### Feedback 3: Archive Photo Comparison Without Re-Upload
"From compare you should be able to either upload or call up any person or photo in
the archive already (or upload one or more photos)."
The compare page should support selecting existing archive photos AND uploading new ones.

### Feedback 4: Compare One Person to All Faces in a Photo
"You should be able to compare one person to all people in a photo to see if there
are any probable matches."
Example: Select Isaac Cohen → Select photo f86fdef4cd4051da → See per-face scores.

### Feedback 5: Shareable Output for Claude Benatar
One deliverable should be a shareable link for Claude Benatar to view.

## Gap Analysis: PRD-025 vs Session 85 Delivery

### DELIVERED in Session 85
- [x] Unified upload pipeline (compare uses same process_directory as Upload)
- [x] Person search autocomplete (GET /api/compare/search-person)
- [x] Per-face match scores against selected person (POST /api/compare/vs-person)
- [x] Confidence bars with dual encoding (color + percentage + tier label)
- [x] Person/photo links on result page (partial)
- [x] Shareable result URLs (/compare/result/{id})
- [x] HTMX polling replaces SSE interceptor
- [x] 22 compare tests

### NOT DELIVERED (PRD-025 Acceptance Criteria)
1. **Context: reference person's existing top archive matches** — PRD specifies
   "Isaac Cohen's closest archive match is ~1.22" shown on result page. Not implemented.
2. **Isaac Cohen end-to-end test** — Not verified in production browser
3. **Merge/Reject/Not Same actions** — PRD section "Navigation and Actions" specifies
   these. Not implemented on compare result page.
4. **Mobile responsive at 375px** — Not explicitly verified

### NOT SPECIFIED IN PRD-025 BUT REQUESTED BY NOLAN
5. **Archive photo → vs-person comparison** — Compare existing archive photo to a person
   without re-uploading. NEW FEATURE.
6. **Navigation links from person/photo pages** — "Compare this face" action buttons.
   NEW FEATURE.
7. **Select archive photo from compare page** — Browse/search archive photos from within
   compare flow. NEW FEATURE.

## Key Architectural Decision
The vs-person endpoint currently requires a `job_id` from an upload. To support archive
photos, we need either:
- Option A: Create a synthetic job_id from an existing photo_id (reuse same endpoint)
- Option B: New endpoint POST /api/compare/photo-vs-person (photo_id, identity_id)
Option A is cleaner — create a virtual "job" from existing photo data.

## Test Image Reference
- Photo URL: https://rhodesli.nolanandrewfox.com/photo/f86fdef4cd4051da
- This is likely the Isaac Cohen potential photo uploaded in session 85
- Isaac Cohen identity: search Supabase for confirmed identity named "Isaac Cohen"
