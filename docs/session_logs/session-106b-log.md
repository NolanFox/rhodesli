# Session 106b Log — Triage Fix Sprint (FB-001 through FB-012)
Started: 2026-03-16
Prompt: docs/prompts/session-106b-prompt.md

## Phase Checklist
- [ ] Phase 0: Orient + Plan
- [ ] Phase 1: Photo Search by Filename (FB-007)
- [ ] Phase 2: Match View Fixes (FB-001, FB-002, FB-003, FB-006)
- [ ] Phase 3: Reciprocal Rank Indicator (FB-008, FB-011)
- [ ] Phase 4: P2 Items → BACKLOG
- [ ] Phase 5: Deploy + Browser Verify
- [ ] Phase 6: Assessment + Session Close

## Phase 0: Orient + Plan

### Plan per P1 item:

**FB-007 (Photo Search by Filename)**
- File: `app/main.py` `_search_photos()` line 2104
- Current: search only checks `searchable_text` field (Gemini descriptions)
- Fix: Also check photo path/filename from `_photo_cache` using `cache_photo_id` or `photo_id`
- Tests: search by partial filename, full filename, non-existent filename, regression for text search

**FB-001 (Match view photo button missing community prefix)**
- File: `app/match_facecompare_routes.py` line 250
- Current: `_fc_url = f"/photo/{photo_id}/partial?face={face_id}"` — no community prefix
- Fix: Add `nav_prefix` to the URL. Need to get community context in `_face_card` or pass it as param.
- Tests: verify match view HTML has community-prefixed URLs

**FB-002 (Show source photos side-by-side in match view)**
- File: `app/match_facecompare_routes.py` `_face_card()` line 241
- Current: shows only face crop, no source photo
- Fix: Add small source photo thumbnail below face crop using `get_photo_url()`
- Tests: match view HTML contains photo thumbnail img elements

**FB-003 (Clickable photo + person links in match view)**
- File: `app/match_facecompare_routes.py` `_face_card()` line 241
- Current: face card clickable to photo modal, but no visible links to photo/person pages
- Fix: Add text links "View Photo" and "View Person" below face info
- Tests: match view HTML contains person page links

**FB-006 (Loading feedback on "Same Person" button)**
- File: `app/match_facecompare_routes.py` line 309
- Current: button clicks with no feedback
- Fix: Add hyperscript `on click add .opacity-50 to me then put 'Merging...' into me`
- Tests: verify button has loading indicator attributes

**FB-008 (Reciprocal rank in Find Similar panel)**
- File: `app/page_routes.py` line 7332
- Current: shows neighbors but no reciprocal rank info
- Fix: For each neighbor, compute reverse neighbors and find source identity's rank
- Performance: ~12 × 50ms = 600ms, acceptable for admin tool
- Tests: find-similar response includes reciprocal rank data

**FB-011 (Compare tool rank context buried)**
- File: `app/compare_routes.py` line 4994-4998
- Current: context line is `text-[11px] text-slate-500` — buried
- Fix: Make it larger, colored, and positioned more prominently. Add rank text.
- Tests: compare results have prominent context styling

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
