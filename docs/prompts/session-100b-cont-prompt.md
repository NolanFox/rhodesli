# Session 100b Continuation Prompt

**Read first:** `docs/session_context/session-100b-context.md` — has all research findings, root causes, and fix locations.

**Mission:** Fix ALL 26+ documented issues from Session 100 dogfood feedback. The user wants everything resolved before session end. Work through bugs in priority order, commit after each fix, push regularly.

## Phase 1: Fix Jacob Cohen Photo Overlay (BUG 1)
- **File:** `app/page_routes.py` in `public_photo_page()` function
- **Search for:** `bbox_conflict` — find where conflict display overrides identity name
- **Fix:** When BOTH conflicting faces are CONFIRMED, show their names (not "Needs review"). Only use "Needs review" for PROPOSED/INBOX faces with conflicts.
- **Also consider:** Raising IoU threshold from 0.80 to 0.85
- **Test:** Write test that CONFIRMED faces show names even with bbox overlap

## Phase 2: Fix Photo Metadata Save (BUG 2)
- **File:** `app/main.py` in `_build_caches()` function around lines 3854-3870
- **Root cause:** Cache iterates over SHA256 IDs but photo_registry stores under inbox-style IDs
- **Fix:** When reading `get_source()`, `get_collection()`, `get_source_url()` in cache building, reverse-resolve cache IDs to registry IDs using the same alias map the edit routes use
- **Test:** Write test that verifies metadata persists after cache rebuild

## Phase 3: Face Card Multi-Face UX (BUG 3)
- **User request:** Identity cards need a way to browse/review multiple faces, not just show one thumbnail
- **Current:** Cards show single hero crop with face count badge
- **Fix:** Add face cycling (prev/next arrows) or mini-gallery expansion on identity cards
- **Keep it simple:** Small arrows or dot indicators to cycle through faces on hover/click

## Phase 4: Person → Photo Wrong Landing (BUG 4)
- Investigate: When clicking a photo from person page, does the link use the correct photo_id?
- Check sort ordering and photo_id resolution in person_routes.py gallery

## Phase 5: Address Remaining Dogfood Issues
Read `docs/assessments/session-100b-audit.md` section on "Consolidated List of ALL Unfixed Issues" for the full 26-item list. For each:
- If fixable in <15min: fix it
- If architectural: document in BACKLOG with clear description
- If UX design needed: note for future session

## Phase 6: ROADMAP/CHANGELOG Updates
- Add session 97, 98, 99, 100 entries to CHANGELOG.md
- Update ROADMAP.md with session status
- Update SESSION_HISTORY.md

## Phase 7: Deploy + Browser Verify
- `git push origin main` (triggers Railway deploy)
- Verify via browser: Jacob Cohen photo, Roland Fox face cards, photo metadata save
- Take screenshots for evidence

## Verification Gate
- All 26 issues addressed (fixed or documented in BACKLOG)
- Both test suites pass
- Production browser verified
- Assessment updated
