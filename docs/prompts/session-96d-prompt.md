# Session 96d Prompt — Fix Fox Family to Usable State

**Context:** `docs/session_context/session-96d-context.md`
**Priority:** P0 — User blocked, Fox Family "totally unusable"
**Scope:** Fix ALL 7 COMMUNITY bugs. No deferrals. Browser-verify every fix.

---

## Act 0: Orient (3 min)
Read these files to understand current state:
- `docs/session_context/session-96d-context.md` (full context with architecture notes)
- `docs/BACKLOG.md` (COMMUNITY-007 through COMMUNITY-013)
- `tasks/lessons.md` (index — check lessons 108-110)
- `app/main.py` — search for `sidebar()` and `_compute_sidebar_counts()`
- `app/page_routes.py` — search for bottom nav and `render_to_review_section`
- `app/cluster_review_routes.py` — search for `_load_proposals`

Set `.claude/current_session.txt` to `96d`.

## Act 1: Sidebar Counts + Proposals (COMMUNITY-007, COMMUNITY-010)
**Goal:** Fox Family sidebar shows correct community-scoped counts AND proposals count.

1. In `_compute_sidebar_counts()`, add `community_identity_ids` parameter
2. Filter identity lists (inbox, proposed, confirmed) by community set before counting
3. Wire proposals count: read `proposals.json`, filter by community identity set, show in sidebar
4. In `sidebar()`, pass community context to `_compute_sidebar_counts()`
5. Test: verify Fox sidebar shows Fox-only counts, Rhodes sidebar unchanged

Commit after this act. /clear.

## Act 2: Bottom Nav + Admin Headers (COMMUNITY-008, COMMUNITY-013)
**Goal:** Bottom nav uses community prefix. Admin pages show community name.

1. Find bottom nav generation (likely in `page_routes.py` or `main.py`)
2. Add `community_url_prefix()` to all bottom nav links
3. Find admin page header rendering
4. Pass `community.name` or `community.landing_title` to admin page headers
5. Test: Fox Family bottom nav links go to `/c/fox-family/...`, admin shows "Fox Family Archive"

Commit after this act. /clear.

## Act 3: Upload Review + GEDCOM in Sidebar (COMMUNITY-009)
**Goal:** Upload Review and GEDCOM triage pages are discoverable in Fox Family sidebar.

1. Check `sidebar()` function — are Upload Review and GEDCOM already there?
2. If not, add sidebar links with community prefix
3. Verify they appear for Fox Family (and Rhodes)

Commit after this act. /clear.

## Act 4: Cluster Review Community Scoping (COMMUNITY-011)
**Goal:** `/admin/upload-review` shows only Fox Family proposals when viewed from Fox Family.

1. In `cluster_review_routes.py`, add `request` parameter to GET handler
2. Read `request.state.community` and get community identity set
3. Filter proposals by community: source or target identity must be in community set
4. Test: Fox Family upload-review shows ~35 proposals, Rhodes shows Rhodes proposals

Commit after this act. /clear.

## Act 5: To Review Proposal Match Info (COMMUNITY-012)
**Goal:** Faces with proposals show match info on their cards in To Review.

1. In `render_to_review_section()` (or identity card renderer), check if identity has proposals
2. Load proposals once at section render time, build lookup: `source_identity_id → proposal`
3. On card, show match badge: "Matches [Name] ([confidence]%)" with link to target identity
4. Style: small badge below the identity name, green/blue for high/medium confidence
5. Test: Fox Family To Review shows "Matches Roland Fox" on matched faces

Commit after this act. /clear.

## Act 6: Cross-Community Content Indicator (COMMUNITY-014)
**Goal:** When viewing Fox Family, any photo/face from another community is clearly marked.

This is critical UX feedback from Nolan. When a Fox Family person matches a Rhodes photo:
1. Photo Context modal must show "From Rhodes" badge (community name + icon)
2. Photo Context modal must link to the full photo page (`/photo/{photo_id}`)
3. ALL detected faces in the photo must be labeled with identity name + clickable (link to person page)
4. Cross-community links should say "View in Rhodes" or navigate to `/c/rhodes/photo/...`
5. Apply the same badge to discovery cards and identity cards when showing cross-community faces
6. Check: Which photos belong to which community? Use `_get_community_photo_ids()` — if photo NOT in current community's set, it's cross-community

**Files:** Photo Context modal (search for "Photo Context" in main.py/page_routes.py), identity card renderer, discovery card builder.

Commit after this act. /clear.

## Act 7: Browser Verification (ALL 12 checks)
**Goal:** Every fix verified in production browser. Screenshots optional but evidence required.

Navigate to each URL in Claude Chrome and verify:

### Fox Family (`/c/fox-family/`)
1. Sidebar counts are Fox-only (not global)
2. Bottom nav links include `/c/fox-family/` prefix
3. Proposals count shows correct number (not 0)
4. Upload Review + GEDCOM visible in sidebar
5. To Review cards show proposal match info
6. Admin pages show "Fox Family Archive" header
7. Discoveries shows Betty Capeluto and Ray Franco matches
8. Cross-community photos show "From Rhodes" badge
9. Photo Context modal links to full photo page with all faces labeled

### Rhodes (`/`)
10. Sidebar counts unchanged/correct
11. Discoveries still work
12. No regressions

## Act 8: Session Wrap
1. Update `docs/session_logs/session-96d-log.md` with all acts
2. Write `docs/assessments/session-96d-assessment.md` with PASS/FAIL per check
3. Lessons 108-110 already added (session 96c-cont4)
4. Update BACKLOG: mark COMMUNITY-007 through COMMUNITY-014 as DONE
5. Update ROADMAP: add session 96d to Recently Completed
6. Update CHANGELOG with v0.97.3

## Verification Gate
- ALL 12 browser checks PASS
- ALL tests pass (excluding pre-existing 4 failures)
- Git clean, all changes committed and pushed
- Assessment file exists with evidence
- BACKLOG updated
- Lessons logged

## Anti-Patterns to Avoid
- Do NOT defer any of the 7 COMMUNITY bugs — fix them all
- Do NOT declare PASS without browser verification
- Do NOT filter confirmed_list by community (breaks cross-community matching — Lesson 108)
- Do NOT forget that /api/ paths bypass CommunityMiddleware (Lesson 109)
- /clear between every act commit — NO EXCEPTIONS
