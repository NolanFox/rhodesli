# Session 126 — Polish Sprint + Codex Audit + Delight

@docs/session_context/session-126-context.md
@tasks/lessons.md

## Goal

Fix all outstanding Session 125 gaps, run Codex audit-and-fix cycles, and ship delightful UX improvements via Antigravity. The app should feel polished and modern when done.

## Pre-Requisites

```bash
echo "126" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline
```

---

## Phase 0: Orient + SQL Indexes (10 min)

1. Create session log
2. Create admin migration endpoint `/api/admin/run-migrations` that executes:
   ```sql
   CREATE INDEX IF NOT EXISTS idx_photo_communities_community_id ON photo_communities (community_id);
   CREATE INDEX IF NOT EXISTS idx_identity_communities_community_id ON identity_communities (community_id);
   ```
3. Call it via curl on production after deploy
4. Add `_check_admin` guard — admin only

**Commit + /clear**

---

## Phase 1: Flaky Test Fix (20 min)

1. Run `pytest tests/ -q --timeout=60 --ignore=tests/e2e -x` to identify first failure
2. Root cause: module-level cache state persisting between test files
3. Fix by adding teardown fixtures that reset `_face_data_cache`, `_registry_cache`, etc.
4. Verify: full suite passes with zero ordering-dependent failures

**Commit + /clear**

---

## Phase 2: Speed-Run reviewed_ids Wiring (20 min)

1. Read the speed-run JS block in `cluster_review_routes.py` (~line 900-1000)
2. Add JS-side accumulation: when a speed-run action fires, append the identity_id to a `reviewedIds` array
3. Include `reviewed_ids` as a query parameter on all speed-run action buttons (confirm-all, reject-all, skip, dismiss)
4. Test: simulate a skip then verify the skipped ID appears in the next request's reviewed_ids

**Commit + /clear**

---

## Phase 3: P3 UX Quick Wins — Worktree Subagents (30 min)

Launch parallel worktree subagents for independent fixes:

### Subagent A: Sidebar + Top Bar (app/main.py)
- Dim zero-count sidebar items (text-slate-600, no badge when count=0)
- Sequential display names: "Unidentified Person 1043" not "efb4d153"

### Subagent B: Compare + 404 (app/compare_routes.py, app/main.py)
- Tools subnav link padding (py-3 on individual links)
- "Compare against all archive" → primary indigo style
- 404 nav: add Photos/People links
- 404: add "Go back" secondary link

### Subagent C: People Grid (app/browse_routes.py)
- Subtitle: add "awaiting identification" count
- Share link: add icon, slightly more visible

Merge all worktrees, run tests.

**Commit + /clear**

---

## Phase 4: Codex Audit Cycle (30 min)

Run Codex as read-only auditor:

> "Audit the deployed codebase for UX consistency, visual bugs, accessibility issues, and design inconsistencies. Read all route files in app/. Write findings to docs/session_context/session-126-codex-ux-audit.md. Do NOT modify any code."

Review findings. For each:
- High-impact + quick fix → implement immediately
- Needs design work → BACKLOG with breadcrumb
- False positive → skip

May do 2-3 audit-and-fix rounds.

**Commit + /clear**

---

## Phase 5: Merge Antigravity + Deploy + Verify (30 min)

1. Check for Antigravity branch `session-126/antigravity-delight`
2. Review with same safety checklist as Session 125:
   - No data/ changes, no core/ changes, no auth guard removals
   - No route path changes, no Supabase query changes
3. Cherry-pick safe changes, reject unsafe ones
4. Full test suite
5. Deploy + browser verify all major surfaces
6. Run /ux-review skill on screenshots

**Commit + /clear**

---

## Phase 6: Harness Outputs (10 min)

1. Assessment: `docs/assessments/session-126-assessment.md`
2. CHANGELOG: v0.99.36
3. ROADMAP + SESSION_HISTORY
4. BACKLOG updates

**Commit + Push**

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| SQL indexes created? | curl admin endpoint | Indexes exist |
| Flaky tests fixed? | Full suite no failures | 0 ordering failures |
| reviewed_ids wired? | Test | JS passes IDs through |
| P3 UX items fixed? | Browser | Visual improvements |
| Codex audit done? | File exists | Audit doc with findings |
| Antigravity merged? | git log | Commit or BACKLOG note |
| All tests pass? | `make test-fast` | PASS |
| Assessment exists? | File check | Exists |
| `git log origin/main..HEAD` empty? | git log | Empty |
