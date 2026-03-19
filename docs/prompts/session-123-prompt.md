# Session 123 — Performance + UX + Upload Audit Sprint

@docs/session_context/session-123-context.md
@tasks/lessons.md

## Goal

Fix the top 2 performance bottlenecks, improve landing page for community adoption, reorder enrichment panel for triage efficiency, and audit the upload pipeline. No regressions.

## CRITICAL CONSTRAINTS

1. **Browser automation is READ-ONLY on production** (Lesson 149).
2. **DO NOT touch**: `core/neighbors.py` (frozen), `core/pfe.py`.
3. **DO NOT break community middleware** — test community-scoped routes after changes.
4. **Every change gets tests** — happy path + failure + regression.
5. **/clear between phases** — commit first, then /clear immediately.
6. **Parallelization**: 2 worktrees possible. See context file.
7. **Security audit**: After all code phases.
8. **Gap check**: Re-read this prompt at end. Auto-fix any gaps.
9. **No data regressions** — verify data integrity tests pass.
10. **REMINDER**: Tell user to do upload testing tonight (AD-229).

## Pre-Requisites

```bash
echo "123" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline
```

---

## Phase 0: Orient (3 min)

Create session log. Verify baseline tests pass. Record count.

**Commit:** `docs: session 123 phase 0 — orient`
**/clear**

---

## Phase 1: PERF-A — Deduplicate embeddings.npy Loads (15 min)

### 1A: Find all direct np.load calls

Search for `np.load.*embeddings` across app/ — each should use `get_face_data()` from main.py instead of direct np.load.

### 1B: Fix bypass routes

Replace direct `np.load(embeddings_path, allow_pickle=True)` with `_main_mod.get_face_data()` or equivalent cached loader. Key locations:
- `app/compare_routes.py:3877`
- `app/sync_routes.py:1211`
- `app/main.py:3694` and `app/main.py:4547`

### 1C: Tests

- Test that get_face_data() is the canonical loader
- Test that compare_routes doesn't call np.load directly

**Commit:** `perf: session 123 phase 1 — PERF-A deduplicate embeddings loads`
**/clear**

---

## Phase 2: PERF-B — save_registry changed_ids Audit (20 min)

**Worktree A — touches identity_routes.py, cluster_review_routes.py, page_routes.py**

### 2A: Audit all save_registry callers

Search for `save_registry(` across app/. For each call:
- Does it pass `changed_ids`?
- If not, what identity IDs were actually changed?
- Fix: pass the specific changed IDs

### 2B: Fix callers

Each `save_registry(registry)` should become `save_registry(registry, changed_ids=[specific_ids])`.

### 2C: Tests

- Test that save_registry is called with changed_ids in key routes (confirm, merge, reject, skip)
- Structural test: grep for `save_registry(registry)` without changed_ids

**Commit:** `perf: session 123 phase 2 — PERF-B save_registry changed_ids propagation`
**/clear**

---

## Phase 3: UX-A — Enrichment Panel Reorder (15 min)

### 3A: Find the enrichment panel

Search for the enrichment/suggestions panel rendered after confirm in speed-run or Focus view. It should be in `app/cluster_review_routes.py` or `app/main.py`.

### 3B: Reorder sections

Current order: name input → merge search → GEDCOM link
New order: **merge search FIRST** → name input → GEDCOM link

Rationale: When triaging, you first check "does this person already exist?" (merge search), then name them, then link GEDCOM.

### 3C: Tests

- Test enrichment panel has merge search before name input (check DOM order)

**Commit:** `fix(ux): session 123 phase 3 — UX-A enrichment panel reorder`
**/clear**

---

## Phase 4: UX-B — Landing Page CTAs (15 min)

**Worktree B — touches page_routes.py only**

### 4A: Add visitor CTAs

On the landing page, below the photo grid, add clear call-to-action buttons for non-admin visitors:
- "Help Identify Someone" → `/help-identify` or equivalent
- "Compare a Face" → `/tools/compare`
- "Explore the Archive" → `/people` or `/photos`

Design: large buttons (min 48px height), mobile-friendly, museum-quality styling consistent with existing dark theme.

### 4B: Tests

- Test landing page has CTA buttons for non-admin visitors
- Test CTAs link to correct routes

**Commit:** `feat(ux): session 123 phase 4 — UX-B landing page CTAs`
**/clear**

---

## Phase 5: Upload Pipeline Audit (15 min)

### 5A: End-to-end trace

Read the upload pipeline code path:
1. Upload form → `POST /upload` → staging directory
2. Approval → `POST /admin/pending/{id}/approve` → process_directory
3. R2 upload → photo record creation → Supabase sync
4. Cache invalidation → photo appears in browse

### 5B: Find the regression

Check for:
- Missing R2 uploads (photos in photo_index but not on R2)
- Staging cleanup deleting files before R2 upload completes
- Photo IDs mismatched between registry and photo_index
- source_url propagation (fixed in Session 121, verify)

### 5C: Document findings

Write findings to `docs/session_context/session-123-upload-audit.md`. Fix if straightforward, otherwise BACKLOG with specific findings.

**Commit:** `docs: session 123 phase 5 — upload pipeline audit`
**/clear**

---

## Phase 6: Security Audit + Harness Outputs (15 min)

### 6A: Security audit of changed files
Review all files changed this session for auth guards, injection, XSS.

### 6B: Harness outputs
1. Assessment: `docs/assessments/session-123-assessment.md`
2. CHANGELOG: v0.99.33
3. ROADMAP + SESSION_HISTORY updates
4. BACKLOG updates

### 6C: Gap check + browser verify

Re-read this prompt. Verify every phase. Auto-fix gaps.
Browser-verify landing page CTAs if deploy is complete.

### 6D: Remind user
"Remember to do upload testing tonight for AD-229."

**Commit:** `docs: session 123 harness outputs`
**Push to origin main**

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| PERF-A: No direct np.load? | grep | All use get_face_data() |
| PERF-B: save_registry has changed_ids? | grep | All callers pass IDs |
| UX-A: Enrichment reordered? | Test | Merge search before name |
| UX-B: Landing CTAs? | Test + browser | 3 CTA buttons visible |
| Upload audit documented? | File exists | Findings documented |
| All tests pass? | `make test-fast` | PASS |
| No data regressions? | data integrity tests | PASS |
| Assessment exists? | File check | Exists |
| `git log origin/main..HEAD` empty? | git log | Empty |

## Parallelization

**2 parallel worktrees:**
- **Worktree A:** Phase 2 (PERF-B save_registry audit) — identity_routes, cluster_review_routes
- **Worktree B:** Phase 4 (UX-B landing CTAs) — page_routes.py only
- **Sequential on main:** Phase 0 → Phase 1 → Phase 3 → Phase 5 → Phase 6
