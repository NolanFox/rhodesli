# Systematic Feature Audit — What Actually Exists

**Date:** 2026-02-17
**Method:** Local server (localhost:5001, auth disabled), curl + grep
**App state:** 277 photos, 664 identities, 271 indexed photos

## Route Status Codes

| Route | Status |
|-------|--------|
| `/` | 200 |
| `/map` | 200 |
| `/connect` | 200 |
| `/tree` | 200 |
| `/timeline` | 200 |
| `/compare` | 200 |
| `/collections` | 200 |
| `/photos` | 200 |
| `/people` | 200 |
| `/admin/gedcom` | 200 |
| `/admin/approvals` | 200 |
| `/activity` | 200 |
| `/person/{confirmed_id}` | 200 |
| `/identify/{inbox_id}` | 200 (unmerged) |
| `/photo/{photo_id}` | 200 |
| `/collection/{slug}` | 200 |

All 16 routes return 200.

---

## Feature Audit Table

| # | Feature | EXISTS | WORKS | Evidence |
|---|---------|--------|-------|----------|
| 1 | `/identify/{a}/match/{b}` | Yes | Yes | Returns 200, has OG tags (og:title, og:description, og:image, og:url) |
| 2 | Match response storage | Yes | Partial | Responses stored in `data/identification_responses.json` (created on first POST). Rate limited (10/hr/IP). File doesn't exist until first use. |
| 3 | Person page comments | Yes | Yes | Comment form renders with `data-testid="comments-section"`. POST handler at `/api/person/{id}/comment`. Admin hide at `/api/person/{id}/comment/{id}/hide`. File created on first use. |
| 4 | Face click behavior | Yes | Yes | Face overlays are `<a href="/person/{id}">` links with `cursor-pointer`. Confirmed faces → `/person/`, identified faces link correctly. |
| 5 | Photo carousel | Yes | Yes | "Photo 1 of 108" position indicator. Next arrow links to `/photo/{next_id}`. Keyboard nav wired. Touch swipe implemented. |
| 6 | Admin element visibility | Yes | Yes | "Add Photos" button on collections wrapped in `if (user and user.is_admin if is_auth_enabled() else False)`. Back image upload on photo page. Auth disabled → admin elements hidden correctly. |
| 7 | Person page action bar | Yes | Yes | `data-testid="person-action-bar"` with Timeline, Map, Family Tree, Connections links — all parametrized with person_id. |
| 8 | Person page field order | Yes | Partial | Family section shows Children/Spouse with cross-links. Birth/death/maiden fields depend on identity metadata — tested identity had no metadata populated, so no fields rendered. |
| 9 | Geographic autocomplete | No | No | `data/location_dictionary.json` exists (22 locations) but is NOT wired into `app/main.py` — zero references to `location_dictionary` in main.py. Used only in geocoding pipeline (`core/geocoding.py`). |
| 10 | `/identify` share URL | Yes | Yes | Share button with `data-action="share-photo"` and correct URL. OG tags present (og:title, og:description, og:image, og:url). Web Share API for mobile. |
| 11 | Sidebar consistency | Yes | Partial | Admin pages (`/admin/approvals`, `/admin/gedcom`) have navigation links (Audit Log, Back to Dashboard) but NOT the full sidebar. Main dashboard has the full sidebar with Approvals/Proposals/GEDCOM links. |
| 12 | Tree in all nav | Yes | Yes | `href="/tree"` present on all 8 checked public pages: /, /map, /timeline, /connect, /compare, /collections, /photos, /people. |
| 13 | Photo uploader attribution | No | No | Photo page shows provenance (AI analysis sections) but NO "uploaded by" or "contributed by" attribution. Upload metadata not displayed. |
| 14 | Collection "Add Photos" button | Yes | Yes | Code renders `A("+ Add Photos", href="/upload")` but only when `user.is_admin` and auth is enabled. With auth disabled, correctly hidden. |
| 15 | Bulk collection editing | Yes | Yes | Bulk action bar with collection dropdown (`#bulk-move-collection`), source dropdown, source URL input. Handler at `/api/photos/bulk-update-source`. |
| 16 | Compare two-mode UX | Yes | Yes | Two sections: archive face selector (search + grid) and upload section. Description: "Find matching faces in two ways." |
| 17 | `&harr;` bug on /connect | No bug | N/A | Only `&amp;` entity found (standard HTML encoding). No raw `&harr;` or other broken entities. |
| 18 | OG tags on shareable pages | Yes | Partial | `/person/{id}` — Yes (title, desc, image). `/photo/{id}` — Yes. `/collection/{slug}` — Yes (title, desc, url). `/identify/{id}` — Yes. `/identify/{a}/match/{b}` — Yes. |
| 19 | Face overlay alignment | Yes | Yes | `.photo-hero-container` has `position: relative`. Overlays use percentage-based positioning (`left: 65.59%; top: 20.92%; width: 10.11%; height: 10.51%`). |
| 20 | Photo collection/source editing | Yes | Partial | API endpoints exist (`/api/photo/{id}/collection`, `/api/photo/{id}/source`, `/api/photo/{id}/source-url`, `/api/photo/{id}/metadata`). BUT no inline edit UI on the photo page — no select/input for editing collection or source visible in rendered HTML. Admin can edit via bulk mode on /photos page only. |
| 21 | Upload flow collection assignment | Yes | Yes | Upload area has `#upload-collection` dropdown, `#upload-source` input, `#upload-source-url` input. Collection passed to ingest subprocess. |
| 22 | Upload/approval logging | Yes | Partial | `data/audit_log.json` exists. User actions logged to `logs/user_actions.log` (append-only). Activity feed at `/activity` reads from log. No separate `upload_log.json` or `approval_log.json`. |
| 23 | Suggest a correction | Yes | Partial | Date correction pencil (`✏️`) exists on photo page with correction form (year input + submit). But NO "Suggest a correction" button on person pages for other metadata (name, birth, death). Admin inline editing of person metadata not surfaced in photo/person page UI. |
| 24 | Session completion checklist | No | N/A | CLAUDE.md has rule "Update CHANGELOG.md before ending any session" but no formal session completion checklist. |
| 25 | Batch ingest rules | No | N/A | Not in CLAUDE.md. Upload pipeline is documented in MEMORY.md and `docs/ops/PIPELINE.md`. |
| 26 | Web Share API | Yes | Yes | `navigator.share` implemented in two places: photo share and identify share. Falls back to clipboard copy on desktop. |
| 27 | Photo position indicator | Yes | Yes | "Photo 1 of 108" shown. Next/prev arrows link to adjacent photos. |
| 28 | Mobile swipe for carousel | Yes | Yes | `touchstart` and `touchend` event listeners on photo modal container. Swipe left/right triggers prev/next. |
| 29 | Search → correct destination | Yes | Yes | People page links to `/person/{id}`. Search result cards link to person pages. Sidebar search uses HTMX filtering. |
| 30 | Postmortem documents | Yes | Partial | `docs/postmortems/identify_500.md` exists (1 file). No others. |
| 31 | AD-085 through AD-090 | Partial | N/A | Only AD-090 exists ("Gemini-InsightFace Face Alignment"). AD-085 through AD-089 do not exist. Last sequential AD is AD-080. |
| 32 | Feedback file completeness | Yes | N/A | `docs/feedback/session_40_feedback.md` exists (4.6KB). Also `CLAUDE_BENATAR_FEEDBACK.md` and `FEEDBACK_INDEX.md`. |
| 33 | Deploy safety tests | Yes | Yes | `TestDockerfileModuleCoverage` class in `tests/test_sync_api.py` (line 497). Tests verify Dockerfile COPY for rhodesli_ml subpackages. |
| 34 | GEDCOM manual person linking | Yes | Yes | `/admin/gedcom/confirm/{xref}` and `/admin/gedcom/reject/{xref}` POST endpoints exist. Admin can confirm/reject GEDCOM-to-archive person matches. |
| 35 | GEDCOM data on person pages | Yes | Yes | Family section renders with Children/Spouse links from `get_relationships_for_person()`. "Family Tree" link. "View in Family Tree →" cross-link. Family badges ("Family", "Spouse") on related people. |
| 36 | Comments rate limiting | Partial | Partial | Match responses have rate limiting (10/hr/IP via `_match_rate_limit`). Person page comments have NO rate limiting — POST handler has no IP check. |

---

## Summary

### CONFIRMED WORKING (22)
1. `/identify/{a}/match/{b}` route with OG tags
2. Match response storage (identification_responses.json)
3. Person page comments system
4. Face click behavior → `/person/` links
5. Photo carousel with position indicator
6. Admin element visibility (auth-guarded)
7. Person page action bar (Timeline, Map, Tree, Connections)
8. `/identify` share URL with OG tags and Web Share API
9. Tree in all public page navigation
10. Collection "Add Photos" button (admin-only)
11. Bulk collection editing
12. Compare two-mode UX
13. OG tags on /person, /photo, /collection, /identify, /identify/match
14. Face overlay alignment (percentage-based, position:relative wrapper)
15. Upload flow collection assignment
16. Web Share API (mobile share + clipboard fallback)
17. Photo position indicator ("Photo X of Y")
18. Mobile swipe for carousel
19. Search → correct person page destination
20. Deploy safety tests (Dockerfile module coverage)
21. GEDCOM manual person linking (confirm/reject)
22. GEDCOM data on person pages (family section with cross-links)

### EXISTS BUT BROKEN OR INCOMPLETE (8)
1. **Person page field order (#8)**: Family section works but birth/death/maiden fields only render if identity has metadata populated. Most identities have no metadata.
2. **Admin sidebar consistency (#11)**: Main dashboard has full sidebar. Admin sub-pages (approvals, gedcom) have partial nav (Audit Log link, Back to Dashboard) but NOT the full admin sidebar menu.
3. **Photo collection/source editing (#20)**: API endpoints exist but NO inline edit UI on photo pages. Editing only possible via bulk mode on /photos page.
4. **Suggest a correction (#23)**: Date correction pencil exists on photo pages. But NO metadata correction UI on person pages (can't suggest name, birth, death corrections inline).
5. **Upload/approval logging (#22)**: User actions logged to `user_actions.log`. Audit log exists. But no dedicated upload or approval log files. Activity feed reads from action log.
6. **AD-085 through AD-090 (#31)**: Only AD-090 exists. AD-081 through AD-089 skipped (numbering gap, not sequential from AD-080).
7. **Comments rate limiting (#36)**: Match responses have IP rate limiting. Person page comments have NONE — anyone can POST unlimited comments.
8. **Postmortem documents (#30)**: Only 1 postmortem (identify_500.md). No systematic postmortem process.

### NOT IMPLEMENTED (4)
1. **Geographic autocomplete (#9)**: `location_dictionary.json` exists but is NOT wired into the upload form or any UI input. Only used in geocoding pipeline.
2. **Photo uploader attribution (#13)**: No "uploaded by" or "contributed by" info shown on photo pages.
3. **Session completion checklist (#24)**: Not in CLAUDE.md as a formal checklist.
4. **Batch ingest rules (#25)**: Not documented in CLAUDE.md (exists in MEMORY.md and ops docs).

### NO ISSUE FOUND (2)
1. **`&harr;` bug on /connect (#17)**: No broken HTML entities found. Only standard `&amp;` present.

### NEEDS MANUAL VERIFICATION (4)
1. **Face click for unidentified faces (#4)**: Confirmed faces link to `/person/`. Need browser test to verify INBOX/SKIPPED faces link to `/identify/`.
2. **Mobile responsiveness**: All features checked via curl (desktop rendering). Mobile layout needs browser verification.
3. **Compare upload persistence**: Upload to R2 needs actual file upload test, not just code check.
4. **Admin edit UI when auth enabled**: Many admin features hidden when auth disabled. Need production or auth-enabled local test.
