# Session 158d — PRD-063 Day 3 cutover (RENAME retry → DROP → VACUUM)

**Mode**: implementation
**Predecessor**: Session 158c (`docs/feedback/session-158c-carry-verify.md`, `docs/feedback/session-158c-backfill-report.md`, commits `8a1db1f8`, `304c0964`)
**Critical deadline**: 2026-05-29 — Supabase free-tier 1.1 GB ceiling. Re-confirm via `date -u`.

## Why this session exists

Session 158c made major progress:
- **AD-246**: discovered pooler **session-mode (port 5432) works** while transaction-mode (6543) is dead
- **Codex 158b P0/P1 fixes** all committed (`8a1db1f8`)
- **Phase 158c-2 backfill**: families went 6,741 → 13,158 rows (33,322 v1 rows scanned, 13,158 unique payload_hashes upserted in ~3.2 min). Individuals already complete from 158b at 43,172 rows.
- **Phase 158c-3 R2 preflight**: deferred — Session 156 R2 archive is canonical. R2 preflight DRY-RUN failed on `gedcom_change_log` REST timeout. Documented decision.
- **Phase 158c-4.1 v2 views applied**: `current_gedcom_individuals_v2` (21,998 rows) and `current_gedcom_families_v2` (6,741 rows) created via psycopg2 session-mode. Sanity check passed (view rows == DISTINCT count).

158c attempted **Phase 158c-4.2 RENAME** but hit `psycopg2.errors.QueryCanceled: canceling statement due to statement timeout` on the first `ALTER TABLE gedcom_individuals RENAME TO _dropped_gedcom_individuals_session158`. Transaction rolled back cleanly (all v1 tables intact). The default `statement_timeout=2min` was too tight because production app cache refresh (~every 120s) holds AccessShareLock, blocking the AccessExclusiveLock RENAME needs.

**158c session ended at the 709-transcript-line clear gate** — the script needs a 1-line patch and a retry. That's 158d's job.

## Setup

```bash
echo "158d" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
bash scripts/harness-check.sh
make test-fast                            # baseline — 4271 expected
git log origin/main..HEAD                 # 2 commits unpushed from 158c (push or carry)
git pull origin main
git status --short
date -u                                   # confirm date for deadline math
```

## FIRST ACTION — Apply the cutover_rename.py patch (Codex 158c P1 + lock fix)

**Codex 158c audit** found 2 things to fix in 158d FIRST ACTION (`docs/session_context/session-158c-codex-audit.md`):
1. The lock_timeout/statement_timeout fix should use `SET LOCAL` *inside* BEGIN, not session-level `SET` before BEGIN. Cleaner for connection pooling, auto-reverts on COMMIT/ROLLBACK.
2. `scripts/session158c_apply_v2_views.py` has a P1: `conn.commit()` runs BEFORE the sanity checks. If a check fails, replaced views are already committed. Move commit AFTER sanity checks (or rollback on failure).
3. Pre-existing P2 in `session158b_drop_and_vacuum.py::vacuum_full`: per-table errors swallowed silently. Re-raise on first failure OR exit non-zero if any timing has status ERROR.

The exact patch needed (Edit tool — both `cutover_forward` and `cutover_rollback` need the same SET LOCAL treatment):

```python
# In scripts/session158b_cutover_rename.py, replace cutover_forward() body:
def cutover_forward(conn) -> None:
    cur = conn.cursor()
    # 158d (Codex 158c P1 form): production app holds AccessShareLock on
    # gedcom_individuals via TTL cache refresh queries (every ~120s). Default
    # statement_timeout (2min) was too tight for RENAME's required
    # AccessExclusiveLock to acquire (158c observed timeout). Two-step fix:
    #   1. lock_timeout=30s — fail FAST if lock is held; retry the script.
    #   2. statement_timeout=0 — once we have the lock, RENAME is metadata-only
    #      and instantaneous; allow unlimited time inside the transaction.
    # SET LOCAL scopes the override to this transaction only (auto-revert on
    # COMMIT/ROLLBACK — cleaner for connection pooling).
    cur.execute("BEGIN")
    cur.execute("SET LOCAL lock_timeout = '30s'")
    cur.execute("SET LOCAL statement_timeout = '0'")
    cur.execute("DROP VIEW IF EXISTS current_gedcom_individuals")
    for src, dst in RENAME_PAIRS:
        cur.execute(f"ALTER TABLE {src} RENAME TO {dst}")
    cur.execute("COMMIT")
    cur.close()
```

Same `SET LOCAL` block (after BEGIN) needed in `cutover_rollback`.

Same treatment also needed in `scripts/session158b_drop_and_vacuum.py::drop_renamed_tables()` AFTER BEGIN.

`scripts/session158c_apply_v2_views.py` P1 fix: restructure to commit AFTER sanity checks pass (or use `conn.autocommit = True` AFTER the migration block).

Commit: `fix(session-158d): cutover lock_timeout + Codex 158c P1/P2 fixes`

## Phase 158d-2 — RENAME retry

```bash
PYTHONPATH=. python scripts/session158b_cutover_rename.py --execute
```

**If `lock_timeout` fires**: nothing happened, transaction never started. Wait ~30s and retry. Up to 3 retries, then escalate.

**Expected SUCCESS output**:
```
Before state:
  v1 alive: ['gedcom_individuals', 'gedcom_families', 'gedcom_change_log']
  ...
FORWARD cutover complete.
After state:
  v1 alive: []
  _dropped_*_session158 alive: ['_dropped_gedcom_change_log_session158', ...]
  v2 alive: [...]
```

Commit: `feat(session-158d): cutover RENAME v1 → _dropped_session158 (REVERSIBLE)`

## Phase 158d-3 — Smoke + browser verify

```bash
make test-fast                                                          # 4271+ pass
python scripts/production_smoke_test.py --url https://rhodesli.nolanandrewfox.com
```

Chrome MCP browser verify the canonical 6 + GEDCOM-aware pages (READ-ONLY per `.claude/rules/browser-read-only.md`).

If ANY 5xx or "GEDCOM data unavailable" string: ROLLBACK via `--rollback` and end session.

## Phase 158d-4 — Wait period (5 min)

```bash
sleep 300
# Re-run smoke tests; pull Sentry/Railway logs
```

If issues: rollback (RENAME back). If clean: proceed.

## Phase 158d-5 — DROP + VACUUM FULL (IRREVERSIBLE)

### 5.0 — User authorization gate (MANDATORY)

Use `AskUserQuestion`:
> "All 6 pre-DROP gates passed (carry / change-history / backfill / views / rename / wait). The next step DROPs `_dropped_gedcom_individuals_session158`, `_dropped_gedcom_families_session158`, `_dropped_gedcom_change_log_session158` and runs VACUUM FULL on Supabase. After this point, recovery is via R2 archive (~1h) or local pg_dump (~30min). Options: PROCEED / HOLD / ROLLBACK"

If PROCEED:
```bash
PYTHONPATH=. python scripts/session158b_drop_and_vacuum.py --dry-run
PYTHONPATH=. python scripts/session158b_drop_and_vacuum.py --execute
```

Expected: DB size drops from ~2,564 MB to ~600-700 MB.

Commit: `feat(session-158d): DROP v1 + VACUUM FULL (IRREVERSIBLE)`

## Phase 158d-6 — Post-cutover verification

Browser verify the canonical 6 pages a final time. Verify Albert Fox change-history query still returns 2 rows (`@I132123840707@` v1-v6 + v9-v9).

Commit: `chore(session-158d): post-cutover verification + query timing`

## Phase 158d-7 — Closeout

Run /session-review. Codex final-pass audit. CHANGELOG, ROADMAP, BACKLOG, SESSION_HISTORY. git push origin main.

## Critical state inherited from 158c

- **Pooler**: transaction-mode (6543) DEAD. Use session-mode (port 5432). `connect_timeout=60`. AD-246.
- **v2 row counts** (verified via psycopg2 at 158c close):
  - gedcom_individuals_v2: 43,172 / 21,998 distinct gedcom_id
  - gedcom_families_v2: 13,158 / 6,741 distinct family_gedcom_id
  - gedcom_change_manifest: 9
- **Albert Fox** test: 2 states present (v9-v9 hash=1d77bf67, v1-v6 hash=fd1f05bd) ✓
- **DB size**: 2,564 MB (target: 600-700 MB after DROP+VACUUM)
- **Views applied**: current_gedcom_individuals_v2, current_gedcom_families_v2 — both pass 1:1 distinct sanity check
- **App code**: `app/relationship_routes.py` (lines 685, 691, 987, 999) and `app/gedcom_dual_read.py` (lines 106, 117, 183) all have v2-view-first fallback chain. RENAME triggers PGRST205 cascade → v2 view succeeds.
- **R2 archive**: Session 156 R2 archive at `gedcom-version-snapshots/2026-05-08-session-156/` is canonical rollback source (264 MB / 42 files / per-version snapshots intact).

## Codex P0/P1 fixes (committed in 158c, no rework needed)

All from `8a1db1f8`:
- P0-1: chunked-write `.order(gedcom_id|family_gedcom_id)` — fast PostgREST exec
- P0-2: NULL payload_hash refusal — 0 fallbacks observed in 158c execute
- P0-3: drop_and_vacuum all-or-nothing gate
- P1-1, P1-2: cutover gates require all 3 v1 + all 3 v2 alive (rollback requires all 3 renamed)
- P1-3: drop_and_vacuum pooler health probe before DROP

## Non-negotiable rules (carried)

1. READ-ONLY on production browsers
2. Codex: `codex exec "<prompt>" </dev/null`. Never `--full-auto`.
3. Commit atomically per phase. /clear at 300+ transcript lines.
4. AD entries for every ML/data decision
5. R2 reversibility re-test BEFORE any irreversible action — Session 156 archive
6. No DROP unless every gating phase passes (carry / backfill / views / rename / wait)
