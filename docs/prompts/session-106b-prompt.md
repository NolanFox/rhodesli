# Session 106b — Triage Fix Sprint (FB-001 through FB-012)

**Context:** docs/session_context/session-106b-context.md
**Feedback source:** docs/session_context/session-106-feedback.md
**Priority:** P1 — fix all P1 feedback from Session 106 user triage
**Predecessor:** Session 106 (triage feedback collection)

## Overview

Session 106 was a user-driven triage session. Nolan identified Fox Family photos, cross-referenced with Google Photos, and collected 12 feedback items. This session fixes all 7 P1 items and logs 5 P2 items to BACKLOG.

**This session runs autonomously.** Every phase must:
- Plan before coding (understand existing code, identify blast radius)
- Write tests first (TDD — tests fail, then implement, then tests pass)
- Commit atomically per phase
- Run `make test-fast` before every commit
- /clear between phases

**Safety rules:**
- No data loss. No registry mutations without save guards.
- No modifications to `core/neighbors.py` (FROZEN).
- All URL generation must use `community_url_prefix()`.
- All HTMX endpoints must return proper status codes (401/403/404, not redirects).
- Read existing code before modifying. Understand what exists before changing it.

---

## Phase 0: Orient + Plan (10 min)

1. Set `.claude/current_session.txt` to `106b`
2. Set `.claude/session_mode.txt` to `implementation`
3. Read these files:
   - `docs/session_context/session-106-feedback.md` (all 12 feedback items)
   - `docs/session_context/session-106b-context.md` (context + risks)
   - `tasks/lessons.md` (lessons index)
4. Create session log: `docs/session_logs/session-106b-log.md`
5. Create assessment stub: `docs/assessments/session-106b-assessment.md`
6. **Plan each phase**: For each P1 item, read the relevant source code and document:
   - What file(s) need changes
   - What the current behavior is
   - What the fix is
   - What tests to write
   - What could go wrong
7. Commit scaffolding

/clear after committing.

---

## Phase 1: Photo Search by Filename (FB-007)

**Problem:** No way to search photos by filename in the Photos section. Nolan's workflow: get filename from Google Photos → search in Rhodesli. Currently broken.

### Plan
1. Read `app/main.py` `_search_photos()` (~line 2104) and `_load_search_index()` (~line 1631)
2. Check what fields are in `data/photo_search_index.json`
3. Determine if filename/path is already in the search index docs
4. If yes: add filename matching to `_search_photos()` alongside `searchable_text`
5. If no: add filename to the search index builder AND to `_search_photos()`

### Implementation
- In `_search_photos()`, after the `searchable_text` check, also check `doc.get("path", "")` or `doc.get("filename", "")` against the query
- Set `match_reason = "filename"` when matched this way
- This is the minimal fix — no search index rebuild needed if we search the path field directly

### Tests
- Test: searching "01984" returns the photo with path containing "01984"
- Test: searching "13akf5twbc5244" returns the same photo
- Test: searching a non-existent filename returns no results
- Test: existing text search still works (regression)

### Acceptance
Searching "01984" or "13akf5twbc5244" in Photos search box finds the photo.

/clear after committing.

---

## Phase 2: Match View Fixes (FB-001, FB-002, FB-003, FB-006)

**Problem:** Multiple issues with the speed-run match view at `/c/{community}/?section=to_review&view=match`.

### Plan
1. Find the match view rendering code — likely in `app/cluster_review_routes.py` or `app/page_routes.py`
2. Grep for `view=match` or `match_view` to find the entry point
3. Read the relevant rendering functions

### FB-001: Photo button missing community prefix
- Find the "Click to view photo" button/link
- Ensure URL uses `community_url_prefix()` or `nav_prefix`
- Test: verify generated HTML includes `/c/fox-family/` prefix

### FB-002: Show source photos side-by-side
- Current: only face crops shown
- Fix: add source photo thumbnails (small, ~120px) next to each face crop
- Use `get_photo_url()` to get the source photo URL
- Use photo_registry to look up which photo each face belongs to

### FB-003: Clickable photo + person links
- Each face card needs:
  - Link to photo page: `{nav_prefix}/photo/{photo_id}`
  - Link to person page: `{nav_prefix}/person/{identity_id}`
- Small link icons or text links below the face crop

### FB-006: Loading feedback on "Same Person"
- Add `hx-indicator` with a spinner, OR
- Use hyperscript: `on click add .opacity-50 to me then put 'Merging...' into me`
- Button should disable itself on click to prevent double-submit

### Tests
- Test: match view HTML contains community-prefixed photo URLs
- Test: match view HTML contains source photo elements
- Test: match view HTML contains person page links
- Test: "Same Person" button has loading indicator attributes

/clear after committing.

---

## Phase 3: Reciprocal Rank Indicator (FB-008, FB-011)

**Problem:** When viewing matches, you can't tell if the match is mutual. This is critical for identification — mutual #1 matches are strong signals, asymmetric matches suggest the face is actually another photo of the dominant match person.

### Plan
1. Read `app/page_routes.py` find-similar handler (~line 7332)
2. Read `core/neighbors.py` `find_nearest_neighbors()` API (READ ONLY, don't modify)
3. Understand how neighbors are computed and cached
4. Design the reciprocal rank lookup

### Implementation — Find Similar Panel
1. In the find-similar API handler, after getting neighbors for the source identity:
2. For each neighbor N, compute reciprocal rank:
   - Call `find_nearest_neighbors(N.identity_id, registry, photo_registry, face_data, limit=12)`
   - Search the result list for the source identity_id
   - Record the rank (1-indexed) or None if not in top 12
3. Add to neighbor data: `reciprocal_rank`, `reciprocal_best_name`, `is_mutual_top`
4. Render in the tile:
   - Green badge: "Mutual #1" if both are each other's #1
   - Neutral text: "You're their #3 match"
   - Warning text: "Not in their top matches" with who their #1 actually is

### Implementation — Compare Tool
1. In `app/compare_routes.py`, find where "best is X%" text is rendered
2. Make it more prominent: larger font, positioned above the score bar, colored by strength
3. Add rank info: "Ranked #N for this person" alongside the existing "best is" text

### Performance
- `find_nearest_neighbors` for 12 neighbors ≈ 12 × ~50ms = ~600ms
- Acceptable for admin-only tool
- Consider caching: the identity_routes already has a TTL cache (`NEIGHBORS_CACHE`)
- Use that cache if available, otherwise compute fresh

### Tests
- Test: find-similar API response includes reciprocal_rank data
- Test: mutual top-1 matches get "Mutual #1" indicator
- Test: non-mutual matches show correct rank text
- Test: compare results show prominent rank context

/clear after committing.

---

## Phase 4: P2 Items → BACKLOG (10 min)

Add these to `docs/BACKLOG.md` with breadcrumbs to `docs/session_context/session-106-feedback.md`:

| ID | Issue | Source |
|----|-------|--------|
| FB-004 | Consistent face crop ↔ source photo toggle across all views | Session 106 FB-004 |
| FB-005 | Raw internal IDs shown to users — use "Unknown Person" or clean numbers | Session 106 FB-005 |
| FB-009 | Compare search dropdown persists after person selection | Session 106 FB-009 |
| FB-010 | Compare tool shows all communities — needs community filter | Session 106 FB-010 |
| FB-012 | Compare tool UX doesn't help reach identification conclusions | Session 106 FB-012 |

Update `docs/session_context/session-106-feedback.md` status column for all items.

/clear after committing.

---

## Phase 5: Deploy + Browser Verify (15 min)

1. `make test-fast` — all pass
2. `make test-full` — all pass (run if time allows, otherwise test-fast is sufficient)
3. Deploy: `railway deploy`
4. Wait for deploy, verify DOCKERFILE builder via `mcp__railway-mcp-server__list-deployments`
5. Browser verify on production (use Claude Chrome — admin is logged in):
   - [ ] Photos section: search "01984" → finds the photo
   - [ ] Photos section: search "13akf5twbc5244" → finds the photo
   - [ ] Match view: photo button links have `/c/fox-family/` prefix
   - [ ] Match view: source photos visible alongside face crops
   - [ ] Match view: person page links work
   - [ ] "Same Person" button shows loading state
   - [ ] Find Similar panel: shows reciprocal rank info (e.g., "Mutual #1" or "Their #3 match")
   - [ ] Compare tool: rank context is prominent, not buried
6. Save screenshots to `docs/screenshots/session-106b/`

If any check fails: fix, re-deploy, re-verify. Do not skip.

---

## Phase 6: Assessment + Session Close (10 min)

1. Re-read this prompt (`docs/prompts/session-106b-prompt.md`) — verify every phase was completed
2. Write `docs/assessments/session-106b-assessment.md` with PASS/FAIL per phase + evidence
3. Update `docs/session_logs/session-106b-log.md` with actual results
4. Update `docs/session_context/session-106-feedback.md` — mark all fixed items as FIXED
5. Update `ROADMAP.md` — add session to Recently Completed
6. Update `BACKLOG.md` — P2 items added
7. Update `CHANGELOG.md` — new version entry
8. Final commit

---

## Key Files (read before modifying)
- `app/main.py` — `_search_photos()` (~2104), `_load_search_index()` (~1631)
- `app/page_routes.py` — find-similar panel (~7332), match view rendering
- `app/cluster_review_routes.py` — cluster review / speed-run
- `app/compare_routes.py` — compare results (5778 lines — targeted edits only)
- `core/neighbors.py` — `find_nearest_neighbors()` — **FROZEN, DO NOT MODIFY**
- `core/storage.py` — `get_photo_url()`, `get_crop_url()`
- `docs/session_context/session-106-feedback.md` — feedback source of truth

## Non-Goals
- No ML pipeline changes
- No architecture changes
- No modifications to `core/neighbors.py`
- P2 items go to BACKLOG only
- No refactoring of compare_routes.py
- No new PRDs needed (all fixes are < 30 min each)
