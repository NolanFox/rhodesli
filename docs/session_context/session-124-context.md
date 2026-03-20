# Session 124 Context — Performance Blitz + UX Design Audit

**Predecessor:** [Session 123 Context](session-123-context.md)
**Codex Audit:** [Session 123 Codex Performance Audit](session-123-codex-perf-audit.txt)

## Strategy

Two parallel tracks running simultaneously:

### Track A: Performance (Codex-assisted)
Implement the remaining 4 high-value Codex findings from the Session 123 audit.

**Item #2: Recursive speed-run prefetch (CRITICAL)**
- `cluster_review_routes.py:1917,2251` — each card contains `hx_trigger="load"` prefetch that renders another card with another prefetch
- 179 cascading requests on a single page load
- Fix: Strip nested prefetch from prefetched cards, or prefetch only the next card (not the whole queue)

**Item #5: Missing community_id indexes (QUICK WIN)**
- `photo_communities` and `identity_communities` tables filter by `community_id` but only have composite PKs starting with photo_id/identity_id
- Fix: Add `CREATE INDEX` on community_id for both tables
- SQL file: `scripts/sql/session_124_community_indexes.sql`

**Item #9: CDN Tailwind → precompiled CSS (MEDIUM)**
- `main.py:198,208,223` — runtime Tailwind from cdn.tailwindcss.com blocks first paint
- Fix: Precompile to static CSS, self-host
- Risk: High — Tailwind runtime JIT generates CSS on-the-fly based on class usage. Precompiling requires a build step.
- **Decision: DEFER** — too risky for a sprint. Add to BACKLOG as PERF-012.

**Item #3: Unresolved review groups O(n²) (MEDIUM)**
- `cluster_review_routes.py:514,560,565` — builds full distance matrix for 1571 identities (815ms)
- Fix: Cache by registry version, skip matrix computation when result is cached
- This is essentially adding a TTL cache like we did for speed-run clusters

### Track B: UX/Design (Antigravity-assisted)
User pastes a design audit prompt into Antigravity. Antigravity reviews the codebase and produces UX recommendations. Claude Code implements the top findings.

**Focus areas for Antigravity:**
1. Mobile landing page experience
2. Speed-run triage visual hierarchy
3. Person page information architecture
4. Compare tool guided flow
5. Emotional design — heritage archive warmth

**Implementation approach:**
- User pastes Antigravity prompt into Antigravity IDE
- Antigravity produces recommendations (saved to a file)
- Claude Code reads recommendations and implements top 5

## Parallelization

| Track | Phase | Files | Parallel? |
|-------|-------|-------|-----------|
| A-1: Recursive prefetch fix | cluster_review_routes.py | YES — worktree |
| A-2: Community indexes SQL | scripts/sql/ | YES — worktree (docs only) |
| A-3: Review groups cache | cluster_review_routes.py | SAME FILE as A-1, sequential |
| B-1: UX implementation | page_routes.py, main.py | YES — worktree after Antigravity output |

**Execution plan:**
1. Phase 0: Orient, generate Antigravity prompt for user
2. Phase 1: Codex perf — recursive prefetch fix (cluster_review_routes.py)
3. Phase 2: Codex perf — community indexes SQL (scripts/sql/)
4. Phase 3: Codex perf — review groups cache (cluster_review_routes.py)
5. Phase 4: UX implementation from Antigravity findings (depends on user providing output)
6. Phase 5: Security audit + harness outputs + gap check

If Antigravity output isn't available yet when Phase 3 finishes, do screenshot-based UX analysis as fallback.

## Breadcrumbs
- Codex audit: `docs/session_context/session-123-codex-perf-audit.txt` (10 findings)
- Performance memory: Codex finding #2 (recursive prefetch) is the single highest-impact item
- UX backlog: UX-077/078 (compare), UX-130 (landing — partially done), UX-061 (contributor mgmt)
- AD-229: Remind user about upload testing
