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
- [ ] Card shows "Return to Inbox" button only
- [ ] Card reflects new state (emerald badge)

### 7. Skip Identity
- [ ] Click Skip on a Inbox item
- [ ] State changes to SKIPPED
- [ ] Identity moves to Skipped section
- [ ] Card shows Confirm/Reject/Reset buttons
- [ ] Can click Reset to return to Inbox

### 8. Reject Identity
- [ ] Click Reject on a Inbox item
- [ ] State changes to REJECTED (or CONTESTED)
- [ ] Identity moves to Rejected section
- [ ] Card shows "Return to Inbox" button only
- [ ] Item does NOT vanish - always visible in Rejected section

### 9. Workflow Reversibility
- [ ] From Confirmed: Click Reset → returns to Inbox
- [ ] From Skipped: Click Reset → returns to Inbox
- [ ] From Rejected: Click Reset → returns to Inbox
- [ ] All 292 identities always visible across all sections (no vanishing)

### 10. Detach Face
- [ ] Face is removed from identity
- [ ] Face count updates immediately (no stale count)
- [ ] Detached face creates new identity in Inbox section

### 11. Manual Search
- [ ] Returns results
- [ ] Results show photos (not blank cards)
- [ ] Results are clickable

### 12. Command Center Layout (v0.3.8)
- [ ] Sidebar is fixed on left (doesn't scroll with content)
- [ ] Sidebar shows correct counts for all sections
- [ ] Sidebar highlights current section with color
- [ ] "Upload Photos" button in sidebar links to /upload
- [ ] Version number displays in sidebar footer (v0.3.8)
- [ ] Main content is offset from sidebar (not hidden behind it)

### 13. Section Navigation
- [ ] Click "Inbox" in sidebar → shows Inbox section
- [ ] Click "Skipped" in sidebar → shows Skipped section
- [ ] Click "Confirmed" in sidebar → shows Confirmed section
- [ ] Click "Dismissed" in sidebar → shows Dismissed section
- [ ] Each section shows appropriate header and content

### 14. Focus Mode (Inbox section)
- [ ] Default view shows one identity expanded
- [ ] Expanded card shows large face thumbnail
- [ ] Expanded card shows face count and all faces
- [ ] "Up Next" queue shows upcoming items
- [ ] Queue shows "+N more" indicator when appropriate
- [ ] Focus/Browse toggle buttons are visible
- [ ] "Focus" button is highlighted when in focus mode

### 15. Focus Mode Actions
- [ ] Click Confirm → advances to next identity (not stay on confirmed card)
- [ ] Click Skip → advances to next identity
- [ ] Click Reject → advances to next identity
- [ ] Toast notification appears for each action
- [ ] When all items reviewed → shows "All caught up!" message
- [ ] "Find Similar" button works on expanded card

### 16. Browse Mode (Inbox section)
- [ ] Click "View All" → switches to grid view
- [ ] "View All" button is highlighted when in browse mode
- [ ] Grid shows all identity cards
- [ ] Can switch back to Focus mode
- [ ] Actions in browse mode update cards normally (don't advance)

### 17. Source Attribution (v0.4.0)
- [ ] Upload form has source/collection text input
- [ ] Source autocomplete suggests existing collections
- [ ] New uploads include source in photo metadata
- [ ] Source displays in Photo Context modal (below dimensions)

### 18. Photo Viewer (v0.4.0)
- [ ] "Photos" link appears in sidebar under "Browse" section
- [ ] Photo count badge is accurate
- [ ] Click Photos → shows grid of all photos
- [ ] Photo cards show: thumbnail, face count, identified faces avatars, filename, source
- [ ] Filter dropdown shows all collections
- [ ] Filter by collection works correctly
- [ ] Sort dropdown has: newest, oldest, most faces, by collection
- [ ] Each sort option works correctly
- [ ] Click photo → Photo Context modal opens
- [ ] Face overlays in Photo Context are clickable
- [ ] Clicking face navigates to that identity

### 19. Docker Deployment (v0.5.0)
- [ ] `docker build -t rhodesli .` succeeds
- [ ] `docker run` with mounted volumes starts without errors
- [ ] Startup logs show correct config values
- [ ] `/health` endpoint returns JSON with status, counts
- [ ] App loads at localhost:5001
- [ ] All photos display correctly (served from mounted volume)
- [ ] Sidebar navigation works
- [ ] Focus mode works
- [ ] Photo viewer works
- [ ] Photo context modal opens

### 20. Production Upload (PROCESSING_ENABLED=false)
- [ ] Upload page renders
- [ ] Can select and upload files
- [ ] Files saved to `data/staging/{job_id}/`
- [ ] `_metadata.json` created with source and timestamp
- [ ] UI shows "Received X photos - Pending admin review" message
- [ ] NO subprocess spawned (no ML processing attempt)
- [ ] App does not crash or error

### 21. Railway Deployment (Production)
- [ ] App accessible at custom domain (rhodesli.nolanandrewfox.com)
- [ ] HTTPS working (Cloudflare SSL)
- [ ] `/health` returns expected counts
- [ ] All identities visible
- [ ] All photos load from Railway volume
- [ ] Upload shows "pending admin review" message
- [ ] No console errors

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
