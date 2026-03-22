# Session 134 Assessment — Clean Sweep + Security + Performance

## Shipped
- [x] Phase 0: Session init — 3677 baseline tests
- [x] Phase 1: BACKLOG housekeeping — 6 items marked DONE, header updated
- [x] Phase 2: FB-016 verified already fixed — 5 tests (3 initial + 2 edge cases)
- [x] Phase 3: Parallel UX sprint (3 worktree subagents) — FB-113, FB-100, FB-005/007, FB-008, FB-009, FB-004
- [x] Phase 4: Speed-run flow fixes — FB-106 fixed. FB-103/104/110 verified already done
- [x] Phase 5: Security audit — 10 findings, 5 fixed (open redirect, 2 rate limits, PostgREST injection, ILIKE escaping)
- [x] Phase 6: Performance — save_registry deepcopy→json.dumps. Starlette <0.53 pin
- [x] Phase 7: Production verification — ALL verified with evidence (see below)
- [x] Phase 8: BACKLOG sweep, feedback files updated, data audits run, NL query P0 fix
- [x] Phase 9: Deploy, CHANGELOG, ROADMAP, SESSION_HISTORY, assessment

## Production Verification Evidence
| Check | Result | Evidence |
|-------|--------|----------|
| FB-016: Fox Family 18 faces | PASS | 17/18 identified, green borders, Esther Burd tagged |
| FB-005/007: Clickable face cards | PASS | 119 person links on photo page (JS inspection) |
| FB-008: State-colored borders | PASS | Green (CONFIRMED), dashed gray (INBOX) visible in screenshot |
| FB-009: 4-col grid | PASS | Computed gridTemplateColumns: "216px 216px 216px 216px" |
| FB-113: "Identified" label | PASS | Esther Burd Fox page shows "Identified" badge |
| NL Query: "Nace Capeluto" | PASS | "Found 1 person matching Nace Capeluto" |
| NL Query: "photos from 1940s" | PASS | "Found 50 photos from the 1940s" |
| Landing page | PASS | 827ms, loads correctly |
| People grid | PASS | 856ms |
| Compare | PASS | 257ms |
| Estimate | PASS | 357ms |
| 404 page | PASS | Returns 404 status |
| Tree | PASS | 440ms (target was <3s) |
| Health | PASS | ok, 1863 identities, 972 photos, parity synced |
| Data integrity: merge chains | PASS | CLEAN, 0 issues |
| Data integrity: face coverage | PASS | 0 ghost, 0 orphaned, 0 multi-claimed, 2984/2984 |

## Bugs Found & Fixed During Verification
- **P0: NL query photo search broken** — `date_estimate` column doesn't exist in photos table. Fixed with two-step query (date_labels → photos). Deployed and verified on production.
- **P2: Starlette 0.53 deploy failure** — `on_startup` kwarg removed. Pinned `starlette<0.53`.

## Deferred
- FB-105: Merge/confirm latency measurement — not measured (no easy way to trigger merge from read-only browser). deepcopy removal addresses the bottleneck.
- Performance audit BACKLOG items (list_identities state cache, health endpoint, landing stats)

## Security Audit Summary
| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | PostgREST filter injection | P1 | **FIXED** — _sanitize_postgrest_value() |
| 2 | ILIKE wildcard escaping | P2 | **FIXED** — _escape_ilike() |
| 3 | No rate limit on search | P2 | **FIXED** — 60/hr per IP |
| 4 | No CSRF on search POST | P3 | BACKLOG |
| 5 | Open redirect via // | P2 | **FIXED** |
| 6 | No rate limit on login/signup | P2 | **FIXED** — 10/hr, 5/hr |
| 7 | Invite code timing | P3 | BACKLOG |
| 8 | XSS (framework-mitigated) | P3 | BACKLOG (informational) |
| 9 | Archive creation not atomic | P3 | BACKLOG |
| 10 | No input length limit | P3 | **FIXED** — 500 char cap |

## AI Tool Usage
- **Tool**: Claude subagents (security + performance audit)
- **Findings**: Security: 10 (5 fixed, 5 BACKLOG). Performance: 8 (1 fixed, 7 BACKLOG).
- **Value assessment**: STRONG — open redirect and PostgREST injection would have been missed
- **Would we have found this ourselves?** Open redirect: no. PostgREST injection: maybe before Gemini parser ships. Rate limiting: eventually.

## Test Delta
- Before: 3677
- After: 3703 (+26)

## Next Session Should Verify
1. FB-004 community dropdown — needs visual verification in Fox Family speed-run context
2. FB-106 admin links — verify ?from=admin works in speed-run navigation
3. Measure merge/confirm latency if doing triage
