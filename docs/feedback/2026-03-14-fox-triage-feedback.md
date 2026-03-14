# Fox Family Triage Feedback — 2026-03-14

**Source:** Nolan's live triage session, ~20 minutes of speed-run + people page work
**Result:** Named and merged Charles Fox (68 faces), Esther Burd Fox (12 faces), Roland Fox (31 faces). Linked Charles and Esther to GEDCOM.

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

## Screenshots
16 screenshots captured and viewable in Chrome tabs. Chronological order shows:
1. Speed-run confirm of Person 3594 (Charles Fox, 14 faces)
2. Enrichment panel with suggested matches
3. People page progression through merges (6→5→3 people)
4. Person 2986 page (Charles Fox, 58 faces after merge)
5. GEDCOM linking (Charles Borris Fox, b. 1931)
6. Person 3086 similar identities panel (Charles Fox 72% match)
7. Merge complete (68 faces confirmed as Charles Fox)
8. Person 2988 page (renamed to Esther Burd Fox)
9. GEDCOM linking for Esther (Esther Burd, b. 1900, d. 1966)
10. Final state: 3 confirmed people (Roland Fox, Esther Burd Fox, Person 2986)
