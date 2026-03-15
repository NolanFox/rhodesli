# Session 102 — Performance, Speed Loop Fixes, Navigation Wiring, and Triage Sprint

## Predecessor
- Context: `docs/session_context/session-102-context.md`
- Feedback: `docs/feedback/2026-03-14-fox-triage-round2.md` (24 items, FB-120–FB-143)
- Prior context: `docs/session_context/session-101-context.md`
- Current: v0.99.3, 4276 tests, 3412 identities, 941 photos, ~86 confirmed

## Goal

Fix the three root problems exposed in the Session 101 triage sprint:
1. **Performance** — GEDCOM search (~1min), Similar panel (5–10s), every action feels slow
2. **Speed Loop broken** — assignments silently dropped (BUG-001, P0), bounding boxes misaligned, entry point broken
3. **Navigation disconnected** — no path from speed-run ↔ photo context ↔ face tagging

Then do a final triage sprint where Nolan drives and Claude fixes or logs in real-time.

No data regressions. No loss of confirmed identities. DATA-019 (community re-assignment) fixed before triage sprint.

---

## Phase 0: Orient (5 min)

1. Set `.claude/current_session.txt` to `102`
2. Read `tasks/lessons.md` + `docs/session_context/session-102-context.md`
3. Verify deploy: `/health` check
4. Create `docs/session_logs/session-102-log.md` with phase checklist
5. Verify DATA-019 scope: run `grep -r "Jews of Rhodes" data/photo_index.json | head -5` to confirm how many photos are misattributed to Fox Family batch
6. Commit: `chore: session 102 orient`
7. **DO NOT /clear yet — Phase 1 launches parallel worktrees**

---

## Phase 1: Launch Parallel Tracks (10 min)

Launch three worktree subagents simultaneously. They are independent and can run in parallel.

### Track A — Performance (worktree: `session-102/perf`)

**Goal:** Make GEDCOM search and Similar panel feel responsive. Target: GEDCOM <2s, Similar <1s.

**A1: GEDCOM search index + debounce (FB-120, PERF-006)**

File: `app/relationship_routes.py` — the `/api/gedcom/search` endpoint.

Fixes:
1. **Postgres GIN trigram index** — create a SQL migration:
   ```sql
   CREATE EXTENSION IF NOT EXISTS pg_trgm;
   CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gedcom_name_trgm
     ON gedcom_individuals USING GIN (name gin_trgm_ops);
   CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gedcom_given_trgm
     ON gedcom_individuals USING GIN (given_name gin_trgm_ops);
   ```
   Apply via Supabase SQL editor or `supabase.rpc()`. Verify timing before/after.
2. **Min 3 chars before firing** — in the HTMX `hx_trigger` for GEDCOM search input, change from `input changed delay:300ms` to require minimum character count. Add frontend guard: `if (this.value.length < 3) return;`
3. **Don't auto-fire on panel open** — change `hx_trigger="load"` to `hx_trigger="input"` (or keep load but with a "Type to search..." placeholder that only fires when query is non-empty)
4. **Add structlog timing** — log `gedcom_search_ms` for before/after comparison

**A2: Similar panel community-scoped scan (FB-127, PERF-005)**

File: `app/main.py` or wherever `neighbors_sidebar` is rendered — find the `/api/identity/{id}/similar` or equivalent endpoint.

Fixes:
1. **Community-scope first pass** — when computing neighbors, filter embeddings to same community first (use `identity_communities` table or the community membership set). Full cross-community scan only if community-scoped results < 5.
2. **Cache with TTL** — cache similar-identity results per identity_id with 5-minute TTL. Invalidate on merge/confirm that touches the identity.
3. **Add structlog timing** — log `similar_scan_ms` with community_scope vs full_scan flag

**A3: Verify registry TTL cache hits**

In `app/main.py`, add a quick `logger.debug("registry_cache_hit=%s", cache_hit)` in `load_registry()`. Deploy, do 3 operations in the app, check Railway logs. If cache is being bypassed, find why and fix it.

**Tests for Track A:**
- `test_gedcom_search_requires_min_chars` — verify empty/1-char query returns empty without DB hit
- `test_similar_panel_community_scoped` — mock embeddings, verify community-scoped identities returned first
- `test_registry_cache_repopulated_after_save` — already in Session 101; verify still passes

**Branch:** `session-102/perf`
**Commit:** `perf: GEDCOM trigram index + debounce + similar panel community scoping`

---

### Track B — Speed Loop Save Bug + Alignment (worktree: `session-102/speed-loop`)

**Goal:** Fix BUG-001 (assignments not persisting), fix bbox alignment, fix broken entry button.

**B1: Investigate and fix Speed Loop save bug (FB-141, BUG-001)**

The Speed Loop (`?seq=1` on the photo page) visually advances to the next face but assignments are silently dropped.

Investigation steps:
1. Find the POST route that handles tag assignment in `?seq=1` mode. Search `app/page_routes.py` for `seq` parameter handling and the associated tag/identify POST handler.
2. Add `logger.info("speed_loop_tag_save", identity_id=..., face_id=..., name=...)` before and after `save_registry()`.
3. Check the return value — does `save_registry()` succeed? Is there an uncaught exception after the visual advance?
4. Verify the save is writing to the SAME identity the display reads from (not two different registries).
5. Write a failing test FIRST that proves the bug: tag a face in Speed Loop, assert the identity's name changed in the registry.

Fix:
- If `except: pass` is eating errors — change to `logger.warning()` + re-raise or return error to UI (DATA-014 pattern)
- If writing to wrong data structure — fix the write target
- If save succeeds but reload fetches stale cache — add cache invalidation in save_registry after Speed Loop tag

**B2: Fix bbox alignment in Speed Loop (FB-139, UX-090)**

The overlay bounding boxes are shifted/disconnected from actual faces in `?seq=1` mode.

1. Find the JS/CSS that positions bbox overlays in the photo page Speed Loop view. Likely in `app/page_routes.py` or a JS block inline in the photo template.
2. Compare to the non-Speed-Loop photo overlay positioning — same coordinate math?
3. The fix likely needs `offsetLeft`/`offsetTop` of the photo container, or `naturalWidth`/`naturalHeight` vs `clientWidth`/`clientHeight` scaling factor.
4. Test with at least 2 different photos (one portrait, one group) to verify alignment holds.

**B3: Fix "Start Speed Loop" broken button (FB-138, UX-089)**

On the photo page, "Start Speed Loop (N unidentified)" button did not trigger navigation on click.

1. Find the button in `app/page_routes.py`. Check its `href` or `onclick`.
2. The `?seq=1` URL itself works (confirmed in triage). The issue is the button click handler.
3. Simple fix: ensure the button is an `<a href="?seq=1">` or has working JS navigation. Not an HTMX endpoint that returns a page — just a link.

**B4: Community-scope tag search (FB-140, UX-091)**

The name search in Speed Loop shows cross-community results unsorted.

Fix: In the tag search HTMX endpoint (within `?seq=1` handler), filter to current community identities first, OR sort community-match results before cross-community results, using the same "From [Community]" badge pattern from Session 96d.

Pass `community_slug` from the photo page URL into the search handler context.

**Tests for Track B:**
- `test_speed_loop_tag_saves_to_registry` — MUST BE A FAILING TEST FIRST, then fix makes it pass
- `test_speed_loop_bbox_coordinates_match_face_positions` — mock photo dimensions, verify overlay coords
- `test_speed_loop_start_button_has_correct_href` — verify href="?seq=1" or equivalent
- `test_speed_loop_search_community_scoped` — verify community identities ranked first

**Branch:** `session-102/speed-loop`
**Commit:** `fix(speed-loop): tag assignments now persist + bbox alignment + button + community search`

---

### Track C — Navigation Wiring (worktree: `session-102/nav`)

**Goal:** Create a connected triage flow: speed-run ↔ photo context ↔ face tagging. No more dead ends.

**C1: Identify Mode → activates Speed Loop (FB-137, FB-138, UX-088, UX-089)**

"Identify Mode" button is currently cosmetic-only (pulse animation + "?" badges). It should activate the Speed Loop.

Fix:
- Change "Identify Mode" button to navigate to `?seq=1` for admin users
- For non-admin users, keep current behavior (visual highlight + "?" badges for public contribution)
- Guard: `if is_admin: href="?seq=1"` else keep toggle behavior

**C2: Face click → admin tag panel (FB-134, UX-085)**

On the photo page, clicking a face bbox currently navigates to `/identify/{face_id}` (public page). For admins, this should open the Speed Loop on that specific face.

Fix:
- When admin is on photo page, face bbox click should navigate to `?seq=1&face={face_id}` (if Speed Loop supports jumping to a specific face) OR activate the inline tag panel for that face
- If `?seq=1&face={face_id}` requires new Speed Loop parameter support: add `face_id` as starting position to Speed Loop handler
- Non-admin behavior unchanged

**C3: Speed Loop → "Back to review queue" return link (FB-135, UX-086)**

After completing Speed Loop on a photo (all faces tagged or skipped), there's no way back to the speed-run cluster queue.

Fix:
- Add a "Back to Review Queue" link/button at Speed Loop completion and as a persistent escape hatch
- Pass `?from_queue=1` or `?from_queue={photo_id}` when navigating to photo from speed-run
- "Back to Review Queue" link reads this param and returns to `/c/{slug}/admin/upload-review?mode=speed`

**C4: Admin tools on /identify/ page (FB-136, UX-087)**

The `/identify/{face_id}` page is public-only — no merge search, no name input, no GEDCOM link.

Fix:
- When admin is on `/identify/{face_id}`, render the admin enrichment section below the public section
- Reuse `_speed_run_enrichment_panel()` or build a simpler inline version with:
  - Current identity info
  - Name input (pre-filled if named)
  - Merge search (same typeahead as speed-run)
  - GEDCOM link button (same as enrichment panel)

**C5: Fix community URL prefixes on speed-run face crop links (FB-125, UX-079)**

Speed-run face crop links use `/photo/{id}` without community prefix. Fix to `/c/{slug}/photo/{id}`.

Find all `href=f"/photo/{...}"` in `app/cluster_review_routes.py` and add community prefix.

**Tests for Track C:**
- `test_identify_mode_button_admin_links_to_speed_loop` — admin user gets `?seq=1` href
- `test_identify_mode_button_nonadmin_is_toggle` — non-admin gets toggle behavior
- `test_face_click_admin_opens_speed_loop` — verify bbox click href for admin
- `test_speed_loop_has_back_to_queue_link` — verify back link rendered when `from_queue` param present
- `test_identify_page_admin_sees_enrichment` — admin sees name input + merge search on /identify/
- `test_speed_run_face_links_include_community_prefix` — verify `/c/fox-family/photo/...` in links

**Branch:** `session-102/nav`
**Commit:** `feat(nav): connected triage flow — Identify Mode + face clicks + back links + admin identify`

---

## Phase 2: DATA-019 Fix — Rhodes Photos in Fox Family (20 min)

**This runs on main after Phase 1 launches. Must complete before triage sprint.**

**Problem (FB-129):** Community-batch-20260214 included Rhodes-community photos (collection="Jews of Rhodes: Family Memories & Heritage") alongside Fox Family photos. These now appear in Fox Family speed-run.

**Investigation:**
1. Run: `python -c "import json; d=json.load(open('data/photo_index.json')); print([p['path'] for pid,p in d['photos'].items() if 'Jews of Rhodes' in p.get('collection','') and 'community-batch' in p.get('source','')][:10])"`
2. Count: how many photos have collection="Jews of Rhodes" but are in community-batch-20260214?
3. List their identities.

**Fix:**
- For each misattributed photo: update `photo_communities` table in Supabase to set `community_id = Rhodes community ID` (not Fox Family)
- For each identity that ONLY appears in those misattributed photos: update `identity_communities` to remove Fox Family membership
- Script should be `scripts/fix_data_019_community_reassignment.py` — dry-run first, then `--execute`
- After execution: verify Fox Family speed-run no longer shows the naturalization document

**Safety:** Before running, export current `photo_communities` and `identity_communities` rows for affected IDs to `data/backups/pre_data019_fix_{timestamp}.json`.

**Tests:**
- `test_data_019_rhodes_photos_not_in_fox_family` — verify no photo with collection "Jews of Rhodes" appears in Fox Family speed-run queue

**Commit:** `fix(data): DATA-019 re-assign community-batch Rhodes photos to correct community`
**/clear after commit**

---

## Phase 3: DATA-020 — Postgres Name Protection Guard (15 min)

**Re-read this phase from `docs/prompts/session-102-prompt.md` after /clear.**

**Problem (FB-122):** The non-blocking Postgres shadow sync in `save_registry()` can overwrite a production name ("Charles Fox") with a local auto-generated name ("Unidentified Person 2986") if local and production are out of sync.

**Fix:**
- In `core/registry.py` or wherever `upsert_identity_to_supabase()` is called: add a guard before writing the `name` field:
  ```python
  # Never overwrite a meaningful Postgres name with an auto-generated local name
  if local_name.startswith("Unidentified Person") and postgres_name and not postgres_name.startswith("Unidentified"):
      skip_name_field = True
  ```
- The guard should: fetch the current Postgres name before upsert, skip the name field if local is auto-generated and Postgres has a real name
- Log when this protection fires: `logger.warning("name_protection_fired", identity_id=..., local_name=..., postgres_name=...)`

**Tests:**
- `test_postgres_sync_does_not_overwrite_real_name_with_autogenerated` — mock Supabase, verify name field not written when local is "Unidentified Person NNN" and Postgres has a real name
- `test_postgres_sync_does_overwrite_when_both_autogenerated` — if both are auto-generated, the upsert proceeds normally

**Commit:** `fix(data): DATA-020 Postgres name protection — never overwrite real name with auto-generated`

### Also in Phase 3:

**FB-143: Enrichment panel GEDCOM link status after merge**
After merging into a person who already has a GEDCOM link, the enrichment panel still shows a fresh "Link to Family Tree" search instead of "Already linked to: [Name]". Fix: in the merge confirmation response, check `_load_gedcom_face_links()` for the target identity. If linked, render `_person_gedcom_link_section()` instead of `_gedcom_link_panel()`.

**FB-142: Keyboard shortcut action logging (OBS-002)**
Add `input_method` field to `log_user_action()` calls in speed-run: `"keyboard"` vs `"button"`. Track in PostHog. Also log undo patterns (confirm → immediate undo = possible accidental). This enables data-driven decision on whether to keep hotkeys.

**Commit:** `feat(ux): GEDCOM link status after merge + keyboard action logging`
**/clear after commit**

---

## Phase 4: Merge All Tracks + Deploy (20 min)

**Re-read this phase from `docs/prompts/session-102-prompt.md` after /clear.**

1. Wait for all three worktree tracks (A, B, C) to complete and commit
2. Merge in order: B first (Speed Loop save — P0), then C (navigation), then A (performance)
   ```bash
   ./scripts/merge.sh session-102/speed-loop session-102/nav session-102/perf
   ```
3. Run full test suite: `make test-fast`
4. If any failures: fix before proceeding. Do not skip.
5. Deploy: `git push origin main` then verify with `mcp__railway-mcp-server__list-deployments`
6. Wait for deploy to show `status=SUCCESS` and `builder=DOCKERFILE`

**Commit:** `chore: merge session-102 tracks — speed-loop + nav + perf`
**/clear after commit**

---

## Phase 5: Browser Verify — 12 Checks (20 min)

**Re-read this phase from `docs/prompts/session-102-prompt.md` after /clear.**

Use Claude Chrome browser plugin (admin is logged in). Navigate to Fox Family.

**Speed Loop (BUG-001 fix):**
- [ ] Tag a face with a name in Speed Loop → reload photo page → face shows as tagged (not Unidentified)
- [ ] Tag 3 faces in sequence → all 3 persist after page reload
- [ ] Bbox overlays align with actual faces in the photo (not shifted left)
- [ ] "Start Speed Loop" button click navigates to `?seq=1`

**Performance:**
- [ ] GEDCOM search for "Albert" returns results in <3s (not 1 minute)
- [ ] Similar panel loads in <2s (not 5–10s)

**Navigation:**
- [ ] "Identify Mode" button on photo page links to `?seq=1` for admin
- [ ] Clicking a face on the photo page (admin) opens Speed Loop on that face
- [ ] Speed Loop completion shows "Back to Review Queue" link
- [ ] `/identify/{face_id}` page shows admin tools (name input + merge search) when admin

**Data integrity:**
- [ ] Fox Family speed-run no longer shows "Bohor Sabatai Soriano" naturalization document
- [ ] Charles Fox identity has name "Charles Fox" (not reset to "Unidentified Person")

Save screenshots to `docs/screenshots/session-102/`. Mark each check PASS/FAIL in session log.

**Commit:** `docs: session 102 browser verification — N/12 PASS`
**/clear after commit**

---

## Phase 6: Batch Validation Decision + Cleanup (15 min)

**Re-read this phase from `docs/prompts/session-102-prompt.md` after /clear.**

### Decision: Fix batch validation or remove from nav?

**Option A: Remove from nav (recommended)**
- Remove any sidebar link to `/admin/cluster-batch`
- Add BACKLOG item PIPELINE-001 as prerequisite for revival
- Mark UX-081 as DEFERRED in BACKLOG
- The page still exists at the URL but is not surfaced to users (invisible ≠ removed)

**Option B: Fix it** (only if Nolan wants to use it in the triage sprint)
- Fix 404 (route at `/admin/cluster-batch` not `/admin/cluster-validation`) — update or add redirect
- Add to admin sidebar under "Review"
- Show ALL faces per cluster card (inline scrollable grid, not "+N more")
- Remove pre-selection — start with all unchecked
- Minimum: admin must check at least 1 card before "Confirm Selected" button enables

Default to Option A unless Nolan overrides.

**Regardless of choice:**
- Add `test_unwired_admin_routes_detection` — TEST-002 from FB-132: enumerate all `/admin/` routes and verify each has at least one nav entry pointing to it, or is explicitly marked as "no-nav" in a skip list. This prevents Lesson 138 from recurring.

**Commit:** `fix(nav): batch validation — remove from nav + unwired route detection test`
**/clear after commit**

---

## Phase 7: ML Active Learning Research + PRD (30 min)

**Re-read this phase from `docs/prompts/session-102-prompt.md` after /clear.**

### Background
Nolan's insight (FB-145): after confirming several Fox Family clusters, can we re-run ML with that feedback to improve matching and reduce manual triage? This is the core value proposition of PRD-038 (Session 97) which built infrastructure but never activated it.

### Research context (from web search, 2026-03-14)
The academic literature strongly supports this approach:
- **Constrained clustering** (Wagstaff et al. 2001, comprehensive review Springer 2025): must-link/cannot-link constraints from user feedback dramatically improve clustering. Confirmed faces = must-links, "Not Same" = cannot-links.
- **Semi-supervised deep embedded clustering** (ScienceDirect 2023): pairwise constraints guide clustering in embedding space — exactly our setup with frozen PFE embeddings.
- **Continuous learning for face clustering** (ResearchGate 2021): combines active learning + self-paced learning for automatic annotation under weak expert re-certification.
- **DC-SSDEC** (PMC 2025): dual-constraint semi-supervised deep clustering using soft "should-link"/"shouldNot-link" — applicable to our similarity scores.

### What PRD-038 already built (Session 97)
1. **Prototype-bank reranker** (Phase 2) — confirmed faces as reference centroids, shadow mode
2. **Active learning** (Phase 3) — selects most informative face to review, wired to review UX
3. **Adapter experiment harness** (Phase 4) — frozen-embedding fine-tuning track
4. All rollout gates closed — not enough labels at the time

### Tasks for this phase
1. **Audit PRD-038 state**: Read `rhodesli_ml/` modules, check what's working in shadow mode, what data we have
2. **Count confirmed Fox labels**: How many confirmed identities × faces do we have? Minimum viable for constrained re-clustering?
3. **Design retroactive experiment**: Take current confirmed anchors, re-run clustering with must-link constraints, compare cluster quality vs. blind clustering
4. **Write PRD-045**: "Active Learning Feedback Loop" — scope: (a) activate prototype-bank reranker, (b) re-cluster with confirmed anchors as seeds, (c) measure improvement, (d) if positive, wire into post-triage pipeline (after confirming N clusters, auto-improve remaining matches)
5. **Document research**: Save findings to `docs/ml/ACTIVE_LEARNING_RESEARCH.md` with paper references and breadcrumbs to PRD-038

**Commit:** `docs: PRD-045 active learning feedback loop + research`
**/clear after commit**

---

## Phase 8: Triage Sprint with Nolan (30 min)

**Re-read this phase from `docs/prompts/session-102-prompt.md` after /clear.**

Return to Fox Family speed-run: `/c/fox-family/admin/upload-review?mode=speed`

Nolan drives. For each issue:
1. Can it be fixed in <10 min? → Fix immediately, commit, push, deploy
2. Cannot be fixed quickly? → Create BACKLOG entry with specifics, move on

**Pre-triage checklist (verify before handing to Nolan):**
- [ ] Speed Loop saves are working (from Phase 5 browser verify)
- [ ] DATA-019: Rhodes photos are gone from Fox Family queue
- [ ] DATA-020: Name protection guard is deployed
- [ ] GEDCOM search is fast
- [ ] Person 2795 (unnamed CONFIRMED cluster) — needs Nolan's decision: merge into Charles Fox, Esther Burd, or new person? Provide URL: `/c/fox-family/person/98772230-f4a2-4a10-b6cf-36d915e29225`

**Document all feedback in:** `docs/feedback/2026-03-14-fox-triage-round3.md`
(or continue in same file if short)

---

## Phase 9: Session Closeout (15 min)

**Re-read this phase from `docs/prompts/session-102-prompt.md` after /clear.**

1. Run `/session-review` skill — catch any gaps
2. Write `docs/assessments/session-102-assessment.md`
3. Update BACKLOG.md — add all new BACKLOG items from FB-120–FB-141 with correct IDs:
   - UX-077 through UX-091 (if not already in BACKLOG)
   - BUG-001 (Speed Loop save)
   - PERF-005, PERF-006
   - DATA-018, DATA-019 (mark FIXED), DATA-020 (mark FIXED)
   - PIPELINE-001 (incremental clustering audit)
   - TEST-002 (unwired route detection test — mark FIXED if shipped in Phase 6)
4. Update `CHANGELOG.md` — v1.0.0 if Speed Loop + Performance + Navigation all ship; v0.99.4 otherwise
5. Update `ROADMAP.md` — check off Session 102 deliverables
6. Update `tasks/lessons.md` — add any new lessons (especially around Speed Loop silent failures)
7. Final commit with all harness docs

---

## Critical Rules

- **/clear between phases** — MANDATORY after every phase commit.
- **BUG-001 is P0** — Speed Loop save bug is the first thing merged. Don't mark session complete if tags still don't persist.
- **DATA-019 before triage** — Do not start the Nolan triage sprint until Rhodes photos are removed from Fox Family queue.
- **Test before every commit** — `make test-fast`. Track B test must FAIL first on BUG-001, then pass after fix.
- **Browser verify all 12 checks** — Lesson 131: never claim fixed without production browser verification.
- **Document subagent state before /clear** — branch names + commit hashes in session log.
- **Monitor context** — at 30% remaining, stop and write handoff. Do not wait for user to ask.

---

## Acceptance Criteria

Session 102 is done when:
1. BUG-001: Speed Loop tag assignments persist after page reload (verified in browser)
2. Performance: GEDCOM search <3s, Similar panel <2s (verified in browser)
3. Navigation: connected flow from speed-run → photo → Speed Loop → back to speed-run (verified in browser)
4. DATA-019: Rhodes photos removed from Fox Family speed-run (verified in browser)
5. DATA-020: Postgres name protection guard deployed (verified by test)
6. Nolan completes at least one full triage round without hitting P0/P1 issues
7. All tests pass (app + ML): `make test-fast`
8. Session assessment filed with evidence and 12-check browser verify results
9. CHANGELOG, ROADMAP, BACKLOG updated
