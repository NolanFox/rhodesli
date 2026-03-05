# Session 89 Continuation — User Feedback (save in case of compaction)

## Feedback from Nolan (2026-03-05 00:07)

1. **Location doesn't persist after reload** — Re-analyze returns Asheville but page refresh still shows Brooklyn. The volume write path fix (DATA_DIR) may still not be working correctly.

2. **Wrong model label** — The UI says "Analyzed with Gemini 3-flash" but the actual call uses gemini-3.1-pro-preview. The model label should NOT be hardcoded — it should reference the actual model used in the API call that produced the displayed result.

3. **Photo Detective Evidence incomplete** — Only shows evidence for date estimation, not geographic/location estimation. Need to show HOW the GEDCOM biographical context was used to determine the location. The user wants to see the reasoning chain: "Victoria lived at 33 Elizabeth Street, Asheville, NC from 1928-1940 → children born in Asheville → photo likely taken in Asheville."

## Current State
- Gemini API returns correct result: "Asheville, North Carolina, USA" with GEDCOM context
- 4 bugs fixed: identity dict envelope, timeout, JSON structure, DATA_DIR path
- But page refresh still shows Brooklyn — persistence issue remains
- Commits: 0530f0c, 819c2c7, b76373d, c1378d4

## TODO (do not stop until done)
- [ ] Fix location persistence on page refresh
- [ ] Dynamic model label from API call data (not hardcoded)
- [ ] Show GEDCOM/location reasoning in Photo Detective Evidence section
