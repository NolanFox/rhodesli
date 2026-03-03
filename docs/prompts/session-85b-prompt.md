# Session 85b: Compare Navigation + PRD-025 Gap Closure

**Predecessor:** Session 85 (v0.87.0)
**Context:** docs/session_context/session-85b-context.md
**PRD:** docs/prds/025_compare_functional_rebuild.md
**Test case:** Compare photo f86fdef4cd4051da against Isaac Cohen

## Goal
Close all gaps between PRD-025 and what session 85 delivered. Add archive-to-compare
navigation so existing photos/people can be compared without re-uploading. Produce a
shareable link for Claude Benatar.

## Phase 0: Orient (3 min)
- Set `.claude/current_session.txt` to `85b`
- Read: `tasks/lessons.md`, PRD-025, session 85 assessment
- Confirm session 85 deployment is live
- Create session log: `docs/session_logs/session-85b-log.md`

## Phase 1: Archive Photo → Compare (20 min)
**Goal:** Enable comparing an existing archive photo against a specific person.

### 1a. New route: GET /api/compare/from-photo?photo_id=X&identity_id=Y
- Takes an existing photo_id and identity_id
- Loads the photo's faces from photo_index/embeddings
- Computes per-face distances against the identity's anchors
- Returns the same result format as POST /api/compare/vs-person
- Saves result to comparison_results so it's shareable

### 1b. Compare page: archive photo selector
- On /compare, add a section "Or select an existing photo from the archive"
- Search by photo source/collection, or browse thumbnails
- Selecting a photo loads its faces (same as upload result)
- Then user can search a person and compare

### 1c. Direct URL pattern
- Support `/compare?photo_id=X&person_id=Y` — auto-runs comparison on page load
- Support `/compare?photo_id=X` — shows photo's faces, user searches person

### Tests
- test_compare_from_photo_returns_scores
- test_compare_from_photo_invalid_photo_404
- test_compare_from_photo_invalid_person_404
- test_compare_direct_url_with_photo_and_person

## Phase 2: Navigation Links (15 min)
**Goal:** Add "Compare" actions to person and photo pages.

### 2a. Photo page (/photo/{photo_id})
- Add "Compare faces in this photo" button/link
- Links to `/compare?photo_id={photo_id}`
- Shows on all photo pages (admin and public)

### 2b. Person page (/person/{identity_id})
- Add "Compare against a photo" button/link
- Links to `/compare?person_id={identity_id}` — pre-fills the person search
- Shows for CONFIRMED identities

### 2c. From Find Similar / Neighbors sidebar
- Add "Compare with uploaded photo" action
- Links to `/compare?person_id={identity_id}`

### Tests
- test_photo_page_has_compare_link
- test_person_page_has_compare_link
- test_compare_page_prefills_person_from_query_param

## Phase 3: PRD-025 Gap Closure (15 min)
**Goal:** Implement missing PRD-025 acceptance criteria.

### 3a. Reference person context
- On vs-person result, show: "Isaac Cohen's closest archive match is [Name] at
  distance [X] ([Tier]). Your best match (Face N) scores [Y]."
- Fetch from neighbors/similarity data for the reference person
- Display prominently on result page

### 3b. Merge/Reject/Not Same actions
- Add admin-only merge/reject buttons on compare result page
- For each face match: [Merge] [Not Same]
- Merge: calls same endpoint as neighbors_sidebar merge
- Not Same: calls same endpoint as neighbors_sidebar reject
- HTMX swap to update the row after action

### Tests
- test_compare_result_shows_reference_context
- test_compare_result_merge_action
- test_compare_result_not_same_action

## Phase 4: Isaac Cohen End-to-End + Shareable Link (10 min)
**Goal:** Verify the full flow and produce Claude Benatar's link.

### 4a. Find the photo and person
- Identify photo f86fdef4cd4051da in the archive
- Identify Isaac Cohen's identity_id
- Generate: `/compare?photo_id=f86fdef4cd4051da&person_id={isaac_id}`

### 4b. Browser verification
- Open the direct comparison URL in Chrome
- Verify: photo loads, faces shown, Isaac Cohen selected, per-face scores displayed
- Verify: context line shows Isaac Cohen's existing archive match distance
- Verify: shareable link works (open in new tab)
- Take screenshots: `docs/screenshots/session-85b/`

### 4c. Produce shareable link
- The /compare/result/{id} URL from step 4b is the shareable link
- Verify it works without authentication (incognito)
- Record the URL in the session log

## Phase 5: Session Docs (5 min)
- Assessment: `docs/assessments/session-85b-assessment.md`
- Update CHANGELOG.md, ROADMAP.md
- Update PRD-025 acceptance criteria (check boxes)
- Update ALGORITHMIC_DECISIONS.md if any new decisions
- Update DESIGN_DECISIONS.md if any new decisions

## Verification Gate
- [ ] Photo f86fdef4cd4051da can be compared to Isaac Cohen via URL
- [ ] Person page has "Compare" link
- [ ] Photo page has "Compare" link
- [ ] Reference person context shown on result page
- [ ] Merge/Not Same actions work on compare result
- [ ] Shareable link works in incognito
- [ ] All new tests pass
- [ ] Full test suite passes (make test-fast)
- [ ] Browser screenshots captured

## Deliverable for Claude Benatar
A shareable URL showing: Isaac Cohen compared to each face in the family photo,
with confidence scores, face crops, and a "Do you recognize anyone?" prompt.
