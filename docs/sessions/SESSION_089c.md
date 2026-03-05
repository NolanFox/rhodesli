# Session 89c: Fix Re-analyze + Location ID Mismatch

**Date**: 2026-03-05
**Version**: v0.92.1
**Predecessor**: Session 89b

## Summary
Fixed 3 bugs blocking the re-analyze feature on the Leon's Restaurant photo (3192877a90a174e9):

1. **Photo location ID mismatch** — `_load_photo_locations()` now dual-keys inbox IDs to SHA256 IDs, matching the pattern in `_load_date_labels()`. Fixes inline Leaflet maps for all inbox-uploaded photos.

2. **Gemini 504 timeout** — Added retry logic (2 retries, 5s/15s backoff) for DEADLINE_EXCEEDED errors. GEDCOM timeout increased from 120s to 180s.

3. **Analysis metadata UX** — Model badge now shows timestamp and prompt version. "Run Face Analysis" renamed to "Detect Faces".

## Commits
- `2784387` docs(session): session 89c orient
- `bb2a223` fix(map): dual-key photo_locations for inbox IDs + rename Detect Faces button
- `2d060f8` fix(estimate): retry on Gemini timeout + analysis metadata in UI

## Tests
- 7 new tests (2 dual-keying, 3 retry logic, 2 model badge)
- All existing tests pass (1437+ app, 551 ML)

## Deferred
- Re-analyze Leon's Restaurant photo — deploy was building during session
- Browser verification of inline map + button rename — pending deploy

## Key Files Changed
- `app/main.py` — `_load_photo_locations()` dual-keying, model badge timestamp, button rename
- `app/estimate_routes.py` — retry logic, timeout increase, prompt_version storage
- `tests/test_location_ux.py` — 2 new dual-keying tests
- `tests/test_reanalyze.py` — 5 new tests (retry + model badge)
