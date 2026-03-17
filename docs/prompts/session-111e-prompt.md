# Session 111e — Continuation: Performance + Remaining Fixes

## Context
@docs/session_context/session-111e-context.md
@docs/feedback/session-111-feedback.md
@docs/feedback/session-111d-interactive-feedback.md

Session 111d shipped 16 fixes but deferred performance work and several items. This session finishes everything. No new features — fix and optimize only.

## CRITICAL CONSTRAINTS
1. **ZERO REGRESSIONS.** Test before and after every change.
2. **NEVER click action buttons on production.** Browser is READ-ONLY (Lesson 149).
3. **Plan before coding.** Complex changes need written plan first.
4. **Single source of truth.** When fixing data issues, update BOTH `identities` AND `identity_overrides` tables.

## Pre-Requisites
1. Read `tasks/lessons.md` — especially Lessons 149, 150
2. Read `docs/session_context/session-111e-context.md` — full deferred items list
3. Set `.claude/current_session.txt` to `111e`
4. Set `.claude/session_mode.txt` to `implementation`

---

## Phase 0: Orient (5 min)
1. `git log --oneline -5` — confirm 111d complete
2. Read context file for prioritized remaining work

---

## Phase 1: Performance — P0 (45 min)

The site is too slow. Three root causes remain after the `save_registry()` fix:

### 1A: Cache `_get_confirmed_identity_suggestions()`
- Location: `app/cluster_review_routes.py`
- Currently iterates ALL identities + computes quality scores on every call
- Add TTL cache (30s) keyed by identity_id
- Invalidate on confirm/merge/skip

### 1B: Cache `_get_speed_run_clusters()`
- Location: `app/cluster_review_routes.py`
- Recomputed on every request
- Cache for 30s, invalidate on confirm/merge/skip

### 1C: Profile `find_nearest_neighbors()`
- Location: `core/neighbors.py`
- Loads all embeddings and computes cosine distance
- Consider: precomputed distance matrix, or limit to same-community faces first
- At minimum: add timing logs to identify the exact bottleneck

### Tests
- Verify cached suggestions return same result as uncached
- Verify cache invalidation works after merge

---

## Phase 2: Confirm Button UX — P0 (15 min)

### FB-077: Confirm button fails silently for unidentified persons
- The confirm button shows "Confirming..." then nothing happens
- Root cause: `confirm_identity()` rejects placeholder names ("Unidentified Person NNN")
- The 409 error toast is returned but invisible (goes to wrong container or z-index)
- Fix: On the person page, when confirm is clicked for an unidentified person, show inline error: "Rename this person first, then confirm." VISIBLE, not a toast.
- The triage card confirm buttons already have the FB-066 pre-check — apply the same pattern to the person page confirm handler.

---

## Phase 3: Face Overlay Fix — P0 (15 min)

### FB-075: Face overlays missing on some photos
- The Supabase fallback in `get_photo_dimensions()` can't find photos because it looks up by filename but the photo registry uses `inbox_*` IDs with different filenames
- Fix: In the Supabase fallback, iterate photo registry entries and match by filename (Path(path).name == basename)
- This was partially done in Session 111d but needs the filename matching to work across ID formats

---

## Phase 4: Remaining P1 Fixes (30 min, can parallelize)

### Focus mode URL stripping after merge
- After merge in focus mode, URL changes from `?section=to_review&view=focus&filter=ready` to just `/c/fox-family/`
- Investigate: check if HTMX is pushing the merge endpoint URL as browser history
- Fix: add `hx-push-url="false"` to merge button, or add `HX-Push-Url: false` header to merge response

### FB-072: Approval history
- After approving names, show a list of recently approved items at the bottom of /admin/approvals
- Query approved annotations and display with timestamps

### Source URL not saving
- Verify the save endpoint works by reading DOM attributes (READ-ONLY)
- Check if `resolve_photo_registry_photo_id()` is correctly resolving the photo ID

### FB-076: Community awareness on approve
- Verify the approve endpoint correctly associates the identity with the right community
- Check `add_identity_to_community()` is called after confirm

---

## Phase 5: Deploy + Verify (15 min)
1. `git push origin main`
2. Wait for deploy SUCCESS
3. Browser verify ALL fixes (READ-ONLY):
   - [ ] Similar Identities loads faster (<3s)
   - [ ] Speed-run cluster loads faster
   - [ ] Confirm button shows error for unidentified persons (visible, not hidden toast)
   - [ ] Face overlays appear on Rhodes photos
   - [ ] Focus mode URL preserved after merge
   - [ ] Approve + confirm checkbox works
4. `git log origin/main..HEAD` is empty

---

## Phase 6: Harness Outputs (10 min)
1. Assessment: `docs/assessments/session-111e-assessment.md`
2. Session log: `docs/session_logs/session-111e-log.md`
3. Update ROADMAP, CHANGELOG, BACKLOG
4. Update feedback files — mark all fixed items
5. Verify `git log origin/main..HEAD` is empty
