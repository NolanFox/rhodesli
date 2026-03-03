# Session 84: Unified Face Cards + Restore Find Similar

**Date:** 2026-03-02
**Version:** v0.86.1
**Predecessor:** Session 83a (docs/sessions/SESSION_083a.md)

## Summary
Unified all face cards across admin sections. Browse grid now uses the same `identity_card()` component as People/Confirmed sections, restoring Photos, Share, quality, multi-face gallery, and the full Find Similar panel with Select All, Merge Selected, Not Same Selected, Load More, Manual Search, and Rejected Matches.

## Phase Checklist
- [x] Phase 1: Add show_triage param to identity_card()
- [x] Phase 2: Wire Find Similar to full neighbors_sidebar
- [x] Phase 3: Replace compact cards in browse grid
- [x] Phase 4: Expand share button to all states
- [x] Phase 5: Deprecate identity_card_compact()
- [x] Phase 6: Card expansion animation CSS
- [x] Phase 7: Update tests (25 total, up from 10)
- [x] Phase 8: Fix Help Identify expansion panel width

## Changes
1. **identity_card(show_triage=True)** — New param adds labeled Confirm/Skip/Reject pill buttons
2. **Find Similar -> full neighbors_sidebar()** — Admin Similar button loads complete panel with bulk actions, search, pagination
3. **neighbors_sidebar(container_id)** — New param for browse expansion panel targeting
4. **Share on all named identities** — Removed CONFIRMED-only restriction
5. **identity_card_compact() deprecated** — Delegates to identity_card(show_triage=True)
6. **Card highlight animation** — .find-similar-active CSS class with gold border + scale
7. **Help Identify expansion panel** — Moved outside wrapper div for full-width grid span

## Files Modified
- `app/main.py` — identity_card, neighbors_sidebar, browse grid, expansion panel CSS
- `tests/test_inline_find_similar.py` — 25 tests (15 new)

## Decision Log
- DD-006: Unified Face Cards + Full Find Similar Panel (docs/DESIGN_DECISIONS.md)

## Test Results
- 25/25 inline find similar tests PASS
- 551/551 ML tests PASS
- Pre-existing xdist flakes (not related)

## Browser Verification
- New Matches browse: unified cards + full neighbors panel PASS
- Help Identify browse: expansion panel fixed to span full width
- People section: unchanged, consistent PASS

## Deferred to Future Sessions
- Remove legacy /api/find-similar/{id} endpoint (cleanup)
