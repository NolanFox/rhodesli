# Session 121 — Upload Verification + UX Fix Sprint + Feature Planning

@docs/session_context/session-121-context.md
@docs/assessments/session-120-assessment.md
@tasks/lessons.md

## Goal

Verify AD-229 ML service criteria, fix 4 remaining UX issues from Session 119 feedback, and create planning artifacts for TOOLS-003 and WORKSPACE-001. Conservative approach — every change tested, browser-verified.

## CRITICAL CONSTRAINTS

1. **Browser automation is READ-ONLY on production** (Lesson 149).
2. **DO NOT touch**: `core/neighbors.py` (frozen), `core/pfe.py`, `app/perf_cache.py`.
3. **Every change gets tests** — happy path + failure + regression.
4. **No changes to clustering thresholds** — AD-179 tiers are correct.
5. **/clear between phases** — commit first, then /clear immediately.
6. **Parallelization**: Use worktrees where files don't overlap. See context file for dependency analysis.
7. **SDD approach**: Each UX item needs clear acceptance criteria verified by tests.
8. **Codex audit**: After implementation phases, run a Codex-style security audit on changed files.
9. **Gap check**: After all phases, re-read this prompt and verify every item. Auto-fix any gaps.

## Pre-Requisites

```bash
echo "121" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline — record count and time
```

Read:
- `docs/session_context/session-121-context.md`
- `docs/assessments/session-120-assessment.md`

---

## Phase 0: Orient (3 min)

Create session log. Verify baseline tests pass. Record count.

**Commit:** `docs: session 121 phase 0 — orient`
**/clear**

---

## Phase 1: AD-229 Admin Compare Endpoint (15 min)

### 1A: Create admin proxy endpoint

Add `POST /api/admin/ml-compare` to `app/admin_routes.py`:
- Accepts multipart image upload
- Forwards to ML service `detect-and-embed` via MLServiceClient
- Returns raw embedding JSON (face bboxes + embeddings)
- NO database writes, NO identity creation
- Admin-only auth guard

### 1B: Update comparison script

In `scripts/compare_ml_embeddings.py`, add `--url` flag:
- Default: use MLServiceClient directly (for Railway)
- With `--url https://rhodesli.nolanandrewfox.com`: call `/api/admin/ml-compare` endpoint
- Both paths return the same format

### 1C: Tests

- Test admin endpoint returns embeddings for a test image (mock ML service)
- Test admin endpoint rejects non-admin
- Test script `--url` mode with mock HTTP server

**Commit:** `feat(ml): session 121 phase 1 — AD-229 admin compare endpoint`
**/clear**

---

## Phase 2: UX-207 — Approvals Community-Scoped (15 min)

**Can be parallelized as worktree if admin_routes.py Phase 1 is done first**

### 2A: Filter pending uploads by community

In the admin approvals list handler:
- Get current community from `request.state.community`
- Filter `_load_pending_uploads()` results by community field
- Add community badge to each approval card

### 2B: Tests

- Test approvals filtered by community shows only matching items
- Test approvals without community shows all items (backward compat)
- Test approval card has community badge

**Commit:** `fix(ux): session 121 phase 2 — UX-207 approvals community-scoped`
**/clear**

---

## Phase 3: UX-212 — Source URL Saved During Upload (10 min)

### 3A: Trace the bug

Follow source_url from upload form → pending_uploads.json → approval → photo record:
1. Upload form: `source_url` field exists ✓
2. pending_uploads.json: `source_url` field saved ✓
3. Approval flow: Does it copy source_url to photo_index/Supabase?

### 3B: Fix

If source_url not propagated: add it to the approval copy step.
If it IS propagated but not displayed: fix the display.

### 3C: Tests

- Test that approving an upload preserves source_url in photo record
- Test that source_url appears on photo detail page

**Commit:** `fix(ux): session 121 phase 3 — UX-212 source URL persisted through upload`
**/clear**

---

## Phase 4: UX-208 — Always Show Community Badge (10 min)

**Touches app/main.py only — can parallelize with Phase 2/3**

### 4A: Modify badge logic

In `_cross_community_badge()` (main.py ~line 549):
- Instead of returning None for same-community, return a subtle badge with current community name
- Use muted styling (gray/slate) for same-community vs bright badge for cross-community
- Apply in `neighbor_card()` at ~line 9139

### 4B: Tests

- Test badge renders for same-community identity (was None)
- Test badge renders for cross-community identity (existing behavior)
- Test badge styling differs between same and cross community

**Commit:** `feat(ux): session 121 phase 4 — UX-208 always show community badge`
**/clear**

---

## Phase 5: UX-211 — Face Overlay Minimum Size (15 min)

**Touches page_routes.py + main.py CSS — can parallelize as worktree**

### 5A: Add minimum click target size

In the face overlay CSS (main.py ~line 1005-1034):
- Add `min-width: 44px; min-height: 44px;` to `.face-overlay` or equivalent
- Ensure text labels remain readable at small sizes
- For faces smaller than minimum: expand the overlay symmetrically around center

### 5B: Add zoom-on-hover for dense photos

When a face overlay is hovered on a photo with 8+ faces:
- Scale up the overlay slightly (transform: scale(1.3))
- Raise z-index to prevent overlap
- This is a CSS-only enhancement

### 5C: Tests

- Test face overlay has min-width/min-height CSS properties
- Test zoom-on-hover CSS rule exists for dense photos
- Test overlay renders correctly for small bounding boxes

**Commit:** `fix(ux): session 121 phase 5 — UX-211 face overlay minimum size`
**/clear**

---

## Phase 6: Feature Planning — TOOLS-003 + WORKSPACE-001 (15 min)

**Docs only — can parallelize as worktree**

### 6A: TOOLS-003 PRD

Create `docs/prds/053_face_compare_realtime.md`:
- Problem: Compare tool uses pre-computed embeddings only. Users can't upload a new photo and get instant results.
- Solution: ML service extension — add `/api/v1/embed` endpoint that returns embeddings for an uploaded photo.
- Wire into `/tools/compare` UI: upload → embed → compare against archive → show ranked results.
- Out of scope: ONNX export (too complex for the benefit).
- Acceptance criteria: upload a photo, see top 10 matches within 5 seconds.

### 6B: WORKSPACE-001 Implementation Plan

Review `docs/prds/036_workspace_onboarding.md` against current codebase:
- Document exact Supabase schema changes needed
- Document auth signup hook location
- Document UI changes (sidebar, community switcher)
- Write implementation plan in context file with session estimates

**Commit:** `docs: session 121 phase 6 — TOOLS-003 PRD + WORKSPACE-001 plan`
**/clear**

---

## Phase 7: Security Audit (10 min)

### 7A: Audit changed files

Review all files changed in this session for:
- SQL injection via Supabase queries
- Missing auth guards on new endpoints
- XSS in any user-provided content rendered to HTML
- Missing input validation
- OWASP top 10 concerns

### 7B: Document findings

Log any findings in `docs/session_context/session-121-security-audit.md`.
Fix any P0/P1 issues immediately. P2+ → BACKLOG.

**Commit:** `docs: session 121 phase 7 — security audit`
**/clear**

---

## Phase 8: Harness Outputs + Gap Check (15 min)

### 8A: Final Documentation

1. Assessment: `docs/assessments/session-121-assessment.md`
2. CHANGELOG: v0.99.31
3. ROADMAP: update item statuses
4. SESSION_HISTORY: Session 121 entry
5. Session log: `docs/session_logs/session-121-log.md`
6. BACKLOG: update UX-207, UX-208, UX-211, UX-212 statuses

### 8B: Gap Check

Re-read THIS PROMPT (docs/prompts/session-121-prompt.md) and verify:
- Every phase completed
- Every test passing
- Every artifact created
- Auto-fix any gaps found

### 8C: Browser Verification (READ-ONLY)

Screenshots of:
1. Approvals page with community filter (UX-207)
2. Person page with always-visible community badges (UX-208)
3. Photo page with minimum-size face overlays (UX-211)
4. Photo detail with source URL displayed (UX-212)

**Commit:** `docs: session 121 harness outputs — assessment, changelog, roadmap`

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| AD-229 endpoint works? | Test | Returns embeddings, admin-only |
| UX-207 approvals scoped? | Test + browser | Filtered by community |
| UX-212 source URL saved? | Test + browser | URL persisted and displayed |
| UX-208 badges always show? | Test + browser | Badge on all suggestion cards |
| UX-211 min overlay size? | Test + browser | 44px minimum, hover zoom |
| TOOLS-003 PRD exists? | `ls docs/prds/053*` | Exists |
| WORKSPACE-001 plan? | Context file | Implementation plan documented |
| Security audit clean? | Audit file | No P0/P1 issues |
| All tests pass? | `make test-fast` | PASS |
| Assessment exists? | `ls docs/assessments/session-121*` | Exists |
| `git log origin/main..HEAD` empty? | git log | Empty |

## Parallelization

**3 parallel worktrees possible:**

- **Worktree A:** Phase 5 (UX-211) — page_routes.py + main.py CSS section only
- **Worktree B:** Phase 6 (TOOLS-003 PRD + WORKSPACE-001 plan) — docs only
- **Sequential on main:** Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 (all touch admin_routes.py or main.py logic)
- **Phase 7:** Security audit (after all code changes)
- **Phase 8:** Harness (after all worktrees merged)

Merge order: docs-only first, then code. Run tests after each merge.
