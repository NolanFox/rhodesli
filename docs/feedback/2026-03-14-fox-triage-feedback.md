# Fox Family Triage Feedback — 2026-03-14

**Source:** Nolan's live triage session, ~20 minutes of speed-run + people page work
**Result:** Named and merged Charles Fox (68 faces), Esther Burd Fox (12 faces), Roland Fox (31 faces). Linked Charles and Esther to GEDCOM.

## Resolution Status (Updated Session 134, 2026-03-22)
| FB | Status |
|----|--------|
| FB-100 | FIXED (Session 134 — already implemented, verified) |
| FB-101 | BACKLOG (COMMUNITY-004) |
| FB-102 | BACKLOG |
| FB-103 | FIXED (already implemented — merge banner with face count) |
| FB-104 | FIXED (already implemented — merge search → name → GEDCOM order) |
| FB-105 | PARTIALLY ADDRESSED (Session 134 deepcopy removal, full measurement pending) |
| FB-106 | FIXED (Session 134 — ?from=admin on enrichment links) |
| FB-107 | BACKLOG (unmerge UX needed) |
| FB-108 | BACKLOG (merge count context messaging) |
| FB-109 | BACKLOG (browse view hash anchor issue) |
| FB-110 | FIXED (already implemented — GEDCOM panel in enrichment) |
| FB-111 | BACKLOG (ML cluster ordering improvement) |
| FB-113 | FIXED (Session 134 Track A — "Identified" label for CONFIRMED) |
| FB-114 | BACKLOG ("Grouped" badge removal) |

## Issues Found (in order encountered)

### FB-100: No cross-community indicator on suggested matches
- **Severity:** P1
- **What happened:** Big Leon Capeluto appears in speed-run suggestions but is from Rhodes, not Fox Family. No badge indicating this is a cross-community person.
- **Expected:** "From Rhodes" badge on cross-community suggestions, same as exists on discovery cards
- **BACKLOG:** Extends COMMUNITY-014

### FB-101: No indication person exists in multiple communities
- **Severity:** P2
- **What happened:** Roland Fox exists in both Fox Family and Rhodes. No visual indicator of this.
- **Expected:** "Also in Rhodes" or multi-community badge
- **BACKLOG:** COMMUNITY-004 (existing, never implemented)

### FB-102: Only 3 suggested matches shown, no way to see more
- **Severity:** P2
- **What happened:** Speed-run enrichment panel shows Big Leon, Roland, and one Charles cluster. Cannot expand to see more similar identities.
- **Expected:** "Load more" or scrollable list of all matches above threshold

### FB-103: Merge from speed-run silently fails or is unclear
- **Severity:** P1
- **What happened:** Clicked "Merge" on Person 2986 in speed-run enrichment panel. It jumped to the next cluster. No confirmation the merge happened. No indication the name was saved.
- **Expected:** Clear confirmation ("Merged 44 faces into Charles Fox"), stay on enrichment panel until user clicks "Next"

### FB-104: Flow order wrong — should be merge first, then name, then GEDCOM
- **Severity:** P1 (workflow)
- **What happened:** Enrichment panel shows name input first, then merge search below. But logically: (1) check if this is an existing person → merge if yes (name comes from target), (2) if new person → name them, (3) link to GEDCOM.
- **Expected:** Reorder enrichment panel: Merge search at top → Name input (pre-filled if merged) → GEDCOM link

### FB-105: Performance very slow on merge/similar/rename
- **Severity:** P1
- **What happened:** Merge took several seconds. Find Similar took "forever" to load. Rename was "very, very slow."
- **Root cause likely:** Full registry reload on every operation, large identity count (1174), no caching
- **Related:** PERF-002, OD-011

### FB-106: Speed-run navigates to public page instead of admin
- **Severity:** P1
- **What happened:** After confirming and naming from speed-run, navigating to the person page went to public page (no admin controls visible initially). Had to click "Edit in Admin" to get back.
- **Expected:** Speed-run should always stay in admin context. Person page links from admin should go to admin view.

### FB-107: Merge confirmation says "can't be undone" — is this accurate?
- **Severity:** P2
- **What happened:** Merge dialog says "This action cannot be undone." But we claim merges are reversible.
- **Truth:** Merges ARE technically reversible (detach faces, create new identity) but the current UI has no "unmerge" button. The warning is effectively correct for the current UX.
- **Action:** Either add unmerge capability or keep the warning honest.

### FB-108: People count fluctuates confusingly (6 → 5 → 3 → 5 → 3)
- **Severity:** P2
- **What happened:** After various merges, the People count jumped around. This is actually correct behavior (merges consolidate identities) but it's disorienting without context.
- **Expected:** After a merge, show "Merged [source] into [target] — now N people" message

### FB-109: Browse view route doesn't work properly
- **Severity:** P2
- **What happened:** `?section=confirmed&view=browse#identity-65207728...` was buggy, while `?section=confirmed` worked fine.
- **Root cause:** Likely the hash anchor + view=browse combination has a rendering issue

### FB-110: No GEDCOM linking from speed-run enrichment panel
- **Severity:** P1
- **What happened:** After confirming and naming, there's no way to link to GEDCOM without leaving speed-run to the person page.
- **Expected:** GEDCOM search/link should be available in the enrichment panel, right after naming

### FB-111: Cluster ordering — related clusters not grouped together
- **Severity:** P2 (ML insight)
- **What happened:** Roland Fox and Big Leon clusters appeared before other Charles Fox clusters, even though cluster IDs are sequential and related. Suggests the ML knows these are related but doesn't surface that in ordering.
- **Insight:** Consider sorting speed-run clusters by "most similar to recently confirmed" to group related people together

### FB-112: Esther Burd spelling
- **Severity:** N/A (voice-to-text artifact)
- **Note:** Correct spelling is Esther Burd (B-U-R-D). Already in user memory.

## Workflow Vision (from Nolan)

The intended flow after speed-run triage:
1. **Speed-run** → confirm clusters, merge duplicates, name people
2. **GEDCOM linking** → connect confirmed identities to family tree records
3. **Enrichment** → run Gemini for date estimation, geolocation, face analysis (leveraging GEDCOM relationships)
4. **Longitudinal work** → PRD-038 analysis with confirmed identities at different ages

This requires the speed-run enrichment panel to support the full workflow: merge → name → GEDCOM link, all without leaving the speed-run page.

## Additional UX Issues from Screenshot Review

### FB-113: "Under Review" badge contradicts CONFIRMED state
- **Severity:** P1
- **Screenshots:** Person 2986 page, Person 3086 page
- **What:** Public person page shows "Under Review" badge and "This person hasn't been identified yet" CTA even when the identity is CONFIRMED. The admin section below correctly shows CONFIRMED.
- **Root cause:** The public page status badge uses a different logic path than the admin badge. CONFIRMED identities without a name still show "Under Review" instead of "Confirmed."
- **Impact:** Confusing and contradictory — makes it look like the system is broken.

### FB-114: "Grouped (N faces)" badge meaning unclear
- **Severity:** P2
- **Screenshots:** People page cards
- **What:** Some identity cards show "Grouped (14 faces)" next to CONFIRMED. What does "Grouped" mean? Is it different from non-grouped CONFIRMED? Roland Fox shows CONFIRMED without "Grouped" while Person 3594 shows CONFIRMED + "Grouped (14 faces)".
- **Root cause:** "Grouped" likely means the identity came from the clustering pipeline rather than manual creation. This is an implementation detail, not meaningful to the admin.
- **Recommendation:** Remove "Grouped" badge or replace with something meaningful like "From clustering" in a tooltip.

### FB-115: Face count mismatch / stale cache on people cards
- **Severity:** P2
- **Screenshots:** People page showing Person 2986 at 44 faces, then later Charles Fox at 68 faces
- **What:** After merging, the people page sometimes shows stale face counts until a hard refresh. Person 2986 showed 44 faces even after a merge that should have updated to 58.
- **Root cause:** Registry cache staleness — the in-memory cache wasn't invalidated between the merge action and the page reload.

### FB-116: Person page title doesn't update after rename
- **Severity:** P2
- **Screenshots:** Person 2988 page after rename to "Esther Burd Fox"
- **What:** The page heading still shows "Unidentified Person 2988" after successful rename. The admin section shows "Esther Burd Fox" correctly, and a "Renamed to 'Esther Burd Fox'" confirmation appears.
- **Root cause:** The HTMX partial swap for rename updates the admin section but doesn't update the main page heading (`<h1>`). Requires a full page refresh to see the new name in the header.

### FB-117: Missing face crop on similar matches (CROP-001 recurrence)
- **Severity:** P2
- **Screenshots:** Similar identities panel for Person 3086
- **What:** Person d768a992 in the similar matches shows a grey/missing crop placeholder. This is the CROP-001 issue (Fox crops not on R2) appearing in the similar matches context.

### FB-118: "Merge → Charles Fox" button label — good pattern, apply everywhere
- **Severity:** Positive feedback
- **Screenshots:** Similar identities after merge
- **What:** After a merge establishes Charles Fox, the merge buttons for other similar identities update to "Merge → Charles Fox" instead of just "Merge". This is clear and helpful — should be the pattern everywhere.

### FB-119: Two unnamed confirmed people remain (Person 3086, Person 2941)
- **Severity:** Observation
- **Screenshots:** Final people page
- **What:** Person 3086 (10 faces) and Person 2941 (8 faces) are CONFIRMED but unnamed and unmerged. They might be additional Charles Fox clusters at different ages, or different people. The similar panel showed Person 3086 at 72% match to Charles Fox — likely the same person.
- **Action:** Nolan should decide whether to merge these or keep separate.

## Screenshots
16 screenshots captured. Chronological order:
1. Speed-run confirm of Person 3594 (Charles Fox, 14 faces)
2. Enrichment panel with suggested matches
3. People page — 6 confirmed people
4. People page — 5 after first merge (Person 3594 → Person 2986 = 58 faces)
5. Person 2986 public page — "Unidentified Person 2986", CONFIRMED, 58 faces
6. Person 2986 renamed to Charles Fox — confirmation shown
7. People page — GEDCOM linking for Charles Fox → Charles Borris Fox (b. 1931)
8. People page — GEDCOM linked, "Linked to Family Tree" green banner
9. Person 3086 Similar panel — Charles Fox 72%, 5 other matches at 69%
10. Similar panel after merge — "Merge → Charles Fox" buttons, 3 new cross-community matches
11. Merge complete — "68 faces now confirmed as Charles Fox"
12. People page — 3 people after all Charles Fox merges
13. Person 2988 public page — "Unidentified Person 2988", CONFIRMED
14. Person 2988 renamed to Esther Burd Fox
15. People page — Esther Burd Fox GEDCOM search (55 results for "Esther Burd")
16. Final state — Linked to GEDCOM "Esther Burd (b. 1900 — d. 1966)"
