# Rhodesli Manual Test Checklist

Run this checklist after any significant code change.

## Core Flows

### 1. Upload Photo
- [ ] Upload single photo → face detected
- [ ] Upload multiple photos → faces detected
- [ ] Identity created in inbox
- [ ] Progress indicator shows filename correctly

### 2. View Identity Card
- [ ] Card renders with photo thumbnail
- [ ] Face count is accurate
- [ ] Name displays correctly (not "Identity <UUID>")
- [ ] Click "View Photo" → modal opens correctly

### 3. View Photo Modal
- [ ] Photo displays
- [ ] Faces are highlighted/clickable
- [ ] Clicking a face closes modal and scrolls to that identity
- [ ] Modal closes cleanly (X button or click outside)

### 4. Find Similar
- [ ] Returns results
- [ ] Results show photos (not blank)
- [ ] Results are clickable
- [ ] Confidence levels display (low/medium/high)
- [ ] Clicking result navigates to correct identity

### 5. Merge Identities
- [ ] Merge completes without error
- [ ] Faces move to target identity
- [ ] Face count updates correctly on target
- [ ] Source identity is removed from DOM

### 6. Confirm Identity
- [ ] State changes to CONFIRMED
- [ ] Identity moves to Confirmed section
- [ ] Card shows "Return to Review" button only
- [ ] Card reflects new state (emerald badge)

### 7. Skip Identity
- [ ] Click Skip on a To Review item
- [ ] State changes to SKIPPED
- [ ] Identity moves to Skipped section
- [ ] Card shows Confirm/Reject/Reset buttons
- [ ] Can click Reset to return to To Review

### 8. Reject Identity
- [ ] Click Reject on a To Review item
- [ ] State changes to REJECTED (or CONTESTED)
- [ ] Identity moves to Rejected section
- [ ] Card shows "Return to Review" button only
- [ ] Item does NOT vanish - always visible in Rejected section

### 9. Workflow Reversibility
- [ ] From Confirmed: Click Reset → returns to To Review
- [ ] From Skipped: Click Reset → returns to To Review
- [ ] From Rejected: Click Reset → returns to To Review
- [ ] All 292 identities always visible across all sections (no vanishing)

### 10. Detach Face
- [ ] Face is removed from identity
- [ ] Face count updates immediately (no stale count)
- [ ] Detached face creates new identity in To Review section

### 11. Manual Search
- [ ] Returns results
- [ ] Results show photos (not blank cards)
- [ ] Results are clickable

## Known Bug Locations (Reference)

| Bug | Location | Status |
|-----|----------|--------|
| Photo modal navigation | app/main.py:1808 | [x] Fixed 2026-02-04 (6cf5c1a) |
| Detach face count | app/main.py:2558-2595 | [x] Fixed 2026-02-04 |
| Missing crops hidden | app/main.py:1221-1243, 2359-2382 | [x] Fixed 2026-02-04 |
| CSS selector UUIDs | app/main.py:1042, 1092 | [ ] Fixed |
| Race condition merge | app/main.py:2251-2310 | [ ] Deferred |
| Photo 404 UX | app/main.py:1745-1762 | [ ] Deferred |
| Inbox endpoint semantics | app/main.py:2872-2915 | [ ] Deferred |
| Unsanitized filename | app/main.py:2728 | [ ] Deferred |
| Vanishing reject items | app/main.py:1464 | [x] Fixed 2026-02-04 - Rejected state now fetched and rendered |

## Quick Smoke Test (5 min)

If short on time, test these critical paths:

1. Upload 1 photo with a face
2. Click "View Photo" on the resulting identity
3. Click the face overlay in the modal
4. Verify it scrolls to the identity card
5. Use "Find Similar" and verify results render
