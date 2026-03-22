# Session 129 Feedback — Interactive Triage

Session mode: interactive
Started: 2026-03-21

## Summary
| FB ID | Title | Severity | Category | Status |
|-------|-------|----------|----------|--------|
| FB-001 | Duplicate Esther Burd Fox identities | P0 | DATA | FIXED |
| FB-002 | Esther Burd face untagged in photo despite prior tagging | P0 | DATA | FIXED (Session 133 data repair + Session 134 verification) |
| FB-003 | Face overlay click does nothing for some faces | P1 | UX | FIXED (Session 134 — FB-016 root cause resolved, faces now resolve) |
| FB-004 | Quick Identify name dropdown shows wrong community names | P1 | UX | FIXED (Session 134 Track C — community-scoped dropdown) |
| FB-005 | Face cards at bottom of photo page not clickable to person page | P1 | UX | FIXED (Session 134 Track B — wrapped in A tags) |
| FB-006 | Unidentified face shows no number in photo overlay | P2 | UX | FIXED (Session 133 data repair — faces now resolve to identities) |
| FB-007 | People in photo section — face crops not linked to person pages | P1 | UX | FIXED (Session 134 Track B — same as FB-005) |
| FB-008 | People in photo grid — no visual distinction identified vs unidentified | P2 | UX | FIXED (Session 134 Track B — state-colored borders) |
| FB-009 | Photo page people grid — 2-column wastes space on desktop | P3 | UX | FIXED (Session 134 Track B — responsive 4-col grid) |
| FB-010 | Speed Loop — Esther's face has no checkmark/name | P1 | BUG | FIXED (Session 133 data repair — FB-002 root cause resolved) |
| FB-011 | Speed Loop — two Esther Burds in tag search | P0 | DATA | FIXED |
| FB-012 | Focus mode — two Esther Burds in Similar Identities | P0 | DATA | FIXED |
| FB-013 | Focus sidebar — 839 New Matches is overwhelming | P2 | UX | BACKLOG |
| FB-014 | Identify Mode button green when not active | P3 | UX | BACKLOG |
| FB-015 | "Back to Morris Shane" assumes navigation context | P3 | NAVIGATION | BACKLOG |
| FB-016 | photo_faces uses inbox IDs, URLs use SHA256 IDs | P1 | DATA | FIXED (already resolved — Session 131 SHA256 reverse index + Session 133 data repair) |
| FB-017 | Mobile — no easy way to switch communities | P1 | MOBILE | BACKLOG |
| FB-018 | Compare Faces — "56 of 83" shows stale pre-merge count | P2 | DATA | BACKLOG |
| FB-019 | Compare Faces modal — no merge/action buttons, dead-end UX | P2 | UX | BACKLOG |
| FB-020 | Face count on person page doesn't reflect merged faces without embeddings | P2 | DATA | INVESTIGATING |

---

## Entries

### FB-001: Duplicate Esther Burd Fox identities
- **Severity:** P0
- **Category:** DATA
- **Context:** Two CONFIRMED "Esther Burd Fox" identities — 65207728 (83 anchors) and d4f29ffb (29 anchors). Created because confirm_identity() had no duplicate name check.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshot 5.06.54 PM (speed loop showing two Esther Burd entries)
- **Root cause:** `confirm_identity()` in core/registry.py did not check for existing CONFIRMED identities with the same name.
- **Fix:** FIXED — Merged d4f29ffb into 65207728 (now 112 faces). Added duplicate name prevention to confirm + rename. 9 tests.

### FB-002: Esther Burd face untagged in photo despite prior tagging
- **Severity:** P0
- **Category:** DATA
- **Context:** Photo 10a7d40eb3bf94f7 (Dayton Ohio group) — Esther Burd shows as unidentified with dashed orange border and no person number. 16/18 identified but Esther's face lost its assignment.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshot 5.02.39 PM
- **Root cause:** **photo_faces table mismatch.** Photo has two IDs: SHA256 `10a7d40eb3bf94f7` (URLs) and inbox `inbox_fox-charlie-001_173_...` (photo_faces table). Face-to-identity lookup uses SHA256 but photo_faces stores inbox ID, causing 10/18 faces to be unresolvable. 5 faces have merge chains to deleted IDs; 5 truly orphaned.
- **Fix:** ROOT CAUSE IDENTIFIED — See FB-016. Needs photo_faces to handle both ID formats.

### FB-003: Face overlay click does nothing for some faces
- **Severity:** P1
- **Category:** UX
- **Context:** Clicking Esther's face in photo overlay does nothing. Other identified faces navigate to person page.
- **Device:** Desktop, Chrome
- **Root cause:** Click handler requires identity_id. Esther's face doesn't resolve to any identity (FB-002). Should show tag/identify prompt for unidentified faces.
- **Fix:** BACKLOG — Unidentified faces should be clickable: navigate to INBOX identity or open tag prompt.

### FB-004: Quick Identify name dropdown shows wrong community names
- **Severity:** P1
- **Category:** UX
- **Context:** Fox Family photo page "Quick Identify" dropdown shows ALL community names (Abraham Almaleh, Anita Capeluto Franco — Rhodes names). Should default to Fox Family names.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshot 5.04.04 PM
- **Root cause:** Name dropdown query not filtered by community_slug.
- **Fix:** BACKLOG — Filter by current community, add "Show all" option.

### FB-005: Face cards at bottom of photo page not clickable to person page
- **Severity:** P1
- **Category:** UX
- **Context:** Circular face crops in "People in this photo" can't be clicked to navigate to person page. Only "See all photos" text link works.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshots 5.03.02 PM, 5.03.11 PM
- **Root cause:** Face crop `Img` elements not wrapped in anchor tags.
- **Fix:** BACKLOG — Wrap in `A(href=f"{nav_prefix}/person/{identity_id}")`.

### FB-006: Unidentified face shows no number in photo overlay
- **Severity:** P2
- **Category:** UX
- **Context:** Esther's position shows "Unidentified" with no person number. Person 2931 (another unidentified) has a number. Inconsistent.
- **Device:** Desktop, Chrome
- **Root cause:** Esther's face doesn't resolve to any identity (FB-002). Person 2931 has a valid INBOX identity. Overlay falls back to "Unidentified" when no identity found.
- **Fix:** BACKLOG — Related to FB-016.

### FB-007: People in photo section — face crops not linked to person pages
- **Severity:** P1
- **Category:** UX
- **Context:** In "People in this photo" grid, clicking face crop image does nothing. Duplicate of FB-005 but noted separately for completeness.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshots 5.03.02, 5.03.11, 5.03.20 PM
- **Root cause:** Same as FB-005.
- **Fix:** BACKLOG — Make entire card or face image clickable.

### FB-008: People in photo grid — no visual distinction identified vs unidentified
- **Severity:** P2
- **Category:** UX
- **Context:** Identified people (Morris Shane) look identical to unidentified (Person 2931) in the grid. Photo overlay uses green vs orange dashed borders but grid doesn't carry this through.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshots 5.03.02, 5.03.11, 5.03.20 PM
- **Root cause:** Grid cards don't apply state-based styling.
- **Fix:** BACKLOG — Add green border for CONFIRMED, amber for PROPOSED, dashed for INBOX.

### FB-009: Photo page people grid — 2-column wastes space on desktop
- **Severity:** P3
- **Category:** UX
- **Context:** "People in this photo" uses 2-column grid on desktop. 18 people = very long scroll. 3-4 columns better.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshots 5.03.02, 5.03.11 PM
- **Root cause:** Grid uses `grid-cols-2` without desktop breakpoints.
- **Fix:** BACKLOG — `grid-cols-2 sm:grid-cols-3 lg:grid-cols-4`.

### FB-010: Speed Loop — Esther's face has no green checkmark, no name
- **Severity:** P1
- **Category:** BUG
- **Context:** Most identified faces have green checkmarks + names. Esther's position has yellow/orange highlight, no checkmark, no name.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshot 5.05.38 PM
- **Root cause:** Same as FB-002 — face doesn't resolve to identity due to photo_faces mismatch.
- **Fix:** Depends on FB-016.

### FB-011: Speed Loop — two Esther Burds in tag search dropdown
- **Severity:** P0
- **Category:** DATA
- **Context:** Tag search shows "Esther Bur... 83 faces" and "Esther Bur... 29 faces".
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshot 5.06.18 PM
- **Root cause:** Duplicate CONFIRMED identities (FB-001).
- **Fix:** FIXED — Duplicate merged.

### FB-012: Focus mode — two Esther Burd Fox in Similar Identities
- **Severity:** P0
- **Category:** DATA
- **Context:** Unidentified Person 113 shows two "Esther Burd Fox" suggestions — 59% (dist 0.91) and 49% (dist 1.02).
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshot 5.06.54 PM
- **Root cause:** Duplicate CONFIRMED identities (FB-001).
- **Fix:** FIXED — Duplicate merged.

### FB-013: Focus sidebar — 839 New Matches is overwhelming
- **Severity:** P2
- **Category:** UX
- **Context:** Sidebar shows "New Matches 839" — daunting, no prioritization. User can't tell high vs low confidence.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshot 5.06.54 PM
- **Root cause:** Badge shows raw count without confidence tiering.
- **Fix:** BACKLOG — Show high-confidence count separately or add confidence filter.

### FB-014: Identify Mode button green when not active
- **Severity:** P3
- **Category:** UX
- **Context:** "Identify Mode" button has emerald/green background even when not toggled on. Green = active in standard UI language.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshot 5.02.39 PM
- **Root cause:** Button CSS uses emerald as default instead of active-state indicator.
- **Fix:** BACKLOG — Neutral style for inactive, emerald for toggled-on.

### FB-015: "Back to Morris Shane" assumes navigation context
- **Severity:** P3
- **Category:** NAVIGATION
- **Context:** Photo page shows "Back to Morris Shane" but user may not have come from Morris Shane's page. Back-link should reflect actual navigation.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshot 5.02.39 PM
- **Root cause:** identity_id URL param generates back-link regardless of actual navigation source.
- **Fix:** BACKLOG — Use browser history or generic "Back to Photos".

### FB-016: photo_faces uses inbox IDs, URLs use SHA256 IDs
- **Severity:** P1
- **Category:** DATA
- **Context:** Batch-uploaded photos have inbox-style IDs in photo_faces (`inbox_fox-charlie-001_173_...`) but app generates SHA256 IDs for URLs (`10a7d40eb3bf94f7`). Face-to-identity lookup on photo pages uses SHA256 to query photo_faces, returns 0 results. This causes 10/18 faces on the Dayton Ohio group photo to appear orphaned.
- **Root cause:** Upload pipeline writes inbox photo IDs to photo_faces. Photo page route generates SHA256 from filename. No mapping between formats.
- **Fix:** BACKLOG — Either: (a) populate photo_faces with both ID formats, (b) add SHA256→inbox fallback lookup, or (c) migrate to consistent IDs. **Root cause of FB-002, FB-003, FB-006, FB-010.**

### FB-017: Mobile — no easy way to switch communities
- **Severity:** P1
- **Category:** MOBILE
- **Context:** On mobile, there's no visible community switcher. User has to tap the search icon (bottom right) to open sidebar, then find the "Switch" link. This is a multi-step discovery problem — new users would never find it.
- **Device:** Mobile, Safari (iPhone)
- **Screenshot:** N/A (user described workflow)
- **Root cause:** Community switcher only exists in desktop sidebar. Mobile header/nav doesn't expose it.
- **Fix:** BACKLOG — Add community switcher to mobile bottom nav or mobile header. Could be a dropdown in the top bar showing current community name, or a dedicated icon in the bottom nav bar.

### FB-018: Compare Faces — "56 of 83" shows stale pre-merge count
- **Severity:** P2
- **Category:** DATA
- **Context:** Compare Faces modal shows "56 of 83" pagination for Esther Burd Fox. After the merge (83+29=112), the count should be 112, not 83. The compare view is reading a cached or stale face count.
- **Device:** Mobile, Safari
- **Screenshot:** Screenshot 6:42 PM — Compare Faces modal showing "56 of 83"
- **Root cause:** Compare Faces face count either: (a) was cached before the merge, or (b) only counts faces with valid embeddings/crops (which may be 83 if the 29 merged faces don't have crops).
- **Fix:** BACKLOG — Ensure Compare Faces reads live anchor count from registry, not a cached value.

### FB-019: Compare Faces modal — no merge/action buttons, dead-end UX
- **Severity:** P2
- **Category:** UX
- **Context:** The Compare Faces modal shows "Unidentified Person d02660e1 vs Esther Burd Fox" with face crops and pagination. But there are NO action buttons — no "Merge", "Not Same", "Same Person" buttons. The user can compare visually but can't ACT on what they see. It's a dead-end: you compare, then close, then have to find the identity in a different view to take action.
- **Device:** Mobile, Safari
- **Screenshot:** Screenshot 6:42 PM
- **Root cause:** Compare Faces modal was designed as read-only comparison. Action buttons were never added.
- **Fix:** BACKLOG — Add "Same Person (Merge)" and "Not Same" action buttons at bottom of Compare Faces modal. After action, navigate to next comparison or close with success feedback.

### FB-020: Face count on person page doesn't reflect merged faces without embeddings
- **Severity:** P2
- **Category:** DATA
- **Context:** After merging Esther Burd Fox (83+29=112 anchors in Supabase), the person page shows ~83-86 faces, not 112. Supabase confirms 112 unique anchor_ids. The page renders ~87 crop images but labels it "83 faces". Some of the 29 merged faces likely don't have embeddings or crops in the production system.
- **Device:** Desktop + Mobile
- **Root cause:** The face count displayed on the person page is filtered by faces that have valid entries in the embeddings cache or photo_faces table, not the raw anchor_ids count. Faces from the merged identity (d4f29ffb) may not have been fully synced to all data layers.
- **Fix:** INVESTIGATING — Need to verify which of the 29 merged faces have crops in R2 and entries in embeddings. The face count should either show all anchors or clearly indicate "X of Y faces have images".
