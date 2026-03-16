# Session 106 — Feedback Log

## Fox Family Speed-Run Feedback
| # | Page/Action | Issue | Priority | Status | BACKLOG |
|---|------------|-------|----------|--------|---------|
| FB-001 | Match view — "Click to view photo" | Button broken — URL missing community prefix `/c/fox-family`, photo modal may not load | P1 | FIXED (106b) | |
| FB-002 | Match view — face cards | Should show BOTH source photos side-by-side, not just face crops. Need to see photo context for comparison | P1 | FIXED (106b) | |
| FB-003 | Match view — face cards | Need clickable links to photo page AND person page from each card | P1 | FIXED (106b) | |
| FB-004 | App-wide | Face crop ↔ source photo toggle UX should be consistent across all views | P2 | BACKLOG | FB-004 |
| FB-005 | Match view + all identity cards | Raw internal IDs shown to users ("4ffef472", "3980") — should show "Unknown Person" or clean sequential number | P2 | BACKLOG | FB-005 |
| FB-006 | Match view — "Same Person" button | Response very slow, user thought nothing happened. Needs loading spinner or optimistic UI feedback | P1 | FIXED (106b) | |

| FB-007 | Photos section | No photo search by filename — when you have a filename from Google Photos (or any external source) and want to find it in the archive, there's no way to search. Should support filename, collection name, or any photo metadata search | P1 | FIXED (106b) | |
| FB-008 | Find Similar panel | No reciprocal rank indicator — when viewing matches for Person A, you can't see whether Person A is ALSO the top match for the suggested person. Mutual #1 matches are strong signals; asymmetric matches (where the suggestion's real top match is someone else like Esther Burd) are likely false positives. Show "Rank N for this person" next to each suggestion | P1 | FIXED (106b) | |

| FB-009 | Compare tool — person search | After selecting a person (e.g., Morris Shane), the search dropdown and results list remain visible. Should collapse/clear after selection to reduce clutter | P2 | BACKLOG | FB-009 |
| FB-010 | Compare tool — community scoping | Compare searches across ALL communities — Rhodes people show up when comparing Fox Family people. No way to filter by community. At scale (hundreds of communities) this becomes unusable noise. Future: community filter or default-to-current-community | P2 | BACKLOG | FB-010 |
| FB-011 | Compare tool — results context | Results show score (20%) and distance (1.40) but don't show the rank of this comparison relative to other matches. "Is Morris Shane in Person 2945's top 5?" is unanswered. The small text "best is 31% (Unidentified Person 193)" partially addresses this but is buried and unclear — needs prominence and clearer language like "Ranked #N of N matches for this person" | P1 | FIXED (106b) | |
| FB-012 | Compare tool — overall UX | General confusion about what the results mean and how to interpret them for identification decisions. The tool shows data but doesn't help the user reach a conclusion. Consider: summary verdict, mutual match indicator, "likely same person" / "unlikely" with explanation | P2 | BACKLOG | FB-012 |

## Rhodes Community Labeling Feedback
| # | Page/Action | Issue | Priority | Status | BACKLOG |
|---|------------|-------|----------|--------|---------|
