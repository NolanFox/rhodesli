# Session 158b Log

**Date**: 2026-05-09
**Mode**: implementation
**Prompt**: `docs/prompts/session-158b-prompt.md`
**Predecessor**: Session 158
**Successor**: Session 158c (`docs/prompts/session-158c-prompt.md`)
**Result**: PARTIAL — Phase 158b-2 backfill EXECUTE in progress at close; phases 158b-3 → 158b-9 DEFERRED.

## Phase Checklist

- [x] **Phase 158b-0**: Carry verification + A.5 hardening verify
- [x] **Phase 158b-0B**: Pooler health probe (3 trials)
- [/] **Phase 158b-2**: Redesigned chunked-write historical backfill — script written, EXECUTE PARTIAL. Chunks 1-5/10 individuals upserted successfully. Chunk 6 read+aggregate+merge succeeded, then DIED on upsert (httpx.ReadTimeout exhausted 3 retries on a single batch). v2 individuals state: ~110K rows including chunk-6 partial writes. Chunks 7-10 + all families NOT processed. Resume via 158c. Recommended retry tuning: bump `_upsert_v2` retry count from 3 → 6, sleep 3s → 10s with backoff. Idempotency preserved (ON CONFLICT DO UPDATE), so re-running from chunk 1 is safe.
- [x] **Phase 158b-4.1 (code only)**: Bulk-loader rewire to prefer v2 view
- [ ] **Phase 158b-3**: R2 preflight snapshot — DEFERRED (script ready)
- [ ] **Phase 158b-4.1 (DDL apply)**: View migration — DEFERRED (pooler dead)
- [ ] **Phase 158b-4.2**: RENAME — DEFERRED (pooler dead)
- [ ] **Phase 158b-5**: Wait + sustained validation — DEFERRED
- [ ] **Phase 158b-6**: DROP + VACUUM FULL — DEFERRED (pooler dead)
- [ ] **Phase 158b-7**: Post-cutover query timing + Chrome MCP browser verify — DEFERRED
- [ ] **Phase 158b-8**: Track E GEDCOM upload UAT — DEFERRED (likely 159)
- [ ] **Phase 158b-9**: Final verification — DEFERRED

## Commits

1. `5799700a` — `feat(session-158b): Phase 158b-0 setup + 158b-2 chunked-write backfill + cutover scripts`
2. `f2a857b8` — `feat(session-158b): bulk-loader rewire to prefer current_gedcom_individuals_v2 (Phase 158-4.1)`
3. `182998d3` — `docs(session-158b): progress checkpoint — Phase 158b-2 EXECUTE in progress, pooler degraded`
4. `7d438807` — `docs(session-158b): add session-158c continuation prompt for cutover phases`
5. `1285eb87` — `docs(session-158b): closeout — assessment + CHANGELOG v0.99.76 + ROADMAP + BACKLOG`

## Key artifacts

- Carry verification: `docs/feedback/session-158b-carry-verify.md`
- Progress checkpoint: `docs/feedback/session-158b-progress-checkpoint.md`
- Assessment: `docs/assessments/session-158b-assessment.md`
- 158c continuation: `docs/prompts/session-158c-prompt.md`
- Backfill script: `scripts/session158b_historical_backfill_chunked.py`
- Cutover scripts: `scripts/session158b_{cutover_rename,drop_and_vacuum,r2_preflight_snapshot}.py`
- View migration SQL: `scripts/migrations/session158b_current_v2_views.sql`
- Backfill EXECUTE log (live): `/tmp/sess158b_execute.log`

## Verification Gate

- [x] Original prompt re-read at session-prep
- [x] Phase 158b-0 carry verification PASS
- [x] Phase 158b-0B pooler probe DIAGNOSTIC: 0/3 PASS (FAIL → triggers REST-only path)
- [x] Phase 158b-2 chunked-write redesign delivered (script + commit `5799700a`)
- [/] Phase 158b-2 EXECUTE incomplete at session close — bg job continues; resume via 158c
- [x] Phase 158b-4.1 code rewire shipped + tested (4271 pass)
- [x] Closeout artifacts (assessment + CHANGELOG + ROADMAP + BACKLOG + 158c prompt) shipped + pushed
- [x] `git log origin/main..HEAD` empty (all 5 commits pushed)
- [x] `git status --short` clean
- [x] Memory backup complete (56 → 56)

## Notable observations / lessons-candidate

- **Pooler outage extending across sessions** (Lesson 184 candidate): 158 + 158b both saw 0/3 PASS on pooler probe. SSL connection closed unexpectedly is the consistent failure. >24h sustained suggests ticket-worthy degradation, not transient.
- **Per-chunk wall-clock variance is huge** (220s — 4230s on identical workload): pooler/REST throughput unstable. Script's 3-retry loop handles failures but inflates time.
- **REST upsert IS slower for all-UPDATE chunks than for mostly-NEW chunks** in observation (chunk 2 = 189s, chunk 3 = 1875s, chunk 5 = 4230s). Not investigated — could be PostgREST request queueing under load.
- **Bulk-loader rewire to v2 view is harmless pre-cutover** because the view doesn't exist yet → falls back to `current_gedcom_individuals` (v1 view, still alive). Safe to merge before view DDL is applied.
