# FB-170: Claude Benatar Compare + Upload Failure (2026-03-15)

**Reporter:** Nolan (observing Claude Benatar's Messenger conversation)
**Severity:** P0 — Contributor cannot complete the core use case
**Related:** FB-168, UPLOAD-002, Lesson 135, Lesson 138

## What Claude Benatar Was Trying to Do

Claude Benatar had two photos of men from the Rhodes community and wanted to know if they were the same person. He sent them via Facebook Messenger asking **"Hi Nolan, what do you think... Same person?"**

The person of interest: **Robert Mattatia** — born Cairo, July 22, 1914, son of Marc Baruch Mattatia and Miram Baruch (Baruk), married Rebecca Cohen (1918-2010), murdered in Bukavu in 1967.

### Photos Sent

| File | Dimensions | Type | Content |
|------|-----------|------|---------|
| `1ab8addd-*.jpeg` | 1600x1200 | Full original scan | Group of men in colonial Africa setting (appears to be Congo/Bukavu) |
| `efede0a7-*.jpeg` | 557x399 | Cropped or low-res | Family group photo, outdoor setting |

One additional image visible in Messenger was labeled **"enhanced with Gemini"** — Claude Benatar used Google's AI enhancement on a face crop before sending.

### What He Should Have Done (Ideal Flow)

1. Go to `/tools/compare` (or `/compare`)
2. Upload the two original photos
3. See face detection results + similarity scores
4. Photos automatically saved to the archive for future reference
5. If a match is found, tag the identity

### What Actually Happened

1. **Tried Compare tool** — couldn't figure out how to use it (UX failure)
2. **Tried uploading photos** — upload went through but:
   - 2 uploads showed as "anonymous" with no thumbnails (attribution lost)
   - 1 upload showed with `poisson1957@hotmail.com` (his email) with thumbnail
   - After admin approved the photo with thumbnail, "View photo" linked to dead URL: `rhodesli.nolanandrewfox.com/photo/inbox_efea638c_0_unknown_1` → 404
3. **Gave up and sent via Messenger** — the fallback that shouldn't be necessary

## Root Cause Analysis

### Compare Tool UX Gap
The Compare tool exists at `/tools/compare` but:
- When logged in, uploaded photos should auto-save to archive (Nolan's stated expectation)
- The workflow is not obvious to a first-time contributor
- No guidance on what to upload or what results mean
- Claude Benatar defaulted to Messenger because the tool was not self-explanatory

### Upload Pipeline Regression (AGAIN)
This is the **6th time** uploads have broken:
- Session 65c: subprocess OOM (AD-161)
- Session 66b: cache staleness + R2 race (AD-165)
- Session 96e-cont4: community tagging + Postgres sync (UPLOAD-002)
- Session 100d: staging thumbnails, batch approve
- Session 103: anonymous attribution, dead link after approval

**Pattern:** Every few sessions, uploads break in a new way. The pipeline has too many moving parts (staging → R2 → Postgres → face detection → community tagging → cache invalidation) and no end-to-end integration test that catches regressions.

### Contributor Attribution Lost
Two of three uploads showed as "anonymous" — the user's session/auth was not properly associated with the upload. This may be related to the Compare Upload flow having a different auth path than the main Upload page.

## Specific Bugs

### BUG-1: Approved photo 404 (inbox_efea638c_0_unknown_1)
- Photo ID suggests it was created but never properly registered in photo_index/Postgres
- R2 upload may have failed silently
- Face detection may have failed silently
- The approval flow created a photo record with an ID but no actual photo backing it

### BUG-2: Compare Upload loses user attribution
- `Source: Compare Upload` but uploader is "anonymous"
- Compare upload endpoint may not pass session/auth to the staging pipeline

### BUG-3: No thumbnails for pending uploads
- 2 of 3 pending uploads show filename text only, no preview
- Staging thumbnails may not have been generated, or R2 upload of staging failed

## Nolan's Feedback (Paraphrased)

> "This breaks everything about how contributor use of the app is supposed to work. There is no clear UX for him to do something basic. If you use the compare tool while logged in it should save the photo automatically for you. The ideal situation is he would go to compare and send the two original photos which would then be saved in rhodesli for the future. Maybe we need to think about removing approvals for upload for contributors since this keeps breaking."

## Action Items

1. **P0**: Fix upload pipeline — dead links after approval
2. **P0**: Fix Compare Upload attribution (anonymous → actual user)
3. **P1**: Consider removing approval gate for contributor uploads (auto-approve for logged-in users)
4. **P1**: Compare tool UX — make the "upload two photos, see if same person" flow obvious and self-explanatory
5. **P1**: Compare uploads should auto-save to archive when logged in
6. **P2**: End-to-end upload integration test (staging → R2 → Postgres → photo page loads)

## Photos Preserved

Original photos saved to: `~/Downloads/rhodesli_claude_benatar_compare/`
- These should be ingested into the Rhodes archive with proper attribution to Claude Benatar
- Subject: Robert Mattatia (Congo/Bukavu era, 1950s-1960s based on context)

## Breadcrumbs
- BACKLOG: UPLOAD-003, UX-077, UX-078
- Related: Lesson 135 (notification infrastructure never called), Lesson 136 (fire-and-forget Supabase syncs)
- AD-224 (reranker review — same session)
- Memory: `feedback_upload_ux_issues.md` (updated)
