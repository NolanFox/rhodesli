# Session 129 Context — Interactive Feedback Collection + Performance Step-Function

**Predecessor:** [Session 128 Context](session-128-context.md)
**Assessment:** [Session 128 Assessment](../assessments/session-128-assessment.md)

## Goal

Two parallel tracks running simultaneously:

### Track A: Interactive Feedback Collection (orchestrator)
Nolan triages the Fox Family archive on mobile + desktop, giving real-time feedback on every issue he encounters. Claude logs every item as FB-NNN, asks follow-up questions, and captures screenshots. The goal is to build a comprehensive feedback backlog that can be fixed in subsequent async sessions.

### Track B: Performance Step-Function (background subagent)
Find and implement changes that produce an order-of-magnitude performance improvement. Current state is "at least 10x too slow" per user. Focus areas:
- Photo loading speed (especially mobile)
- Merge/confirm/skip action response time
- Family tree linking speed
- General page load time
- Every user action that creates a visible delay

## Why Now

Nolan tried to demo the app to David (while David was with uncle Charlie) and couldn't get links out fast enough on mobile. The app is functionally complete but operationally unusable at current performance levels. This is blocking community adoption.

## Performance History

### What's Been Done (Sessions 111-125)
- Session 111f: Vectorized confirmed identity distances, smart cache invalidation. Focus mode 124ms (was 3-5s).
- Session 114: PERF-001 test speed <30s achieved.
- Session 123: PERF-A cached embeddings, PERF-B save_registry changed_ids.
- Session 124: Recursive prefetch fix (179 cascading requests eliminated), review groups O(n^2) cache.
- Session 125: Registry SWR, cold start to background, unified embeddings parse, surgical cache invalidation.

### Known Remaining Bottlenecks
- `save_registry()` still writes ALL identities to Supabase on every mutation (should write only changed identity) — partially addressed Session 111d but still slow
- TTL cache reloads (identities 380KB, photos 436KB, photo_faces 293KB every 120s)
- No CDN/edge caching for static assets or API responses
- Photo thumbnails not optimized (full-resolution served to mobile)
- No lazy loading / virtual scrolling on large grids
- HTMX swaps do full re-renders instead of surgical DOM updates
- Supabase round-trips on every mutation (no batching, no optimistic UI)

### Performance Investigation Approach
1. **Measure first**: Use browser DevTools network waterfall, Lighthouse scores, and server-side timing logs
2. **Identify the 3 biggest bottlenecks** by wall-clock time
3. **Fix the biggest one first** — likely photo serving or Supabase write path
4. **Candidate solutions**:
   - R2 image optimization (WebP, thumbnails at multiple sizes)
   - Optimistic UI (show success immediately, write in background)
   - Supabase write batching / targeted writes
   - HTTP cache headers on static responses
   - Virtual scrolling for 800+ item grids
   - Service worker for offline-first feel
   - Edge caching via Cloudflare

## Parallelization Plan

Track A runs in the orchestrator context — it must stay responsive to user messages.
Track B runs as a background subagent (or Codex task) doing performance research and implementation.

### Track A: Feedback Collection (orchestrator)
- Receive screenshots, voice notes, text feedback
- Assign FB-NNN IDs immediately
- Write to `docs/feedback/session-129-feedback.md`
- Ask follow-up questions when context is ambiguous
- Categorize: P0 (broken), P1 (painful), P2 (annoying), P3 (polish)

### Track B: Performance (background subagent)
- Profile the app: identify top 3 bottlenecks by wall-clock time
- Implement fixes in worktree
- Run tests after each fix
- Report back with before/after measurements

## Breadcrumbs
- Performance root causes: `docs/feedback/session-128-feedback.md`, memory `Speed-Run Performance Root Causes`
- Previous perf sessions: 111f, 123, 124, 125
- Supabase egress: `.claude/rules/egress-budget.md`, memory `project_supabase_egress.md`
- BACKLOG perf items: PERF-001 through PERF-011
