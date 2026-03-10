# Session 96e User Feedback — Critical Issues

**Date:** 2026-03-10
**Source:** Nolan direct feedback with screenshots
**Severity:** P0 — Core app functionality broken

## Issues Identified

### 1. Upload Review is NOT community-scoped
- URL `/admin/upload-review` shows GLOBAL data (2115 faces to 70 identities)
- Should be `/c/fox-family/admin/upload-review` showing only Fox Family data
- The global page is completely wrong for community context

### 2. Upload Review face cards are inconsistent with rest of app
- Cards show: thumbnail + confidence badge + "From: Unidentified Person XXXX" + "View photo" + Confirm/Reject
- Should match the face card design used in New Matches (Compare, Merge, Not Same, Share, community labels)
- No way to click through to person page, photo, or identity
- No indication which photos are from which community

### 3. Proposals are mostly garbage — 389 matches for Roland Fox at Low (1.30) confidence
- `cluster_new_faces.py --threshold 1.3` generated matches up to distance 1.30
- Distance 1.30 = "Low" confidence — these are NOT useful matches
- Should only show high-confidence matches (< 0.85 or < 0.95 at most)
- "231 faces matched" for Big Leon Capeluto is also wrong at these volumes

### 4. New Matches shows NO clustering
- Screenshot: `/c/fox-family/?section=to_review&view=browse`
- Every single card is "Unidentified Person ..." with 1 face
- Grouping ran (813 merges reducing 2009 → 1196) but no visible clustering in UI
- "This is the most basic and fundamental thing this app is supposed to do"
- Need to verify: did grouping actually produce multi-face identities on production?

### 5. No PRD/SDD for this feature was followed
- PRD-037 exists at `docs/prds/037_post_upload_intelligence.md`
- Acceptance criteria were not verified
- Design was not consulted before implementation

## User's Expected Experience
1. Upload Review should be community-specific (accessed from sidebar)
2. Top section: Cluster matches — faces the ML grouped as same person, with cross-community support
3. Face cards must be consistent with rest of app (Compare, Merge, links to person/photo)
4. Clear which photos are from which community
5. New Matches should show CLUSTERED faces (multiple faces per person, not 1497 individual cards)
6. The grouping pipeline must actually work — faces of the same person should be grouped

## Root Cause Analysis Needed
- Why did grouping produce 813 merges but no multi-face identities are visible?
- Why were Low (1.30) confidence proposals generated and shown?
- Why wasn't the PRD consulted?
- Why wasn't upload-review browser-verified from the community context?
