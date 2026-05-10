# Session 158d Log

**Date**: 2026-05-10
**Mode**: implementation
**Outcome**: PARTIAL — RENAME landed once, ROLLBACK per safety rule, app 502 cascade discovered (Lesson 185), PGRST002 root cause diagnosed post-closeout (Lesson 186)
**Assessment**: `docs/assessments/session-158d-assessment.md`

## Phase Checklist

- [x] Phase 158d-1: Apply cutover patches (`1cabf2d5`)
- [x] Phase 158d-2: RENAME executed → REVERSIBLE state (`b2a5583e`)
- [x] Phase 158d-3: ROLLBACK per 5xx rule (DB restored cleanly)
- [-] Phase 158d-4: wait period (skipped — rollback path)
- [-] Phase 158d-5: DROP + VACUUM (NOT executed — correct, rolled back)
- [-] Phase 158d-6: post-cutover verification (NOT executed — no cutover state)
- [x] Phase 158d-7: Closeout (`b15ae233`)
- [x] Post-closeout: 158e prompt v1 (`ae1deb8a`) + PGRST002 root cause (`c78af606`) + Lesson 186 (`be9da284`)

## Timeline (UTC)

- **02:11Z** — Session start, baseline test-fast (4269 + 1 flaky retry)
- **02:16Z** — Phase 158d-1 patches applied, dry-run gate verified
- **02:17Z–02:23Z** — RENAME attempts 1–4 fail at lock_timeout
- **02:23Z** — Discovered 16 zombie idle-in-transaction backends from 158b cursor backfill (idle 17–22h)
- **02:23Z** — `pg_terminate_backend` cleared all 16 → RENAME succeeded immediately
- **02:23Z–02:30Z** — Smoke test returns 502 across all 11 routes; per safety rule, executed `--rollback`
- **02:30Z** — DB rolled back: v1 alive 3/3, no `_dropped_*_session158`
- **02:30Z–02:55Z** — Production stayed 502 for ≥ 25 min despite rollback; Railway redeploys (cutover RENAME and closeout) BOTH failed network healthchecks
- **02:55Z** — Closeout commits + push, session-end attempted
- **03:25Z–03:39Z** — Post-closeout investigation via Railway CLI: `railway logs` revealed PGRST002 (PostgREST schema cache stuck) was the actual root cause behind deploy-healthcheck failures
- **03:39Z** — `NOTIFY pgrst, 'reload schema'` from psycopg2 — did NOT recover the cache
- **03:43Z** — 158e prompt updated with PGRST002 root cause + Supabase restart instruction
- **03:44Z+** — Lesson 186 added to lessons.md + harness-lessons.md

## Critical findings

1. **Lesson 184**: zombie idle-in-transaction backends from 158b cursor backfill survived 22 hours holding AccessShareLock
2. **Lesson 185**: `pg_terminate_backend` on hot production pool cascaded into worker crashes (workers held aliases to terminated backends)
3. **Lesson 186**: Supabase PostgREST schema cache stuck after RENAME+ROLLBACK with PGRST002; `NOTIFY pgrst` insufficient; dashboard restart required

## Tests

- `make test-fast`: 4269 pass + 1 flaky REST timeout that passes on retry (same flake pattern from 158c)

## Commits (6, all pushed)

- `1cabf2d5` fix(session-158d): cutover lock_timeout + Codex 158c P1/P2 fixes
- `b2a5583e` feat(session-158d): cutover RENAME v1 → _dropped_session158 (REVERSIBLE)
- `b15ae233` chore(session-158d): closeout — assessment, rollback report, 158e prompt, Lessons 184/185
- `ae1deb8a` docs(session-158e): revise prompt — Railway recovery as FIRST ACTION + recommend MAINTENANCE WINDOW
- `c78af606` docs(session-158e): root cause = PostgREST schema cache stuck (PGRST002)
- `be9da284` docs(session-158d): Lesson 186 — PostgREST schema cache stuck after RENAME+ROLLBACK

## Production state at end of session

- DB: ✅ Rolled back cleanly (v1 alive 3/3, no `_dropped_*_session158`, v2 alive 3/3)
- Supabase pooler: ✅ Healthy (3/3 PASS)
- Supabase PostgREST: ❌ Schema cache stuck (PGRST002) — needs Supabase dashboard restart
- Railway service: ❌ Deploys failing healthchecks because app can't start without REST
- 158e will pick up the recovery from FIRST ACTION 1A-PRE (REST probe + Supabase restart)
