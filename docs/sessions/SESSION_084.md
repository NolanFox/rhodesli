# Session 84: Unified Face Cards + Restore Find Similar

**Date:** 2026-03-02
**Version:** v0.86.1

## Summary
Unified all face cards across admin sections. Browse grid now uses the same `identity_card()` component as People/Confirmed sections, restoring Photos, Share, quality, multi-face gallery, and the full Find Similar panel with Select All, Merge Selected, Not Same Selected, Load More, Manual Search, and Rejected Matches.

## Changes
1. **identity_card(show_triage=True)** — New param adds labeled Confirm/Skip/Reject pill buttons visible on browse cards
2. **Find Similar → full neighbors_sidebar()** — Admin Similar button now loads the complete panel instead of simplified inline version
3. **neighbors_sidebar(container_id)** — New param allows targeting browse expansion panels; Load More, bulk actions, close button all work in browse context
4. **Share on all named identities** — Removed CONFIRMED-only restriction
5. **identity_card_compact() deprecated** — Now delegates to identity_card(show_triage=True)
6. **Card highlight animation** — CSS .find-similar-active class with gold border and subtle scale on Similar click
7. **25 tests** (up from 10) covering all new functionality

## Files Modified
- `app/main.py` — identity_card, neighbors_sidebar, browse grid, CSS
- `tests/test_inline_find_similar.py` — Expanded test coverage

## Test Results
- 25/25 inline find similar tests PASS
- 551/551 ML tests PASS
- xdist flakes pre-existing (not related to changes)
