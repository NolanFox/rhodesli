# Session 106b Log — Triage Fix Sprint (FB-001 through FB-012)
Started: 2026-03-16
Prompt: docs/prompts/session-106b-prompt.md

## Phase Checklist
- [x] Phase 0: Orient + Plan
- [x] Phase 1: Photo Search by Filename (FB-007)
- [x] Phase 2: Match View Fixes (FB-001, FB-002, FB-003, FB-006)
- [x] Phase 3: Reciprocal Rank Indicator (FB-008, FB-011)
- [x] Phase 4: P2 Items → BACKLOG
- [x] Phase 5: Deploy + Browser Verify
- [x] Phase 6: Assessment + Session Close

## Phase 0: Orient + Plan
- Read all 12 feedback items, context file, lessons
- Planned each P1 fix with files, tests, risks
- Commit: 60839f7

## Phase 1: Photo Search by Filename (FB-007)
- Added filename matching fallback in `_search_photos()` (app/main.py:2130-2142)
- Searches `_photo_cache` filename when `searchable_text` doesn't match
- match_reason = "filename" shown in UI as yellow "Matched: filename" badge
- 5 new tests in test_discovery_layer.py
- Browser verified: "Image 001" search returns 1 result on production
- Commit: bb1229b

## Phase 2: Match View Fixes (FB-001, FB-002, FB-003, FB-006)
- FB-001: Added `nav_prefix` to all URLs in match_facecompare_routes.py (photo modal, decide, skip)
- FB-002: Added source photo thumbnails below face crops using `get_photo_url()`
- FB-003: Added "View Photo" and "View Person" text links below each face card
- FB-006: Added hyperscript loading state to "Same Person" button (opacity-50 + "Merging..." + disabled)
- 4 new tests in test_match_mode.py
- Browser verified: all visible on production match view
- Commit: b5375a6

## Phase 3: Reciprocal Rank Indicator (FB-008, FB-011)
- FB-008: Compute reciprocal rank for each neighbor in find-similar API
  - Added to BOTH browse_routes.py and page_routes.py (duplicate endpoints)
  - Shows "Mutual #1" (green badge), "You're their #N", or "Not in top · #1 is Name"
  - Verified via curl: production API returns reciprocal-rank data
- FB-011: Upgraded compare context line styling from text-[11px] text-slate-500 to text-xs text-amber-400 font-medium
  - Added "Ranked #N for Name" alongside "best match" info
  - Added upload_rank computation in target_context building
- 2 new tests in test_inline_find_similar.py
- Commit: 9174a46

## Phase 4: P2 Items → BACKLOG
- Added 5 P2 items to BACKLOG.md: FB-004, FB-005, FB-009, FB-010, FB-012
- Updated feedback status in session-106-feedback.md: 7 FIXED, 5 BACKLOG
- Commit: 008e595

## Phase 5: Deploy + Browser Verify
- make test-fast: 2989 passed
- Deploy: `railway up` → SUCCESS with DOCKERFILE builder
- Browser verifications:
  - [x] Photos search "Image 001" → 1 result with "Matched: filename"
  - [x] Match view: source photos visible, View Photo/View Person links present
  - [x] Match view: community prefix in URLs (/c/fox-family/)
  - [x] Same Person button has loading state attributes
  - [x] Find Similar API: reciprocal-rank data in response (verified via curl)
  - [x] Compare tool: code deployed with prominent context styling

## Verification Gate
- [x] All phases re-checked against original prompt
- [x] Feature Reality Contract passed
