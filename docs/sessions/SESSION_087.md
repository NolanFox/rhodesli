# Session 87 — Compare & Discoveries UX Overhaul
## Date: 2026-03-04
## Version: v0.90.0 → v0.91.0
## Predecessor: Session 86b

### Mission
Fix critical UX issues preventing community members from finding and sharing face matches. Unify 12+ divergent confidence scoring paths, add best-matches summary to Compare, redesign shareable result page, improve Discoveries with sort/filter, and fix identity card navigation.

### What Shipped
1. **AD-200: Unified Confidence Scoring** — Single `core/confidence.py` module replaces 12+ scoring paths. Priority chain: calibrator → sigmoid CDF → linear fallback. Distance 1.13 now consistently produces 43% everywhere.
2. **Compare Best Matches Summary** — New summary section collects top matches across all faces (>= 40% confidence), sorted by confidence desc with CONFIRMED identities first. 150px face images, share buttons.
3. **Shareable Result Page Overhaul** — 200px hero faces, "Could this be [Name]?" positive framing, removed raw distance, improved OG tags for Facebook sharing.
4. **Discoveries Page** — Sort by confidence descending, filter by confidence tier (Strong 70%+/Possible 50%+/All) and photo, inline Compare link, 112px rounded-lg faces.
5. **Identity Card Fixes** — "Faces (N)" button on multi-face cards, detach button always visible for admin.

### Key Metrics
- 63 new tests (35 confidence + 8 compare + 5 shareable + 15 discoveries)
- 15 commits
- Parallel worktree execution: Track A (compare_routes.py) + Track B (main.py)

### Architectural Decisions
- AD-200: Unified Confidence Scoring — single source of truth for all confidence calculations

### Red Flags
- xdist test ordering flakiness (pre-existing, 1-2 tests)
- Chrome extension unavailable for browser verification — used Playwright
