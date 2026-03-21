# Session 129 Feedback — Interactive Triage

Session mode: interactive
Started: 2026-03-21

## Summary
| FB ID | Title | Severity | Category | Status |
|-------|-------|----------|----------|--------|
| FB-001 | Duplicate Esther Burd Fox identities | P0 | DATA | INVESTIGATING |
| FB-002 | Esther Burd face untagged in photo despite prior tagging | P0 | DATA | INVESTIGATING |
| FB-003 | Face overlay click does nothing for some faces | P1 | UX | BACKLOG |
| FB-004 | Quick Identify name dropdown shows wrong community names | P1 | UX | BACKLOG |
| FB-005 | Face cards at bottom of photo page not clickable to person page | P1 | UX | BACKLOG |
| FB-006 | Unidentified face shows no number in photo overlay | P2 | UX | BACKLOG |

---

## Entries

### FB-001: Duplicate Esther Burd Fox identities
- **Severity:** P0
- **Category:** DATA
- **Context:** On /c/fox-family/?section=to_review, TWO separate "Esther Burd Fox" identities appear in suggestions — one with 83 faces, one with 29 faces. Both are Fox Family Archive. This is a data integrity issue — there should only be one Esther Burd Fox identity.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshot 2026-03-21 at 5.06.54 PM (speed loop tag search showing two Esther Burd entries)
- **Root cause:** TBD — investigating. Possible split during merge/confirm, or duplicate creation during upload pipeline.
- **Fix:** INVESTIGATING — must understand root cause before fixing. Five-alarm fire per user.

### FB-002: Esther Burd face untagged in photo despite prior tagging
- **Severity:** P0
- **Category:** DATA
- **Context:** Photo 10a7d40eb3bf94f7 — Esther Burd (woman in middle row far right, below Albert Fox) was previously tagged but now shows as unidentified with dashed orange border. 16/18 identified but Esther's face lost its assignment.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshot 2026-03-21 at 5.02.39 PM (photo overlay showing Esther as unidentified)
- **Root cause:** TBD — likely related to FB-001 duplicate identity issue. Face may have been orphaned when identity was split/duplicated.
- **Fix:** INVESTIGATING

### FB-003: Face overlay click does nothing for some faces
- **Severity:** P1
- **Category:** UX
- **Context:** Clicking on Esther Burd's face in the photo overlay does nothing — no navigation, no popup. Other faces (e.g. other identified people) do navigate to person page when clicked. Inconsistent behavior.
- **Device:** Desktop, Chrome
- **Screenshot:** N/A
- **Root cause:** TBD — may be related to the face being unidentified/orphaned
- **Fix:** BACKLOG

### FB-004: Quick Identify name dropdown shows wrong community names
- **Severity:** P1
- **Category:** UX
- **Context:** On the photo page in Fox Family community, clicking "Quick Identify" on an unidentified face shows a dropdown with names from ALL communities (Rhodes names like Abraham Almaleh, Anita Capeluto Franco, etc.). Should default to showing only Fox Family Archive names.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshot 2026-03-21 at 5.04.04 PM (dropdown showing Rhodes names)
- **Root cause:** Name dropdown query not filtered by community
- **Fix:** BACKLOG — filter dropdown by current community, with option to show all

### FB-005: Face cards at bottom of photo page not clickable to person page
- **Severity:** P1
- **Category:** UX
- **Context:** The face crop circles in the "People in this photo" section at the bottom of the photo page cannot be clicked to navigate to the person page. User expects clicking a face to go to that person's page. Only "See all photos →" link works.
- **Device:** Desktop, Chrome
- **Screenshot:** Screenshots 2026-03-21 at 5.03.02 PM and 5.03.11 PM
- **Root cause:** Face crop images likely not wrapped in anchor tags
- **Fix:** BACKLOG

### FB-006: Unidentified face shows no number in photo overlay
- **Severity:** P2
- **Category:** UX
- **Context:** The unidentified face (Esther Burd's position) shows as just "Unidentified" in the photo overlay instead of showing a person number like "Person 2931" which would help with debugging and reference.
- **Device:** Desktop, Chrome
- **Screenshot:** N/A
- **Root cause:** Display logic may strip number for INBOX state faces
- **Fix:** BACKLOG
