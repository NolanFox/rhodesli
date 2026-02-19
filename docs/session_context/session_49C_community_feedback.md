# Session 49C — First Community Sharing Feedback

## What Happened
Rhodesli match links were shared in the Jews of Rhodes Facebook group
(~2,000 members) on Feb 18, 2026. This was the first real community
test of the sharing and identification flows.

## Engagement Results (22 hours)
- 17 comments, 108 post reach
- 3 family members actively identifying people
- 8 people identified by name in a single comment (Carey Franco)
- 2 face matches confirmed by community members
- Multiple follow-up questions about other faces in photos

## Bugs Found During Live Use
1. **P0: Photo page 404 for community/inbox photos**
   - URL: /photo/inbox_community-batch-20260214_7_howie_franco_collection_...
   - Photos ingested from community submissions exist in the identify
     flow but their /photo/{id} page returns 404
   - Every "View Photo" link from identify flow is broken for these photos
   - Claude Benatar (community member) hit this trying to view the photo

2. **P0: Compare upload silent failure**
   - /compare page accepts file drop but nothing happens
   - No error message, no loading state, no feedback
   - Nolan tried to upload a photo of Howie's mother for comparison
     during a live conversation — complete failure with no indication
   - Upload is also supposed to save the photo for later processing

3. **P1: Version shows v0.0.0 in admin footer**
   - Session 47 was supposed to fix this
   - Public pages may show correct version but admin view shows v0.0.0

4. **P1: Collection name truncation still present**
   - "Jews of Rhodes: Family Me..." appears under photo thumbnails
     on the identify person page
   - Session 49 fixed this on /photos stat cards but NOT on identify
     page photo thumbnails or other locations

5. **P2: No quick-identify from photo view**
   - When viewing a photo with 11 "Unknown" faces, there's no way to
     click a face and type a name inline
   - User must navigate to each face's identify page individually
   - This is a friction problem, not a bug — defer to future session
   - BUT: note that Carey Franco just gave us 8 names for faces in one
     photo. The current workflow makes entering those names very tedious.

## Product Insights from Community Response
- The "Are these the same person?" sharing page works well — clean,
  clear, community members understood it immediately
- Face match links generated the most engagement (people love
  confirming "yes that's my dad!")
- Community members naturally want to identify ALL faces in a photo,
  not just the one being asked about
- The sharing → identification → more sharing loop works in theory
  but bugs break it at critical moments
- Nancy Gormezano (from original thread) is the power user archetype:
  she does manually what Rhodesli automates
