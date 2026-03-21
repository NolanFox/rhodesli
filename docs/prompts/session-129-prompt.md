# Session 129 — Interactive Feedback Triage + Performance Step-Function

@docs/session_context/session-129-context.md
@tasks/lessons.md

## Goal

Dual-track session: (A) collect and log every piece of UX feedback while Nolan triages the Fox Family archive, and (B) find and ship an order-of-magnitude performance improvement in parallel.

**Session mode: interactive** — User gives real-time feedback (screenshots, voice notes, text). Log EVERYTHING as FB-NNN per `.claude/rules/interactive-session-feedback.md`.

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

## Phase 1: Merge Track B Results (when subagent completes)

1. Review changes for safety
2. Merge worktree to main
3. Run tests
4. Deploy
5. Log before/after measurements

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
