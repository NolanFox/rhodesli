# Session 96c Prompt — Community-Scoped Review + Cross-Community Identity Pipeline

## Context
- Fox Family archive has 636 photos, 1652 faces, but shows "0 identities" and no admin tools
- 35 faces auto-clustered to existing identities (27 Roland Fox, 4 Betty Capeluto, 1 Ray Franco, 3 others) but these identities are NOT tagged to Fox Family community
- `identity_communities` table is empty for Fox Family — root cause of all scoping failures
- `/admin/upload-review` cluster review page was built (Session 96b) but not linked from Fox Family sidebar
- Sidebar Review section HTML fix committed (session 96b continuation) but counts still 0
- CI fixed (venv creation in GitHub Actions workflow)
- **AD-216**: Photo-derived community identity sets (the architectural decision for this session)
- **Context file**: `docs/session_context/session-96c-context.md` (full research, gap analysis, user feedback)

## User Feedback (Nolan, verbatim)
1. "Any person in any photo in the community can cause a photo to show up in the review section"
2. "If there is a new photo of Roland Fox in the Rhodesli community, I should be able to review that photo in the Fox Family community"
3. "If I detach a false positive, they would no longer show up in the Fox Family community"
4. "There needs to be a way for someone to make that merge occur (even if by manual search)" — for Type 2 errors (missed matches)
5. "If that merge occurs, that person should show up in To Review in the future since they would be in both communities"
6. Ray Franco is a woman — correct all docs/code that say otherwise
7. Needs admin view for Fox Family — currently has no admin section, no upload review link

## Pre-Requisites
- Read `tasks/lessons.md` + `tasks/todo.md`
- Read `docs/session_context/session-96c-context.md` (full gap analysis + research)
- Read `docs/ml/ALGORITHMIC_DECISIONS.md` entries AD-213, AD-215, AD-216
- Set `.claude/current_session.txt` to `96c`

---

## Act 1: Orient + Fix Ray Franco Gender (5 min)

1. Confirm current state: `git log --oneline -5`, check deploy status
2. Verify Fox Family landing page shows "0 identities" (this is the bug we're fixing)
3. Grep for "Ray Franco" references that use male pronouns — fix to female
4. Log starting state in session log

**Commit:** `fix: correct Ray Franco gender references + session 96c orient`
**/clear**

---

## Act 2: Build Photo-Derived Community Identity Set (20 min)

This is the foundation — everything else depends on it. See AD-216.

### 2a. New function: `_get_community_relevant_identity_ids(community)`

Location: `app/main.py` near existing `_get_community_identity_ids()` (~line 558)

Logic:
1. If community is None or Rhodes/default → return None (no filter, same as today)
2. Get community photo IDs from `_get_community_photo_ids(community)` (existing function)
3. For each photo in that set, get face_ids from `_photo_cache` or `photo_index`
4. For each face_id, look up which identity owns it (check `anchor_ids` and `candidate_ids` in registry)
5. Return the set of identity IDs

Performance: Cache result with 60s TTL (same as community photo IDs). For 636 photos with ~1652 faces, this is fast.

### 2b. Replace `_get_community_identity_ids()` calls

Find all callers of `_get_community_identity_ids()` and replace with `_get_community_relevant_identity_ids()`:
- `_compute_sidebar_counts()` in main.py
- Command center filtering in `page_routes.py`
- Admin bar in main.py
- Community landing stats in `page_routes.py`
- Any other callers (grep to find all)

### 2c. Backfill `identity_communities` table

Write a one-time backfill that calls `add_identity_to_community()` for every identity in the photo-derived set for Fox Family. This populates the explicit tagging table for query performance.

### 2d. Wire `add_identity_to_community()` into clustering pipeline

In `core/auto_cluster.py` or wherever clustering adds a face to an identity: after adding the face, check if the face's photo belongs to a community different from the identity's primary community. If so, call `add_identity_to_community()` to cross-tag.

Also wire into `app/upload_routes.py:_background_ingest()` — after auto-clustering in the background, tag identities.

### Tests
- Test `_get_community_relevant_identity_ids()` returns correct set for Fox Family
- Test it returns None for Rhodes (no filter)
- Test it returns empty set for community with 0 photos
- Test it includes identities from candidate_ids (not just anchor_ids)
- Test cache invalidation after face detach

**Commit:** `feat: photo-derived community identity sets (AD-216)`
**/clear**

---

## Act 3: Fix Sidebar Counts + Enable Admin Section (15 min)

### 3a. Remove ML feature zeroing in `_compute_sidebar_counts()`

File: `app/main.py` ~line 2805-2810

Remove this block:
```python
if community_identity_ids is not None:
    proposal_count = 0
    pending_annotations = 0
    discovery_count = 0
```

Instead, compute proposals/discoveries/annotations using the photo-derived identity set to filter results.

### 3b. Enable Admin section for all communities

File: `app/main.py` ~line 4440-4459

Change:
```python
if (user and user.is_admin and is_rhodes)
```
To:
```python
if (user and user.is_admin)
```

The admin tools (Uploads, Approvals, Proposals, GEDCOM) should be available for any community an admin is viewing.

### 3c. Add Upload Review link to admin sidebar

Add a nav item linking to `/admin/upload-review` in the Admin section. This is the cluster review page built in Session 96b — it needs to be discoverable from the sidebar.

### 3d. Fix discoveries route sidebar counts

File: `app/discoveries_routes.py` ~line 103

Change `_compute_sidebar_counts(registry)` to `_compute_sidebar_counts(registry, community=community)` — the community variable is already extracted at line 94 but not passed.

### Tests
- Test Fox Family sidebar shows non-zero counts for to_review, skipped when identities exist
- Test Admin section renders for Fox Family admin
- Test Upload Review link appears in admin sidebar
- Test discoveries route passes community to sidebar counts

**Commit:** `feat: enable full sidebar for all communities — admin + ML features`
**/clear**

---

## Act 4: Make Discoveries Community-Aware (15 min)

### 4a. Add community parameter to `_compute_discoveries()`

File: `app/main.py` ~line 6158

Add optional `community_identity_ids: set | None = None` parameter. When provided, filter:
- Source identities (INBOX/PROPOSED) to only those in the community set
- Target identities (CONFIRMED) remain global — we want to find matches against ALL confirmed, not just community-scoped
- But only return pairs where the source OR target is in the community set

This ensures: if a Fox Family face matches a Rhodes-confirmed Betty, it appears in Fox Family discoveries.

### 4b. Wire into discoveries route

File: `app/discoveries_routes.py`

Pass the photo-derived identity set to `_compute_discoveries()`.

### Tests
- Test discoveries with community filter returns only community-relevant matches
- Test discoveries with None filter returns all (Rhodes behavior unchanged)
- Test cross-community match appears (Fox Family face → Rhodes confirmed identity)

**Commit:** `feat: community-aware discoveries pipeline`
**/clear**

---

## Act 5: Verify Cross-Community Search + Manual Merge Path (10 min)

This covers the Type 2 error scenario: a missed match that needs manual correction.

### 5a. Verify search is global

Test that searching for an identity name on a Fox Family page returns Rhodes identities too. The merge workflow depends on this.

Check:
- `/api/search?q=Albert` from Fox Family context — does it return Rhodes identities?
- Person page merge search — does it search all communities?
- Admin identity search — is it global?

If search is community-scoped, fix it to be global. Merges MUST work across communities.

### 5b. Verify merge creates cross-community links

After merging two identities where one has Fox Family faces and the other has Rhodes faces, verify:
- The merged identity appears in BOTH communities' photo-derived sets
- The merged identity appears in BOTH sidebars

### 5c. Document the Type 2 error correction workflow

Add a note to the cluster review page or help text explaining: "Don't see someone? Search across all communities and merge to link them."

### Tests
- Test search API returns identities from all communities
- Test merge of cross-community identities updates both community sets

**Commit:** `feat: verify cross-community search + merge path for missed matches`
**/clear**

---

## Act 6: Fix Fox Family Landing Page + Browser Verify (15 min)

### 6a. Fix "0 identities" on Fox Family landing page

File: `app/page_routes.py` ~line 304-451 (`_community_landing_page()`)

The identity count uses `load_identities_for_community()` which queries `identity_communities`. After the Act 2 backfill, this should show the correct count. Verify it works.

If the backfill didn't populate `identity_communities` yet (e.g., the function uses photo-derived set instead), ensure the landing page also uses the photo-derived set for its count.

### 6b. Browser verification (MANDATORY)

Using Claude Chrome browser (admin is logged in):

1. **Fox Family landing page** `/c/fox-family/` — should show 636 photos + N identities (not 0)
2. **Fox Family sidebar** — should show Review section with non-zero counts
3. **Fox Family admin section** — should show Admin tools (Uploads, GEDCOM, etc.)
4. **Fox Family photos page** `/c/fox-family/?section=photos` — should show photo grid
5. **Fox Family To Review** `/c/fox-family/?section=to_review` — should show pending matches
6. **Upload Review page** `/admin/upload-review` — should show 35 cluster matches
7. **Search across communities** — search for a Rhodes identity from Fox Family context
8. **Rhodes sidebar** — verify nothing broke (still shows all sections with correct counts)

Save screenshots to `docs/screenshots/session-96c/`

### Tests
- Run `make test-fast` — all pass
- Run ML tests if any ML code was modified

**Commit:** `fix: Fox Family landing page identity count + browser verified`
**/clear**

---

## Act 7: Assessment + Session Wrap (10 min)

1. Re-read THIS PROMPT from disk: `cat docs/prompts/session-96c-prompt.md`
2. For each act, verify completion with evidence (file exists, test passes, screenshot taken)
3. Write `docs/assessments/session-96c-assessment.md` using standard template
4. Update:
   - `CHANGELOG.md` — new version entry
   - `ROADMAP.md` — check COMMUNITY-003 box, update Recently Completed
   - `docs/BACKLOG.md` — update status for community scoping items
   - `docs/session_logs/session-96b-log.md` — mark Act 8 complete (this session is its continuation)
5. Create `docs/session_logs/session-96c-log.md` with per-act status
6. Final `make test-fast` — must pass

**Commit:** `docs: session 96c assessment — community-scoped review pipeline shipped`

---

## Verification Gate (run before declaring done)

For each feature built:

| Check | Method | Expected |
|-------|--------|----------|
| Photo-derived identity set works | Unit test | Returns Betty, Roland for Fox Family |
| Fox Family sidebar counts non-zero | Browser screenshot | to_review > 0, skipped > 0 |
| Admin section visible for Fox Family | Browser screenshot | Shows Uploads, GEDCOM, etc. |
| Upload Review accessible from sidebar | Browser click-through | /admin/upload-review loads with matches |
| Cross-community search works | Browser test | Search "Betty" from Fox Family finds Rhodes identity |
| Fox Family landing page shows identities | Browser screenshot | N identities, not 0 |
| Rhodes sidebar unchanged | Browser screenshot | All counts correct |
| Discoveries community-aware | Unit test | Fox Family face → Rhodes confirmed = appears |
| Ray Franco gender corrected | Grep | No male pronouns for Ray Franco |
| CI passes | GitHub Actions | Green check on push |

## Output Requirements (Mandatory)

Every session MUST produce before final commit:
1. `docs/assessments/session-96c-assessment.md` — per-act evaluation with evidence
2. Updated `CHANGELOG.md`, `ROADMAP.md`, `BACKLOG.md`
3. Updated session log
4. Screenshots in `docs/screenshots/session-96c/`
5. All tests pass (`make test-fast`)

## Key Files Reference

| File | What to change |
|------|---------------|
| `app/main.py:558` | New `_get_community_relevant_identity_ids()` |
| `app/main.py:2805` | Remove ML feature zeroing for non-Rhodes |
| `app/main.py:4440` | Remove `is_rhodes` gate on Admin section |
| `app/main.py:6158` | Add community parameter to `_compute_discoveries()` |
| `app/page_routes.py:1779` | Use photo-derived identity set |
| `app/page_routes.py:304` | Fix landing page identity count |
| `app/discoveries_routes.py:103` | Pass community to sidebar counts |
| `app/supabase_data.py:1390` | Wire `add_identity_to_community()` into pipelines |
| `app/cluster_review_routes.py` | Verify accessible from sidebar |
| `core/auto_cluster.py` | Auto-tag identity_communities on cross-community match |
| `app/upload_routes.py` | Tag identities after background ingest clustering |
