# Session 129 — Interactive Feedback Triage + Performance Step-Function

@docs/session_context/session-129-context.md
@tasks/lessons.md

## Goal

Three parallel tracks: (A) collect and log every piece of UX feedback while Nolan triages the Fox Family archive, (B) find and ship an order-of-magnitude performance improvement, and (C) fix the P0 community scoping bug where Focus mode leaks to wrong community after actions.

**Session mode: interactive** — User gives real-time feedback (screenshots, voice notes, text). Log EVERYTHING as FB-NNN per `.claude/rules/interactive-session-feedback.md`.

**CRITICAL: Do not break existing functionality. Do not cause data issues. Run tests before every commit.**

---

## Phase 0: Orient + Launch (5 min)

1. Set session mode: `echo "interactive" > .claude/session_mode.txt`
2. Create session log: `docs/session_logs/session-129-log.md`
3. Create feedback file: `docs/feedback/session-129-feedback.md`
4. Baseline: `make test-fast`
5. Read previous performance work: grep PERF in BACKLOG.md

**Then immediately launch Track B as a background subagent.**

---

## Track A: Feedback Collection (orchestrator — runs entire session)

You are the orchestrator. Stay responsive to user messages at all times.

### For every piece of feedback:
1. Assign FB-NNN ID (continue from FB-001)
2. Log immediately to `docs/feedback/session-129-feedback.md`
3. Categorize severity: P0 (broken) / P1 (painful) / P2 (annoying) / P3 (polish)
4. Tag category: PERF / UX / BUG / MOBILE / NAVIGATION / DATA
5. Ask follow-up questions when needed:
   - "What were you trying to do?"
   - "What did you expect to happen?"
   - "What device/browser?"
   - "Can you screenshot the current state?"
6. If it's a quick fix (< 5 min), fix it immediately in a subagent
7. If it's a perf issue, note it for Track B

### Feedback entry format:
```
### FB-NNN: [Title]
- **Severity:** P0/P1/P2/P3
- **Category:** PERF / UX / BUG / MOBILE / NAVIGATION / DATA
- **Context:** [What user was doing, what happened, what should have happened]
- **Device:** [mobile/desktop, browser if known]
- **Screenshot:** [if captured]
- **Root cause:** [if identified, or TBD]
- **Fix:** [FIXED / BACKLOG — effort estimate]
```

---

## Track B: Performance Step-Function (background subagent in worktree)

Launch as a background worktree subagent with this prompt:

> You are working on the Rhodesli heritage photo archive. Your ONLY goal is to find and fix the top 3 performance bottlenecks that will produce an order-of-magnitude improvement in user-perceived speed. The app is "at least 10x too slow" on mobile.
>
> ### Step 1: Profile (30 min)
> Read the app code and identify the top bottlenecks:
> - `app/main.py` — how are pages rendered? What's the server-side time?
> - `core/neighbors.py` — frozen, but how is it called? Cached?
> - Supabase reads: grep for `supabase.table()` calls in request paths
> - Supabase writes: grep for `save_registry`, `save_photo_registry`, any `.upsert()` in request-path code
> - Photo serving: how are images served? Any optimization?
> - HTMX swap sizes: are we sending full page HTML for partial updates?
>
> ### Step 2: Measure (15 min)
> - Add `time.time()` instrumentation to the 5 slowest endpoints (wrap in try/finally, log to structlog)
> - Identify which endpoints take >500ms server-side
> - Check HTMX response sizes (are we sending too much HTML per swap?)
>
> ### Step 3: Fix the Top 3 (60 min)
> Likely candidates:
> 1. **Targeted Supabase writes** — `save_registry()` writes ALL identities. Change to write only the changed identity.
> 2. **Response size reduction** — If HTMX swaps return >50KB, reduce to minimal required HTML.
> 3. **Photo thumbnail optimization** — Add width/height attributes, lazy loading, consider serving smaller images.
> 4. **HTTP cache headers** — Static assets and unchanged API responses should be cached.
> 5. **Optimistic UI** — Return success HTML immediately, write to Supabase in background thread.
>
> ### Rules
> - `source venv/bin/activate` before running tests
> - `make test-fast` must pass before committing
> - Commit after each fix with measurements: `perf: [what] — [before]ms → [after]ms`
> - Do NOT modify data/ files, core/neighbors.py, or core/pfe.py
> - Focus on USER-PERCEIVED speed, not just server metrics

---

## Track C: Community Scoping Bug Fix (background subagent in worktree)

**P0 BUG**: When triaging in Focus mode on `/c/fox-family/?section=to_review`, after performing an action (merge, skip, confirm, "not same"), the NEXT identity shown is from the wrong community (Rhodes instead of Fox Family). The URL still says `/c/fox-family/` but the content leaks to the global/Rhodes pool.

Launch as a background worktree subagent:

> You are fixing a P0 community scoping bug in the Rhodesli heritage photo archive.
>
> ### The Bug
> On `/c/fox-family/?section=to_review` in Focus mode, after any action (merge, skip, confirm, reject), the next identity shown comes from the wrong community. The sidebar still shows "Fox Family Archive" but the main content shows Rhodes community people.
>
> ### Root Cause Investigation
> 1. Find the Focus mode "next identity" endpoint — grep for `section=to_review`, `view=focus`, or `next` in `app/main.py` and `app/identity_routes.py`
> 2. Check if the HTMX `hx-get` or `hx-post` on action buttons (Merge, Skip, Confirm, Not Same) passes the community slug
> 3. Check if the endpoint that returns the next identity filters by community
> 4. The community prefix `/c/fox-family/` should scope ALL queries. If the action endpoint redirects or returns a new identity without community filtering, that's the bug.
> 5. Also check: does the `_get_next_focus_identity()` or equivalent function accept and use a community parameter?
>
> ### Known Context
> - Community middleware sets `request.state.community` from the URL prefix
> - Lesson 109: CommunityMiddleware /api/ skip creates dual-path problem — HTMX URLs must include /c/ prefix
> - Lesson 112: Community-scoped pages must filter ALL sections
> - Previous partial fix in Session 111 (community prefix sweep)
> - This bug has been reported before and "fixed" but persists
>
> ### Fix
> - Ensure ALL action endpoints (merge, skip, confirm, reject-match, not-same) pass community_slug to the next-identity lookup
> - Ensure the next-identity lookup filters identities by community
> - Write tests that verify: after a community-scoped action, the next identity is from the same community
>
> ### Rules
> - `source venv/bin/activate` before tests
> - `make test-fast` must pass
> - Do NOT modify data/ or core/ files
> - Write at least 3 tests for this fix
> - Commit: `fix(community): session 129 — focus mode community scoping after actions`

---

## Phase 1: Merge Track B + C Results (when subagents complete)

1. Review changes for safety
2. Merge worktree to main
3. Run tests
4. Deploy
5. Log before/after measurements

---

## Track D: Observability Audit (quick, can be done by orchestrator)

User expects that admin actions (merge, skip, confirm, reject) are logged with enough detail to debug issues. Check:
1. Are all identity mutation actions logged to `audit_log` table? (Session 113 added 22 calls)
2. Are the logs queryable — can we see what the user did, when, and what identity was affected?
3. If NOT: add structlog entries for every Focus mode action with: action type, identity_id, community_slug, timestamp, user email
4. This feeds into the broader goal of understanding usage patterns and debugging UX issues

---

## Track E: Antigravity Monitor (orchestrator checks periodically)

Antigravity is running on branch `session-129/antigravity-mobile` with prompt `docs/prompts/session-129-antigravity-prompt.md`. It's doing mobile responsiveness + delightful micro-interactions.

When user confirms Antigravity is done:
1. Review the branch diff for safety (no data/, core/, auth changes)
2. Cherry-pick safe changes to main
3. Fix any CSS typos or test assertion breakages
4. Run tests

## Track F: Codex Audit Integration

Use Codex for:
1. **Planning audit**: Before implementing perf fixes, have Codex review the plan
2. **Outcome audit**: After Track B/C complete, have Codex audit all changes
3. **Performance profiling**: Codex is good at finding backend bottlenecks — iterate with it
4. Write Codex findings to `docs/session_context/session-129-codex-audit.md`

## PRD/SDD Enforcement

Per `.claude/rules/spec-driven-development.md`:
- Any feature change >30 min needs a PRD in `docs/prds/`
- Performance changes should document before/after in ALGORITHMIC_DECISIONS.md
- Community scoping fix (Track C) is a bug fix — no PRD needed, but write tests first

## Context Persistence

**CRITICAL**: All feedback must be written to disk immediately via background subagents. If the session crashes or compacts, feedback must survive. Use this pattern:
1. User gives feedback → immediately spawn background subagent to write to `docs/feedback/session-129-feedback.md`
2. Continue conversation — don't block on file writes
3. At milestones, verify the feedback file has all entries

---

## Phase 2: Session End

1. Compile all feedback into prioritized list
2. Write `docs/prompts/session-130-prompt.md` — async fix session for top feedback items
3. Standard harness close-out (assessment, CHANGELOG, ROADMAP, SESSION_HISTORY)
4. Deploy + browser verify
5. Run /session-review

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| All feedback logged? | Count FB entries | Every user message captured |
| Performance improved? | Before/after measurements | Measurable improvement |
| Tests pass? | `make test-fast` | PASS |
| Assessment exists? | File check | Exists |
| Feedback file complete? | Each FB has severity + category | All entries complete |
| `git log origin/main..HEAD` empty? | git log | Empty |
