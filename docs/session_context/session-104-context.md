# Session 104 Context — Contributor UX Fix + Claude Benatar Photos

**Predecessor:** Session 103 (`docs/session_context/session-103-context.md`)
**Date:** 2026-03-15
**Trigger:** Real-world contributor failure observed via Facebook Messenger

## Background

Claude Benatar (poisson1957@hotmail.com) is the primary external contributor to Rhodesli. On 2026-03-15, he messaged Nolan via Facebook Messenger with two photos asking **"Hi Nolan, what do you think... Same person?"**

The person of interest: **Robert Mattatia** — born Cairo, July 22, 1914, son of Marc Baruch Mattatia and Miram Baruch (Baruk), married Rebecca Cohen (1918-2010), murdered in Bukavu in 1967.

### What Claude Benatar Did

1. **Tried the Compare tool** at `/tools/compare` — couldn't figure out how to use it
2. **Tried uploading photos** — this partially worked but:
   - 2 uploads showed as "anonymous" (attribution lost)
   - 1 upload showed with his email but after admin approved, "View photo" → 404 dead link
3. **Gave up and sent via Messenger** — sent photos + one "enhanced with Gemini" crop

### What He Should Have Done (Ideal Flow)

1. Go to `/tools/compare`
2. Upload two original photos
3. See face detection + similarity scores
4. Photos auto-saved to archive (when logged in)
5. Nolan gets a shareable Compare result link to send back

### What's Broken

1. **Upload pipeline** — 404 after approval (`/photo/inbox_efea638c_0_unknown_1`). 6th regression.
2. **Compare Upload attribution** — shows "anonymous" instead of user's email
3. **No thumbnails** for 2/3 pending uploads
4. **Compare UX** — not self-explanatory for contributors
5. **No auto-save** — Compare uploads by logged-in users should persist to archive

### Photos Available

Downloaded to `~/Downloads/rhodesli_claude_benatar_compare/`:
- `1ab8addd-*.jpeg` — 1600x1200, group of men in colonial Africa (Congo/Bukavu era)
- `efede0a7-*.jpeg` — 557x399, family group photo

These need to be:
1. Ingested into the Rhodes archive with attribution to Claude Benatar
2. Processed through ML (face detection, embedding generation)
3. Compared via the Compare tool
4. Result shareable via a single link Nolan can send to Claude Benatar

### Nolan's Key Feedback

- "This breaks everything about how contributor use of the app is supposed to work"
- "There is no clear UX for him to do something basic"
- "If you use the compare tool while logged in it should save the photo automatically"
- "Maybe we need to think about removing approvals for upload for contributors since this keeps breaking"
- "At the end of this I should be able to send him one link comparing the two faces from the original photos which are uploaded into Rhodesli and processed fully through ML"

## Deliverables

1. **Answer for Claude Benatar:** A shareable Compare link showing face similarity scores between the two photos. Also a broader analysis — what other faces are in each photo, do any match known identities in the archive? This gives context beyond just "these two faces."
2. **Fix the upload pipeline** so this never happens again (404, attribution, thumbnails)
3. **Clear contributor path:** After fixes, Claude Benatar should be able to use Compare himself next time — upload two photos, get results, photos saved to archive
4. **Message for Nolan to send:** Include the link, what the tool found, and instructions for next time

## Compare + Community Scoping Design Questions

The Compare tool has an unresolved community relationship:

| Scenario | Current Behavior | Ideal Behavior |
|----------|-----------------|----------------|
| Both photos belong to Rhodes | Compare works, photos in Rhodes archive | Same — auto-tag Rhodes |
| One photo is Rhodes, one is external | Compare works but external photo has no community | External photo saved but untagged, or tagged to user's active community |
| Neither photo is from any community | Compare works (standalone tool) | Photos saved but untagged — user can add to community later |
| Person appears in two communities | Compare shows faces from both | Cross-community badge, results show both archives |
| User is logged into a community | ? | Compare defaults to that community context for matching + saving |

**Key question:** Should there be a **community-scoped Compare** at `/c/rhodes/compare` that:
- Auto-tags uploaded photos to that community
- Searches only that community's identities for matches
- Shows "also found in [other community]" for cross-community hits

vs. the current **standalone Compare** at `/tools/compare` that:
- Is community-agnostic
- Searches all identities across all communities
- Doesn't auto-tag to any community

**Nolan's instinct:** "Maybe there is a dedicated compare link for rhodesli community comparison that acts one way." This suggests the community-scoped version is more useful for contributors.

## Scope

### In Scope
1. Reproduce Claude Benatar's experience step-by-step (document what he saw)
2. Fix upload pipeline: 404 after approval, anonymous attribution, missing thumbnails
3. Fix Compare Upload to auto-save for logged-in users
4. Ingest the two Robert Mattatia photos into archive
5. Process through ML — face detection on BOTH photos, find all faces, check against entire archive
6. Produce a shareable Compare link with per-face similarity + broader context (other faces in photos)
7. Evaluate removing approval gate for contributor uploads
8. Design decision on community-scoped Compare (document as AD, implement if <1h)

### Out of Scope
- Full Compare tool redesign (separate PRD)
- New contributor onboarding flow (WORKSPACE-001+)
- Speed-run / triage work

## Key Files

| File | Purpose |
|------|---------|
| `app/upload_routes.py` | Upload page + processing |
| `app/compare_routes.py` | Compare tool routes |
| `app/admin_routes.py` | Pending uploads approval |
| `core/ingest_inbox.py` | Face detection pipeline |
| `scripts/cluster_new_faces.py` | Proposal generation |
| `docs/user_feedback/FB-170_claude_benatar_compare_failure.md` | Full interaction doc |

## Related Decisions
- AD-161: Upload subprocess OOM fix
- AD-165: Upload cache staleness fix
- UPLOAD-002: Community tagging + Postgres sync fix
- Lesson 135: Notification infrastructure never called
- Lesson 136: Fire-and-forget Supabase syncs create invisible data loss

## Risk Assessment
- **Upload fix is P0** — contributor experience is existential for the project
- **Upload has broken 6 times** — need structural fix, not another patch
- **Removing approval gate** has moderation implications but acceptable for known contributors
