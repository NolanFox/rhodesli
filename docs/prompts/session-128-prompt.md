# Session 128 — Security Hardening + Accessibility + Dead Code Cleanup

@docs/session_context/session-128-context.md
@tasks/lessons.md

## Goal

Fix all actionable findings from the Session 127 security audit. Ship accessibility quick wins. Remove dead code. Merge Antigravity visual polish. Zero new features — this is a hardening session.

**Session mode: interactive** — User is testing uploads on production concurrently. Document any feedback as FB-NNN items per `.claude/rules/interactive-session-feedback.md`.

---

## Phase 0: Orient (5 min)

1. Create session log
2. Read Session 127 audit: `docs/session_context/session-127-codex-audit.md`
3. Baseline: `make test-fast`

**Commit + /clear**

---

## Phase 1: Security Hardening — Parallel Worktree Subagents (40 min)

### Subagent A: CSRF + Origin Check (app/auth.py, app/main.py)
- Set `SameSite=Strict` on session cookies (find where cookies are set in auth.py)
- Create `_check_origin(request)` helper: validate Origin/Referer header matches app domain
- Wire `_check_origin` into the 10 most dangerous POST routes: merge, confirm, reject, skip, rename, detach, upload-approve, annotation-approve, run-migrations, sync endpoints
- If Origin/Referer is missing or doesn't match, return 403

### Subagent B: Rate Limiting (new app/rate_limit.py, app/compare_routes.py, app/match_facecompare_routes.py, app/estimate_routes.py, app/page_routes.py)
- Create `app/rate_limit.py` with in-memory IP-based rate limiter (20 uploads/hour)
- Wire into all 6 public upload endpoints:
  - `/api/compare/upload`
  - `/api/compare/upload-multiple`
  - `/api/compare/pair/upload`
  - `/api/facecompare/upload`
  - `/api/upload/stream`
  - `/api/estimate/upload`
- Return 429 Too Many Requests when exceeded
- Also wire into `/api/compare/result/{result_id}/respond`

### Subagent C: Token + Duplicate Routes (app/compare_routes.py, app/admin_routes.py, app/browse_routes.py, app/page_routes.py)
- ML_SERVICE_TOKEN: Add startup warning if `ML_SERVICE_URL` is set but token is `"dev-token"`
- Remove duplicate route `/api/identity/{identity_id}/reject-match/{neighbor_id}` from `browse_routes.py` (keep in `identity_routes.py`)
- Remove duplicate route `/api/photo/{photo_id}/correct-date` from `page_routes.py` (keep in `photo_routes.py`)
- Remove duplicate route `/api/face-alignment/{photo_id}` from `page_routes.py` (keep in `photo_routes.py`)

Merge all, run tests.

**Commit + /clear**

---

## Phase 2: Accessibility Quick Wins — Parallel Worktree Subagents (30 min)

### Subagent D: Structural A11Y (app/main.py)
- Add skip-to-content link as first focusable element: `<a href="#main-content" class="sr-only focus:not-sr-only ...">Skip to main content</a>`
- Add `id="main-content"` to the main content area
- Wrap primary content in `<Main>` element on pages that lack it
- Add visible focus indicators: `focus:ring-2 focus:ring-indigo-400 focus:outline-none` on interactive elements (buttons, links, inputs) via base styles

### Subagent E: Image + Button A11Y (app/main.py, app/person_routes.py, app/cluster_review_routes.py, app/identity_routes.py)
- Add `alt` text to all `Img()` calls that display face crops: `alt=f"Face of {name}"` or `alt="Face thumbnail"`
- Add `aria-label` to the top 50 icon-only `Button()` elements (close, reject, skip, merge, compare, share, navigation arrows)
- Focus on buttons that only contain SVG icons with no visible text

Merge all, run tests.

**Commit + /clear**

---

## Phase 3: Dead Code Cleanup (15 min)

Can be done on main (small, safe changes):
1. Delete `app/compare_v2_routes.py` and remove its import from `app/main.py`
2. Move `app/audit_notes.md` → `docs/audit_notes.md`
3. Move `app/ui_spec.md` → `docs/ui_spec.md`
4. Remove duplicate `sys.path` insertion in `app/main.py` (line 60, keep line 24)
5. Check if `CONTRIBUTOR_EMAILS` env var is wired end-to-end; if not, add a comment noting status
6. Fix top bar label: "TO REVIEW" → match sidebar label text exactly

Run tests.

**Commit + /clear**

---

## Phase 4: Merge Antigravity + Codex Audit (20 min)

### 4A: Merge Antigravity
1. Check for branch `session-128/antigravity-polish`
2. Safety checklist (same as always):
   - No data/ changes, no core/ changes, no auth guard removals
   - No route path changes, no Supabase query changes
   - Only modifies person_routes.py and cluster_review_routes.py
   - CSS/HTML template changes only — no Python logic
3. Cherry-pick safe changes, reject unsafe
4. Run tests after merge

### 4B: Codex Audit
Run Codex as READ-ONLY auditor on all changes made this session:

> "Audit the changes made in Session 128. Focus on: (1) Does the CSRF origin check have bypasses? (2) Does the rate limiter have race conditions or memory leaks? (3) Do the duplicate route removals break any navigation links? (4) Are the accessibility additions correct (aria roles, focus management)? (5) Did Antigravity changes break any functionality? (6) Are there any regressions? Read all modified files in app/. Write findings to docs/session_context/session-128-codex-audit.md. Do NOT modify any code."

Triage findings. Fix P0/P1 immediately.

**Commit + /clear**

---

## Phase 5: Deploy + Verify + Harness (15 min)

Standard session-end per `.claude/rules/session-defaults.md`.

**Commit + Push**

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| CSRF origin check active? | curl with bad Origin | 403 returned |
| Rate limiter works? | curl 21+ uploads | 429 on 21st |
| Token default fails? | grep for warning | Startup log or assertion |
| Duplicate routes removed? | grep for route path | 1 definition only |
| Skip-to-content link? | Browser | SR-only link present |
| `<main>` landmark? | Browser inspect | Main element on key pages |
| Alt text on crops? | grep `alt=` | Coverage on Img() calls |
| Dead code removed? | `ls app/compare_v2_routes.py` | File not found |
| Antigravity merged? | git log | Commit or BACKLOG note |
| All tests pass? | `make test-fast` | PASS |
| Assessment exists? | File check | Exists |
| `git log origin/main..HEAD` empty? | git log | Empty |
