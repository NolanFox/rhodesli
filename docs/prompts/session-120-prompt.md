# Session 120 — ML Comparison Script + UX Fix Sprint

@docs/session_context/session-120-context.md
@docs/feedback/session-119-feedback.md
@tasks/lessons.md

## Goal

Complete Session 119's outstanding gaps (embedding comparison, Sentry investigation) and fix the top 4 UX issues from interactive feedback. Conservative, test-everything approach — no data regressions.

## CRITICAL CONSTRAINTS

1. **Browser automation is READ-ONLY on production** (Lesson 149).
2. **DO NOT touch**: `core/neighbors.py` (frozen), `core/pfe.py`, `app/perf_cache.py`.
3. **Every change gets tests** — happy path + failure + regression.
4. **No changes to clustering thresholds** — AD-179 tiers are correct.
5. **/clear between phases** — commit first, then /clear immediately.
6. **Parallelization**: Use worktrees where files don't overlap. See context file for dependency analysis.
7. **SDD approach**: Each FB item needs clear acceptance criteria verified by tests.

## Pre-Requisites

```bash
echo "120" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline — record count and time
```

Read:
- `docs/session_context/session-120-context.md`
- `docs/assessments/session-119-assessment.md`
- `docs/feedback/session-119-feedback.md`

---

## Phase 0: Orient (3 min)

Create session log. Verify baseline tests pass. Record count.

**Commit:** `docs: session 120 phase 0 — orient`
**/clear**

---

## Phase 1: ML Embedding Comparison Script (20 min)

### 1A: Create admin compare endpoint

Add `POST /api/admin/ml-compare` to `app/admin_routes.py`:
- Accepts multipart image upload
- Calls ML service `detect_and_embed()` via `_run_ml_client_async()`
- Returns raw JSON response (faces, embeddings, image_size)
- NO database writes, NO identity creation
- Admin-only auth

### 1B: Create comparison script

Create `scripts/compare_ml_embeddings.py`:
- Takes `--photo` (local path) and `--url` (production URL, default localhost)
- Runs local InsightFace detection via `core/ingest_inbox.extract_faces()`
- Calls `/api/admin/ml-compare` with the same photo
- Matches faces by bounding box IoU (>0.5 = same face)
- Reports cosine similarity per matched face pair
- Exit code 0 if all pairs ≥ 0.999, exit code 1 otherwise
- `--dry-run` flag that only runs local detection (no ML service call)

### 1C: Tests

- Test admin endpoint returns embeddings (mocked ML service)
- Test admin endpoint rejects non-admin
- Test admin endpoint rejects non-image files
- Test comparison script with mocked local + remote detection

**Commit:** `feat(ml): session 120 phase 1 — embedding comparison script + admin endpoint`
**/clear**

---

## Phase 2: Sentry Alert Investigation + Fix (15 min)

### 2A: Investigate POST-SYNC VALIDATION

Read `app/upload_routes.py:1190-1240`. Trace:
1. Where does `result["face_ids"]` come from?
2. What format are the face IDs? (inbox_XXX?)
3. When are identities created relative to the validation check?
4. Is `json_registry._identities` the right thing to check against?

### 2B: Fix or Document

If it's a real bug: fix the validation logic.
If it's a false positive: add a comment explaining why and consider demoting from error to warning.
Either way: add a test that verifies the validation works correctly.

**Commit:** `fix(upload): session 120 phase 2 — post-sync validation fix`
**/clear**

---

## Phase 3: FB-009 — Confirm Button Fix (10 min)

**Can be parallelized as worktree — only touches `app/page_routes.py`**

### 3A: Fix the button rendering

In `app/page_routes.py:4005-4026`, check `IdentityRegistry._is_real_name(identity_name)` before rendering the confirm button. If the identity has an auto-generated name:
- Render the button as **disabled** with gray styling and tooltip "Name this person first"
- Do NOT hide the button entirely (hiding would confuse users about what's possible)

### 3B: Tests

- Test that confirm button has `disabled` attribute for "Unidentified Person XXX"
- Test that confirm button is active for named persons
- Test the quick-action endpoint still returns 409 for unidentified (defense in depth)

**Commit:** `fix(ux): session 120 phase 3 — FB-009 disable confirm for unidentified persons`
**/clear**

---

## Phase 4: FB-008 — Cross-Batch Match Notifications (20 min)

**Touches `app/upload_routes.py` — do AFTER Phase 2 (same file)**

### 4A: Understand notification system

Read the existing notification infrastructure:
- How are notifications stored? (Supabase table? In-memory?)
- What does the notification count endpoint return?
- How are notifications rendered in the sidebar?

### 4B: Generate notification after upload

After `find_cross_batch_matches()` completes in `_background_ingest()`:
- Count the number of high-confidence matches (distance < 1.15)
- If any exist: create a notification entry
- Format: "Upload complete: {N} faces detected, {M} potential matches found"
- Include link to the uploaded photo's page

### 4C: Tests

- Test that upload with cross-batch matches generates notification
- Test that upload with no matches generates no notification
- Test notification count endpoint reflects the new notification

**Commit:** `feat(ux): session 120 phase 4 — FB-008 cross-batch match notifications`
**/clear**

---

## Phase 5: FB-001 — Merge Search in Focus View (15 min)

### 5A: Check current state

Determine if "Search to merge..." exists on person pages but NOT in Focus/New Matches view. Read the Focus view card rendering code.

### 5B: Add search to Focus view

If missing: add the same "Search to merge..." input to each identity card in Focus view. The search endpoint (`/api/face/tag-search` or similar) already exists — reuse it.

### 5C: Tests

- Test Focus view card renders search input
- Test search endpoint returns results for known names

**Commit:** `feat(ux): session 120 phase 5 — FB-001 merge search in Focus view`
**/clear**

---

## Phase 6: FB-011 — Community Filter on Similar Identities (20 min)

### 6A: Add community filter

Add a filter control to the Similar Identities panel on person pages:
- Options: "Same community" (default for non-admin), "All communities" (default for admin), specific community names
- Filter the results before rendering
- Preserve the existing ranking within the filtered set

### 6B: Implementation

The Similar Identities data comes from `find_nearest_neighbors` or `_get_confirmed_identity_suggestions()`. Add a `community_id` parameter:
- If set: filter results to only include identities from that community
- If None: show all (current behavior)
- Add HTMX dropdown that re-fetches the panel with the selected community filter

### 6C: Tests

- Test Similar Identities with community filter shows only same-community results
- Test "All communities" shows cross-community results
- Test default behavior unchanged for existing pages

**Commit:** `feat(ux): session 120 phase 6 — FB-011 community filter on Similar Identities`
**/clear**

---

## Phase 7: Harness Outputs (10 min)

### 7A: Final Documentation

1. Assessment: `docs/assessments/session-120-assessment.md`
2. CHANGELOG: v0.99.30
3. ROADMAP: update feedback item statuses
4. SESSION_HISTORY: Session 120 entry
5. Session log: `docs/session_logs/session-120-log.md`
6. BACKLOG: update UX-131 through UX-140 statuses

### 7B: Browser Verification (READ-ONLY)

Screenshots of:
1. Focus view with search box (FB-001)
2. Person page with community filter (FB-011)
3. Speed Loop with disabled confirm button (FB-009)
4. Notification after upload (FB-008) — if testable without uploading

**Commit:** `docs: session 120 harness outputs — assessment, changelog, roadmap`

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| ML compare script works? | `python scripts/compare_ml_embeddings.py --dry-run --photo raw_photos/Image\ 001_compress.jpg` | Exits 0, shows face count |
| Sentry alert fixed? | Read upload_routes.py validation logic | Fixed or documented |
| FB-009 confirm disabled? | Test + browser screenshot | Disabled for unidentified |
| FB-008 notifications? | Test | Notification created after upload |
| FB-001 search in Focus? | Test + browser screenshot | Search box present |
| FB-011 community filter? | Test + browser screenshot | Filter dropdown works |
| All tests pass? | `make test-fast` | PASS |
| Assessment exists? | `ls docs/assessments/session-120-assessment.md` | Exists |
| `git log origin/main..HEAD` empty? | git log | Empty |

## Parallelization

Recommended parallel execution:
- **Worktree A:** Phase 3 (FB-009) — only page_routes.py
- **Worktree B:** Phase 1 (ML compare) — admin_routes.py + new script
- **Sequential on main:** Phase 0 → Phase 2 → Phase 4 (upload_routes.py)
- **After merge A+B:** Phase 5 → Phase 6 (identity rendering, may overlap)
- **Last:** Phase 7 (harness)
