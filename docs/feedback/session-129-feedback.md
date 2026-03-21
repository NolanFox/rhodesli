# Session 129 Feedback — Interactive Triage

Session mode: interactive
Started: 2026-03-21

## Summary
| FB ID | Title | Severity | Category | Status |
|-------|-------|----------|----------|--------|
| FB-001 | Duplicate Esther Burd Fox identities | P0 | DATA | FIXED |
| FB-002 | Esther Burd face untagged in photo despite prior tagging | P0 | DATA | ROOT CAUSE IDENTIFIED |
| FB-003 | Face overlay click does nothing for some faces | P1 | UX | BACKLOG |
| FB-004 | Quick Identify name dropdown shows wrong community names | P1 | UX | BACKLOG |
| FB-005 | Face cards at bottom of photo page not clickable to person page | P1 | UX | BACKLOG |
| FB-006 | Unidentified face shows no number in photo overlay | P2 | UX | BACKLOG |
| FB-007 | People in photo section — face crops not linked to person pages | P1 | UX | BACKLOG |
| FB-008 | People in photo grid — no visual distinction identified vs unidentified | P2 | UX | BACKLOG |
| FB-009 | Photo page people grid — 2-column wastes space on desktop | P3 | UX | BACKLOG |
| FB-010 | Speed Loop — Esther's face has no checkmark/name | P1 | BUG | ROOT CAUSE: FB-002 |
| FB-011 | Speed Loop — two Esther Burds in tag search | P0 | DATA | FIXED |
| FB-012 | Focus mode — two Esther Burds in Similar Identities | P0 | DATA | FIXED |
| FB-013 | Focus sidebar — 839 New Matches is overwhelming | P2 | UX | BACKLOG |
| FB-014 | Identify Mode button green when not active | P3 | UX | BACKLOG |
| FB-015 | "Back to Morris Shane" assumes navigation context | P3 | NAVIGATION | BACKLOG |
| FB-016 | photo_faces uses inbox IDs, URLs use SHA256 IDs | P1 | DATA | BACKLOG |

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
