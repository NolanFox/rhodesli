# Session 158c Log

**Started**: 2026-05-09 22:49 UTC
**Ended**: 2026-05-10 ~02:00 UTC (~3h)
**Mode**: implementation
**Predecessor**: 158b (`docs/assessments/session-158b-assessment.md`)
**Successor**: 158d (`docs/prompts/session-158d-prompt.md`)
**Prompt**: `docs/prompts/session-158c-prompt.md`
**Assessment**: `docs/assessments/session-158c-assessment.md`

## Phase Checklist

- [x] Phase 158c-0: Setup + pooler health probe — DISCOVERED session-mode (port 5432) works
- [x] Phase 158c-1: Fix Codex 158b P0/P1 audit findings (3 P0 + 3 P1)
- [x] Phase 158c-2: Re-run + verify chunked-write backfill (families 6,741 → 13,158)
- [x] Phase 158c-3: R2 preflight snapshot — DEFERRED (Session 156 R2 archive canonical)
- [x] Phase 158c-4.1: Apply v2 views — current_gedcom_individuals_v2 + current_gedcom_families_v2
- [ ] Phase 158c-4.2: RENAME v1 → _dropped_*_session158 — DEFERRED to 158d (lock contention)
- [ ] Phase 158c-5: 5-min wait + sustained validation — DEFERRED to 158d
- [ ] Phase 158c-6: DROP + VACUUM FULL — DEFERRED to 158d (USER GATE required)
- [ ] Phase 158c-7: Post-cutover verification — DEFERRED to 158d
- [ ] Phase 158c-8: Track E GEDCOM upload UAT — DEFERRED to 159 (per 158 prompt §8.3)
- [x] Phase 158c-9: Closeout — assessment + CHANGELOG + ROADMAP + 158d prompt + push

## Verification Gate

- [x] All shipped phases re-checked against original prompt
- [x] Feature Reality Contract passed for shipped phases (data exists, app loads, tests pass)
- [x] Tests: 4271 pass (no regression)
- [x] Production health: HTTP 200
- [x] Git log clean (3 commits pushed to origin/main)

## Commits

1. `8a1db1f8` — fix(session-158c): Codex 158b P0/P1 audit + pooler session-mode workaround (AD-246)
2. `304c0964` — feat(session-158c): Phase 158c-2 historical backfill complete + skip R2 preflight
3. `02bf37dd` — docs(session-158c): closeout — assessment + 158d continuation prompt + order_by wiring

## Phase 158c-0 — Setup + Pooler Health Probe

| Mode | Port | Result | Notes |
|---|---|---|---|
| Transaction | 6543 | 0/3 PASS | SSL connection closed (same outage as 158/158b) |
| Session | 5432 | **5/5 PASS** | Cold 25s → warm <1s |
| Direct (db.<ref>) | 5432 | DNS FAIL | IPv6-only per Lesson 175 |

Decision: PROCEED with session-mode pooler. AD-246 written.

## Phase 158c-1 — Codex P0/P1 Fixes

All 6 findings fixed in `8a1db1f8`:

- P0-1: deterministic ORDER BY via `order_by` parameter (`gedcom_id`/`family_gedcom_id` — TEXT, 105ms vs UUID id 1.5s)
- P0-2: NULL payload_hash refusal (raise instead of narrow fallback)
- P0-3: `assert_drop_gate_safe()` all-or-nothing pre-DROP gate
- P1-1: cutover_forward requires len(v1_alive)==3 AND len(v2_alive)==3
- P1-2: cutover_rollback requires len(renamed_alive)==3 AND not v1_alive
- P1-3: `pooler_health_probe()` before DROP step

Plus port change (6543→5432), connect_timeout (30→60), retry tuning (3→6 with 10/20/30/40/50s backoff).

## Phase 158c-2 — Families Historical Backfill

| Chunk | Version | v1 rows | NEW | UPDATE | Wall-clock |
|---|---|---|---|---|---|
| 1 | v1 | 6,722 | 6,417 | 305 | 39.0s |
| 2-3 | v2-v3 | 0 | 0 | 0 | 0.4s |
| 4 | v4 | 6,722 | 0 | 6,722 | 31.0s |
| 5 | v5 | 0 | 0 | 0 | 0.2s |
| 6 | v6 | 6,722 | 0 | 6,722 | 54.6s |
| 7 | v7 | 6,722 | 0 | 6,722 | 42.2s |
| 8 | v8 | 0 | 0 | 0 | 0.2s |
| 9 | v9 | 6,436 | 0 | 6,436 | 24.7s |
| 10 | NULL | 0 | 0 | 0 | 0.1s |

Total: 33,322 v1 rows scanned, 13,158 unique payload_hashes upserted in 3.2 min wall-clock.
Zero fallback hashes (P0-2 invariant held).

Albert Fox 2-state check: `@I132123840707@` v9-v9 (hash 1d77bf67) + v1-v6 (hash fd1f05bd) ✓

Individuals: already complete from 158b (43,172 rows / 21,998 distinct gedcom_id) — dry-run chunks 1-4 confirmed NEW=0.

## Phase 158c-3 — R2 Preflight DEFERRED

Reasoning:
1. Session 156 R2 archive at `gedcom-version-snapshots/2026-05-08-session-156/` is canonical (264 MB / 42 files / per-version snapshots intact)
2. No GEDCOM imports since 156 (verified via 158-1 reality check; total versions still 9)
3. R2 preflight DRY-RUN failed at gedcom_change_log row 1,020,000 with PostgREST timeout
4. Reversibility verified on v9 in Session 156 per AD-244

## Phase 158c-4.1 — V2 Views Applied

```
current_gedcom_individuals_v2 rows: 21,998
distinct gedcom_id in v2 individuals: 21,998
[OK] individuals view passes 1:1 distinct check

current_gedcom_families_v2 rows: 6,741
distinct family_gedcom_id in v2 families: 6,741
[OK] families view passes 1:1 distinct check
```

Wrapper script: `scripts/session158c_apply_v2_views.py` (committed in `304c0964`).

## Phase 158c-4.2 — RENAME BLOCKED

```
Session 158b Phase 158-4.2 — Cutover RENAME (Mode: EXECUTE)
Before state:
  v1 alive: ['gedcom_individuals', 'gedcom_families', 'gedcom_change_log']
  _dropped_*_session158 alive: []
  v2 alive: ['gedcom_individuals_v2', 'gedcom_families_v2', 'gedcom_change_manifest']
Traceback (most recent call last):
  ...
psycopg2.errors.QueryCanceled: canceling statement due to statement timeout
```

Root cause: production app cache refresh (~120s TTL) holds AccessShareLock on
`gedcom_individuals`. RENAME requires AccessExclusiveLock — waited past default
2-min statement_timeout, transaction rolled back.

Post-error verification: all v1 tables intact, no `_dropped_*_session158` tables created.

Fix ready (1-line patch in 158d prompt §FIRST ACTION):
```python
cur.execute("SET lock_timeout = '30s'")
cur.execute("SET statement_timeout = '0'")
# then BEGIN ... RENAME ... COMMIT
```

## Session-End State Verification (via psycopg2 session-mode)

| Table | Rows | Distinct |
|---|---|---|
| gedcom_individuals_v2 | 43,172 | 21,998 |
| gedcom_families_v2 | 13,158 | 6,741 |
| gedcom_change_manifest | 9 | n/a |
| gedcom_individuals (v1) | 196,645 | 21,998 (is_current=TRUE) |
| gedcom_families (v1) | 33,324 | 6,741 (is_current=TRUE) |
| gedcom_change_log (v1) | 1,646,688 | n/a |

DB size: **2,564 MB** (target post-cutover: 600-700 MB)
Free-tier deadline: 2026-05-29 (19 days)

## Issues Encountered

1. **Pooler transaction-mode (6543) outage continues** — 3rd session in a row. Discovered session-mode (5432) workaround → AD-246. Root cause unknown (no Supabase status incident posted).

2. **PostgREST statement timeout on `count="exact"` queries** — backfill script's final POST count(*) timed out (cosmetic; counts verified via psycopg2). Same issue blocked R2 preflight DRY-RUN at gedcom_change_log row 1M.

3. **PostgREST statement timeout on ORDER BY id (UUID)** — initial Codex P0-1 fix used `id` but UUID sort over 22K rows took 1.5s direct (timed out via REST). Pivoted to ORDER BY gedcom_id (TEXT, 105ms) via benchmark. Wired through `order_by` parameter on `_process_table`.

4. **Stdout buffering through `tail -N`** — first individuals dry-run had no visible output for 1h50m because `tail -45` only flushes at EOF. Resolved by `> /tmp/file 2>&1` direct redirect for long-running scripts.

5. **RENAME lock contention** — 1-line patch ready in 158d prompt.

## Lessons Candidates

- **L185 candidate**: Supabase pooler transaction-mode (6543) can be down while session-mode (5432) is healthy. Always probe BOTH ports before declaring pooler dead.
- **L186 candidate**: PostgREST `.range()` pagination ORDER BY column choice matters — UUID `id` triggers sort-with-LIMIT that PostgREST's 8s default kills. TEXT columns with natural index access (or fast in-memory sorts) win. Benchmark before applying naive `.order("id")` fix.
- **L187 candidate**: Production app cache refresh holds AccessShareLock that blocks DDL. Always set `lock_timeout` (fail-fast) + `statement_timeout=0` (allow DDL once locked) when running RENAME/DROP against a busy app's tables.
- **L188 candidate**: Long-running Python scripts piped through `tail -N` block stdout buffering until EOF. Use `> file 2>&1` redirect for visibility into in-progress runs.

## Tests at Close

```
4271 passed, 8 skipped, 11 xfailed, 1 xpassed, 27 warnings in 50.54s
```

No regression.
