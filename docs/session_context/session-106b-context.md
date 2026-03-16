# Session 106b Context — Triage Fix Sprint

**Predecessor:** Session 106 (triage feedback collection)
**Context file:** docs/session_context/session-106-feedback.md

## Background

Session 106 was a user-driven triage session where Nolan used the platform to identify Fox Family photos and cross-reference with Google Photos identifications. He collected 12 feedback items (FB-001 through FB-012) covering match view, compare tool, photo search, and reciprocal rank gaps.

## Key Workflow Insight

Nolan's identification workflow involves:
1. Looking at a photo in Google Photos → getting filename + Google's face grouping guess
2. Searching for that filename in Rhodesli to find the same photo
3. Using Find Similar to see who the ML thinks the faces match
4. Cross-referencing: if Google says "Dora Burd" and Rhodesli's top match for that face is "Esther Burd", checking whether the match is mutual (#1 for each other) or asymmetric
5. Asymmetric matches suggest the face is actually another photo of the dominant person (Esther), not the suggested person

This workflow is currently broken at steps 2 (no filename search), 4 (no reciprocal rank), and hampered at step 3 (compare tool UX issues).

## P1 Items to Fix

| # | Issue | Key files |
|---|-------|-----------|
| FB-001 | Match view photo button missing community prefix | `app/page_routes.py` or `app/cluster_review_routes.py` |
| FB-002 | Match view needs side-by-side source photos | Same as above |
| FB-003 | Match view needs photo/person page links | Same as above |
| FB-006 | "Same Person" button needs loading feedback | Same as above |
| FB-007 | No photo search by filename | `app/main.py` `_search_photos()` |
| FB-008 | Find Similar needs reciprocal rank indicator | `app/page_routes.py` find-similar API |
| FB-011 | Compare tool rank context buried | `app/compare_routes.py` |

## P2 Items to BACKLOG

| # | Issue |
|---|-------|
| FB-004 | Consistent face crop ↔ photo toggle UX |
| FB-005 | Raw internal IDs shown to users |
| FB-009 | Compare search dropdown persists |
| FB-010 | Compare tool cross-community noise |
| FB-012 | Compare tool overall UX confusion |

## Risk Areas

- **`core/neighbors.py` is FROZEN** — do not modify. Read its API, use it as-is.
- **Compare routes are 5778 lines** — careful targeted edits only, no refactoring.
- **Reciprocal rank performance** — calling `find_nearest_neighbors` per neighbor could be slow. Cache or batch.
- **Photo search index** — may be a static JSON file that needs rebuilding. Check if it's built at startup or by a script.
- **Community scoping** — match view URLs must always include `/c/{community}/` prefix.

## Cross-References

- Feedback log: `docs/session_context/session-106-feedback.md`
- Session 106 assessment: `docs/assessments/session-106-assessment.md`
- UX principles: `docs/design/UX_PRINCIPLES.md`
- Neighbors API: `core/neighbors.py` (FROZEN)
- AD-194: Find Similar panel design
