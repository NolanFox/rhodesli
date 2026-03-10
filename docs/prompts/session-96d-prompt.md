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

## Act 6: Browser Verification (ALL 10 checks)
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

### Rhodes (`/`)
8. Sidebar counts unchanged/correct
9. Discoveries still work
10. No regressions

## Act 7: Session Wrap
1. Update `docs/session_logs/session-96d-log.md` with all acts
2. Write `docs/assessments/session-96d-assessment.md` with PASS/FAIL per check
3. Add Lessons 108-110 to `tasks/lessons/harness-lessons.md`
4. Update BACKLOG: mark COMMUNITY-007 through COMMUNITY-013 as DONE
5. Update ROADMAP: add session 96d to Recently Completed
6. Update CHANGELOG with v0.97.3

## Verification Gate
- ALL 10 browser checks PASS
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
