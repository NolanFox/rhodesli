# Session 100b Context — Continuation

**Predecessor:** Session 100 (Codex, incomplete)
**Agent:** Claude Code (Opus 4.6)
**Date:** 2026-03-12

## What Was Completed in 100b (First Context Window)

1. Full audit of sessions 97-100 → `docs/assessments/session-100b-audit.md`
2. Fixed broken page_routes.py (nav_prefix in timeline + timeline/more routes)
3. Cherry-picked 4 user naming actions, rejected 9 merge chain regressions in identities.json
4. Cleaned 12 orphaned worktrees
5. Fixed stop hook infinite loop (exit 2 → exit 1 for uncommitted files)
6. Updated current_session.txt to 100b
7. Committed and pushed (commits 2c42744, dcd7a89, 23b78e4)

## Research Completed — Bugs to Fix (Priority Order)

### BUG 1: Jacob Cohen "Unidentified" on Photo Overlay
- **Photo:** d5bc8746012a6da3 (Holocaust "We Remember" collage)
- **Root Cause:** Bounding box overlap conflict detection (commit a144b92 by Codex)
- **Mechanism:** Jacob Cohen face `inbox_805664720c8a` and Caden Franco Sadis face `inbox_a56c556100a9` have IoU=0.8256 (threshold is 0.80). When `bbox_conflict=True`, the code OVERRIDES the identity name with "Needs review" — even for CONFIRMED identities.
- **Fix location:** `app/page_routes.py` lines ~11190 in `public_photo_page()`. The conflict display logic overrides `name_el` with "Needs review" when `fi["bbox_conflict"]` is True.
- **Fix:** CONFIRMED identities should show their name even with bbox conflicts. Only show "Needs review" for PROPOSED/INBOX faces. Also consider raising IoU threshold from 0.80 to 0.85.
- **Also:** The "People in this photo" cards show "Overlaps another face assignment" warnings on Jacob Cohen and Caden Franco Sadis. This is in photo_routes.py around line 75-138.

### BUG 2: Photo Metadata Save Broken (Collection/Source/Source URL)
- **Root Cause:** ID mismatch in `_build_caches()` in `app/main.py` lines ~3854-3870
- **Mechanism:** The edit routes (e.g., `/api/photo/{photo_id}/collection`) correctly resolve cache_id → registry_id and save. Caches are invalidated. BUT when `_build_caches()` rebuilds, it iterates over cache IDs (SHA256) and calls `photo_registry.get_source(photo_id)` — but the registry stores data under inbox-style IDs. The ID mismatch means `get_source()` returns empty string, losing the saved data.
- **Fix:** In `_build_caches()`, when reading provenance metadata, reverse-resolve cache IDs to registry IDs before calling `get_source()`, `get_collection()`, `get_source_url()`. Use the same alias resolution that the edit routes use.

### BUG 3: Face Cards — Multi-Face Review UX
- **User clarification:** The issue is NOT layout (grid renders correctly). The issue is that when an identity has 31 faces (like Roland Fox), the face card on browse/people pages shows only ONE thumbnail. There needs to be a way within the UX to review/browse the different faces, not just the default one shown.
- **Current behavior:** Identity cards show a single hero crop. The "Faces (31)" button navigates to a gallery, but individual face cards don't let you cycle through faces.
- **Fix:** Add face count badge + cycling/expansion on identity cards, or a mini-gallery within the card.

### BUG 4: Person → Photo Wrong Landing
- **Issue:** Clicking from a person page to a photo sometimes lands on a photo where that person is NOT tagged.
- **Examples mentioned:** Rica Revah → Jacob Franco photo, Jacob Cohen
- **Needs investigation in continuation context.**

## Full Dogfood Issue List (26 items)
See `docs/assessments/session-100b-audit.md` for full list. Top priorities:
1. Jacob Cohen overlay (BUG 1 above)
2. Photo metadata save (BUG 2 above)
3. Face card multi-face review (BUG 3 above)
4. Person → photo wrong landing (BUG 4 above)
5. Photo overlays obscure caption text
6. Multi-face tagging still too painful
7. Neutral root incomplete
8. ROADMAP/CHANGELOG updates for sessions 97-100

## Agent Comparison (documented in memory)
- Codex: Fast breadth, degrades after ~6h, misses data integrity
- Antigravity: Good design critic, Session 99 UI variant approach
- Claude Code: Best for data integrity and verification
- Optimal: Codex implements → Claude Code audits

## Git State
- Branch: main, clean (all pushed)
- Latest commit: 23b78e4
- Tests: 4137 app + 590 ML pass
