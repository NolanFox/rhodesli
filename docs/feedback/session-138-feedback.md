# Session 138 Feedback

### FB-001: Missing thumbnails for Person 174 and Person 196 in neighbor cards
- **Severity:** P2
- **Context:** On Fox Family Archive focus view (/c/fox-family/?section=to_review), looking at Unidentified Person 4029's Similar Identities. Person 174 and Person 196 show gray placeholder circles instead of face crop thumbnails. However, the full photos load correctly in the Compare Faces modal. This means the face crop files are missing or the crop URL resolution is failing for these specific identities, but the photo-level images work fine.
- **Screenshot:** User provided 3 screenshots showing the issue
- **Root cause:** TBD — likely missing crop files on R2 for these identities, or resolve_face_image_url returning None for their face IDs
- **Fix:** IN PROGRESS

### FB-002: No direct navigation to specific identity from merge result
- **Severity:** P1
- **Context:** After merging in focus mode, there's no way to navigate to the merged identity to confirm it. User had to manually paste identity ID (a56ab152-7b3b-46c5-a982-f5555a439150) into the URL. The merged identity disappears from the triage queue but isn't findable via normal navigation.
- **Screenshot:** User showed browse view with no way to find the specific identity
- **Root cause:** Focus mode merge advances to next identity but doesn't offer a link to the merged result
- **Fix:** IN PROGRESS

### FB-003: Merge in focus mode should auto-confirm
- **Severity:** P1
- **Context:** When user merges identities in focus mode, the merge happens but the result is NOT automatically confirmed. This creates orphaned unconfirmed identities that the user can't easily find or confirm. User wants: merge → auto-confirm → advance to next.
- **Root cause:** merge_identities() doesn't trigger confirmation. By design, but bad UX.
- **Fix:** Needs PRD — this is a workflow change (see Lesson feedback_confirm_merge_needs_prd.md). Log to BACKLOG.

### FB-004: Confirm vs Identify conceptual confusion
- **Severity:** P1 (strategic)
- **Context:** User raised fundamental question: what does "confirm" mean? Is it "I know who this person is" or "this is a real person worth tracking"? Current system conflates two distinct actions: (1) confirming a cluster is one person, and (2) identifying who that person is. User wants to be able to confirm an unidentified person as real, then later identify them. This needs a PRD to redesign the confirmation/identification workflow.
- **Root cause:** CONFIRMED state conflates cluster validation with name identification
- **Fix:** BACKLOG — needs PRD for confirm vs identify separation

### FB-005: Need filtered view for unidentified confirmed people
- **Severity:** P2
- **Context:** User wants to filter confirmed people by "has name" vs "unidentified" so they can go back and identify confirmed-but-unnamed people. Currently no way to see just the unnamed confirmed identities.
- **Root cause:** No filter exists for this use case
- **Fix:** BACKLOG

### FB-006: Cannot confirm Person 3084 — Confirm button disabled
- **Severity:** P0
- **Context:** On person page for a56ab152-7b3b-46c5-a982-f5555a439150 (Unidentified Person 3084), the Confirm button is grayed out and disabled. Person has 3 photos, state is INBOX. User wants to confirm this as a real person even though unidentified. The confirm button is disabled because the person is unidentified — but user's workflow is: confirm first, identify later.
- **Screenshot:** User showed person page with grayed-out confirm button
- **Root cause:** FB-009 from Session 120 intentionally disabled confirm for unidentified persons. But this blocks the user's intended workflow of confirming clusters without naming them first.
- **Fix:** IN PROGRESS — need to re-enable confirm for unidentified persons, at least on person page

### FB-007: Cannot choose hero face for identity card
- **Severity:** P3
- **Context:** Unlike Google Photos, there's no way to set which face crop is the "hero" thumbnail on identity cards. The system uses get_best_face_id() which picks by quality score, but the user may prefer a different face.
- **Root cause:** No UI for choosing primary face
- **Fix:** BACKLOG — nice-to-have feature

### FB-008: Bulk merge (Merge Selected) fails in focus mode
- **Severity:** P1
- **Context:** When selecting multiple similar identities via checkboxes and clicking "Merge Selected" in focus mode, it gives an error. Only single merge works. User was trying to merge multiple Albert Fox faces. This has been reported before.
- **Root cause:** TBD — need to investigate bulk merge endpoint behavior in focus mode
- **Fix:** BACKLOG — needs investigation

### FB-009: Confirm button still grayed out on production
- **Severity:** P0 (blocking)
- **Context:** The confirm button fix (FB-006) has not deployed yet. User is seeing the old disabled confirm button on production. Need to push and deploy.
- **Root cause:** Code not deployed yet
- **Fix:** IN PROGRESS — pushing now

### FB-010: After merge in focus mode, doesn't advance to next person
- **Severity:** P1
- **Context:** After merging in focus mode, shows "Merged 1 identities (1 faces)" success message but stays on the same identity. Doesn't auto-advance to next person. User has to refresh the page. Confirm button still grayed out (pre-deploy). Related to FB-003.
- **Root cause:** Focus mode merge handler returns success toast but doesn't trigger navigation to next identity
- **Fix:** BACKLOG — same root cause as FB-003

### FB-011: Person 163 has no face crop — missing crops pattern
- **Severity:** P1
- **Context:** Same issue as FB-001. Person 163 shows gray placeholder instead of face crop in neighbor cards. Investigation shows 750 out of 1000 faces in photo_faces table have NULL bbox and quality — these are likely all missing crop files on R2. This is a systemic data issue affecting many Rhodes community identities.
- **Root cause:** Face records were created in photo_faces during Supabase migration but crop image files were never generated/uploaded to R2. The original pipeline creates crops locally but they were never synced to R2 for these faces.
- **Fix:** Needs pipeline run to regenerate and upload crops for all affected faces

### FB-012: "Load More" doesn't work with "Same community only" filter
- **Severity:** P2
- **Context:** On person page Similar Identities panel, selecting "Same community only" filter works for initial results but the "Load More" button doesn't preserve the community filter. Previously fixed in Session 135c (FB-014) for the focus mode neighbors sidebar, but person page may use a different code path.
- **Root cause:** Load More URL on person page may not include community_filter parameter
- **Fix:** IN PROGRESS — need to check person page neighbors code path