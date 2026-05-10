**Auditor**: Codex CLI v0.130.0 (gpt-5.5, xhigh)
**Agent type**: Independent (fresh context)
**Scope**: Session 158c commits `8a1db1f8`, `304c0964`, `02bf37dd`, `eae78c52` — 4 scripts in scope (3 modified + 1 new)
**Date**: 2026-05-10
**Wall-clock**: ~5 min, 57,943 tokens
**Invocation**: `codex exec "<focused-scope prompt>" </dev/null` per `.claude/rules/ai-tool-audit.md`

---

## 158b P0/P1 Fix Status — ALL CONFIRMED CORRECT

| Finding | Location | Status |
|---|---|---|
| P0-1 deterministic ORDER BY | `session158b_historical_backfill_chunked.py:132`, wired at lines 333/343 (`gedcom_id` / `family_gedcom_id`) | **CORRECT** |
| P0-2 NULL payload_hash refusal | `session158b_historical_backfill_chunked.py:161` | **CORRECT** |
| P0-3 DROP all-or-nothing gate | `session158b_drop_and_vacuum.py:128` (called at line 259) | **CORRECT** |
| P1-1 cutover_forward gate | `session158b_cutover_rename.py:160` | **CORRECT** |
| P1-2 cutover_rollback gate | `session158b_cutover_rename.py:144` | **CORRECT** |
| P1-3 DROP pooler probe | `session158b_drop_and_vacuum.py:95` (invoked at line 252) | **CORRECT** |

---

## New Findings (introduced by 158c)

### P1: View script commits before sanity check

`scripts/session158c_apply_v2_views.py:82` calls `conn.commit()` immediately after
applying the `CREATE OR REPLACE VIEW` SQL, BEFORE the 1:1 distinct-count sanity
checks at lines 93 and 106. If either check fails, the script `sys.exit()`s but the
replaced views and `GRANT`s are already committed.

**Severity**: P1 (not P0) because:
- `CREATE OR REPLACE VIEW` is idempotent (subsequent runs reapply same SQL)
- The SQL itself is well-formed (manually reviewed)
- The sanity check is for OUR confidence in the tiebreaker correctness, not a structural gate
- 158c verified the check passed (21,998 / 6,741 1:1 — view definitions are correct)

**Fix (defer to 158d)**: Restructure `_apply_views()` to commit AFTER both sanity
checks pass. Or use `conn.autocommit = True` AFTER the migration block so the
sanity-check failure doesn't carry transactional weight.

---

## Pre-existing Findings (still relevant for 158d)

### P2: VACUUM FULL silent partial success

`scripts/session158b_drop_and_vacuum.py:220` catches per-table `VACUUM FULL` errors
into the `timings` dict and continues to the success-flow report. If a timeout or
lock failure occurs on one of the 7 tables in `VACUUM_TABLES`, the script can exit
with code 0 even though space was not fully reclaimed.

**Severity**: P2 — not blocking the cutover, but undermines the size-delta report's
meaning. Not introduced by 158c.

**Fix (defer to 158d)**: Re-raise on the first `VACUUM FULL` failure, OR add a
non-zero exit if any per-table status is `ERROR` AND raise into the report header.

---

## Architecture Validation

### `session158c_apply_v2_views.py` is idempotent in SQL terms

Confirmed:
- Migration uses `CREATE OR REPLACE VIEW` (re-run-safe)
- `GRANT SELECT ON ... TO anon, authenticated, service_role` is repeatable (no error on duplicate grant)
- Distinct-count sanity check is the right cardinality check for "one current row per GEDCOM key"
- Error handling is **not fully safe** due to the pre-check commit (see P1 above)

### 158d FIRST ACTION (lock_timeout/statement_timeout) — directionally correct

`docs/prompts/session-158d-prompt.md:34` proposes:
```python
cur.execute("SET lock_timeout = '30s'")
cur.execute("SET statement_timeout = '0'")
cur.execute("BEGIN")
```

**Codex's preferred form**: use `SET LOCAL` *inside* the transaction:
```python
cur.execute("BEGIN")
cur.execute("SET LOCAL lock_timeout = '30s'")
cur.execute("SET LOCAL statement_timeout = '0'")
# DDL here
cur.execute("COMMIT")
```

Both forms have the correct semantics. `SET LOCAL` is preferred because:
1. The setting is automatically reverted on COMMIT/ROLLBACK (cleaner for connection pooling)
2. It explicitly documents the scope (transaction-only override, not session)
3. Matches the typical Postgres DDL pattern

**Action for 158d**: update FIRST ACTION patch text to use `SET LOCAL` inside BEGIN.

---

## What we asked Codex to do

```
Audit Session 158c changes against the 158b Codex findings.
Files in scope (3 files only — skip everything else):
1. scripts/session158b_historical_backfill_chunked.py
2. scripts/session158b_cutover_rename.py
3. scripts/session158b_drop_and_vacuum.py
4. scripts/session158c_apply_v2_views.py
[Codex 158b P0/P1 list as context]
Audit scope: P0/P1/P2 only. P3 ok to skip. NO unrelated-code exploration.
```

## Codex performance vs 158b run

| | 158b Run 1 | 158b Run 2 | **158c (this run)** |
|---|---|---|---|
| Scope | 7 files, P0-P3, "thorough" | 3 files, P0/P1 only, focused | 4 files, P0/P1/P2, focused |
| Wall-clock | 28 min (terminated) | ~5 min | **~5 min** |
| Findings | 0 (exploration loop) | 6 P0/P1 | 1 new P1, 1 pre-existing P2, 6 confirmations |
| Tokens | unknown | 27K | **57.9K** |

158c run used more tokens than 158b Run 2 because the audit prompt included the
full 158b findings list as context (~2K tokens) and Codex re-verified each fix at
specific file:line locations.

**Lesson reinforced**: tight scope (≤4 files, P0/P1, "skip unrelated exploration")
keeps Codex audit reliable + sub-10-min.

---

## Value Assessment: STRONG

- Caught a P1 we missed (views commit-before-check)
- Confirmed all 6 158b P0/P1 fixes at exact file:line — high signal
- Suggested better `SET LOCAL` form for 158d FIRST ACTION (cleaner pattern)
- Surfaced pre-existing P2 in vacuum that was hiding under "follow-on work"

**Would we have found these ourselves?** Maybe. The views commit-before-check is a
classic "obvious in hindsight" pattern. The `SET LOCAL` recommendation is craft
detail. The vacuum P2 was implicit in the script structure — Codex made it explicit.

## Disposition

- **P1 (views commit-before-check)**: defer to 158d, fix as 5-min patch
- **P2 (vacuum silent partial)**: defer to 158d, fix as 5-min patch  
- **158d FIRST ACTION patch**: update prompt to use `SET LOCAL` form

All updates land in 158d, NOT 158c — current session is past clear gate.

## Codex CLI invocation reference

Working invocation (no hangs, completes in ~5 min):
```bash
codex exec "<focused-prompt>" </dev/null 2>&1 | tee /tmp/codex_158c_audit.log | tail -100
```

NOT used: `--full-auto` (stdin hang per Sessions 152, 153, 153b, 154, 155).
