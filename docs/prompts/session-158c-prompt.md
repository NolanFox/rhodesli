# Session 158c — PRD-063 Day 3: cutover (RENAME → DROP → VACUUM)

**Mode**: implementation
**Predecessor**: Session 158b (`docs/assessments/session-158b-assessment.md`, commits `5799700a..` through `<closing>`)
**Critical deadline**: 2026-05-29 — Supabase free-tier 1.1 GB ceiling. Re-confirm via `date -u`.

## Why this session exists

Session 158b shipped Phase 158b-2 (historical backfill) but DEFERRED Phases 158b-3 through 158b-9 because Supabase pooler psycopg2 was completely unavailable on 2026-05-09. The cutover phases require psycopg2 for DDL (RENAME, DROP, VACUUM FULL) — REST API can't execute these.

158c's job is to land the actual cutover when the pooler recovers.

## What 158b shipped that 158c builds on

- **Phase 158b-0** ✅: carry verification re-passed, A.5 hardening verified
- **Phase 158b-0B** ✅: pooler probe (FAILED 0/3 — diagnostic data captured)
- **Phase 158b-2** ✅: chunked-write historical backfill via REST. v2 row count grew from 21,998 to ~43-65K (TBD on completion). Albert Fox 2-state history verified.
- **Phase 158b-4.1 code only** ✅: bulk-loader rewired to prefer `current_gedcom_individuals_v2` view. View itself NOT yet created (psycopg2 unavailable).
- All cutover scripts written (RENAME / DROP-VACUUM / R2 preflight) — ready to run.

## What 158b deferred (this session's queue)

| Phase | Status | Script |
|---|---|---|
| 158b-3 R2 preflight snapshot | DEFERRED — REST works but didn't have time | `scripts/session158b_r2_preflight_snapshot.py` |
| 158b-4.1 view migration apply | DEFERRED — pooler dead | `scripts/migrations/session158b_current_v2_views.sql` |
| 158b-4.2 RENAME v1 → _dropped_*_session158 | DEFERRED — pooler dead | `scripts/session158b_cutover_rename.py` |
| 158b-5 wait + sustained validation | DEFERRED | n/a (sleep + re-verify) |
| 158b-6 DROP + VACUUM FULL | DEFERRED — pooler dead | `scripts/session158b_drop_and_vacuum.py` |
| 158b-7 post-cutover query timing | DEFERRED — psycopg2 needed | `scripts/session157b_query_timing.py` |
| 158b-7 Chrome MCP browser verify | DEFERRED | n/a (manual via Chrome MCP) |
| 158b-8 Track E GEDCOM upload UAT | DEFERRED — likely roll to 159 | TBD |
| 158b-9 final verification | DEFERRED | n/a |

## Setup

```bash
echo "158c" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
bash scripts/harness-check.sh
make test-fast                            # baseline — 4271 expected
git log origin/main..HEAD                 # MUST be empty
git pull origin main
git status --short
date -u                                   # confirm date for deadline math
```

## FIRST ACTION — Re-run pooler health probe + carry verify

```bash
PYTHONPATH=. python scripts/session158_phase0_verify.py
# Save output to docs/feedback/session-158c-carry-verify.md
```

```bash
# Re-probe pooler — if 0-2/3 PASS, defer cutover AGAIN to 158d
source venv/bin/activate
PYTHONPATH=. python -c "
import os, time, psycopg2
from dotenv import load_dotenv; load_dotenv()
url = os.environ['SUPABASE_URL']
project_ref = url.replace('https://', '').split('.')[0]
for trial in range(3):
    t0 = time.time()
    try:
        conn = psycopg2.connect(
            host='aws-0-us-west-2.pooler.supabase.com', port=6543,
            user=f'postgres.{project_ref}',
            password=os.environ['SUPABASE_DB_PASSWORD'],
            database='postgres', connect_timeout=15,
        )
        cur = conn.cursor()
        cur.execute('SELECT id FROM gedcom_versions LIMIT 1')
        cur.fetchone()
        cur.close()
        conn.close()
        print(f'Trial {trial+1}: PASS in {(time.time()-t0)*1000:.0f}ms')
    except Exception as e:
        print(f'Trial {trial+1}: FAIL — {e.__class__.__name__}: {e}')
"
```

**If 3/3 PASS**: pooler healthy. Proceed with all phases below.
**If 0-2/3 PASS**: ESCALATE — defer to 158d AND consider:
  - Opening Supabase support ticket
  - Trying direct (non-pooler) connection via `db.fvynibivlphxwfowzkjl.supabase.co:5432` (may be IPv6-only — see Lesson 175)
  - Manually applying SQL via Supabase Studio web UI

## Phase 158c-2 — Verify backfill state (REST — works regardless of pooler)

```bash
source venv/bin/activate && PYTHONPATH=. python -u -c "
from dotenv import load_dotenv; load_dotenv()
from app.supabase_data import get_supabase_client
sb = get_supabase_client()
i = sb.table('gedcom_individuals_v2').select('id', count='exact').limit(1).execute()
f = sb.table('gedcom_families_v2').select('id', count='exact').limit(1).execute()
print(f'gedcom_individuals_v2 count: {i.count:,}')
print(f'gedcom_families_v2 count: {f.count:,}')

# Albert Fox 2-state check
from app.gedcom_dual_read import get_individual_history
hist = get_individual_history('@I132123840707@')
print(f'Albert Fox ({len(hist)} states):')
for h in hist:
    print(f\"  v{h['first_seen_version']}-v{h['last_seen_version']}: hash={h['payload_hash'][:8]}\")
"
```

Expected (from 158b plan):
- individuals_v2: ~43,172 to 65,170 rows (TBD final)
- families_v2: ~13K rows
- Albert Fox: exactly 2 states

## Phase 158c-3 — R2 preflight snapshot

```bash
PYTHONPATH=. python scripts/session158b_r2_preflight_snapshot.py --dry-run
PYTHONPATH=. python scripts/session158b_r2_preflight_snapshot.py --execute
```

Expected: ~3-5 GB of compressed JSONL across 4 tables uploaded to R2 prefix `gedcom-pre-drop-snapshots/<UTC-date>-session-158c/`. Verify all 4 ETags match local md5.

Commit: `chore(session-158c): R2 preflight snapshot (Phase 158b-3 carry-over)`.

## Phase 158c-4 — View migration + 4.2 RENAME

### 4.1 — Apply v2 views

```bash
PYTHONPATH=. python -c "
import os
from dotenv import load_dotenv; load_dotenv()
import psycopg2
url = os.environ['SUPABASE_URL']
project_ref = url.replace('https://', '').split('.')[0]
sql = open('scripts/migrations/session158b_current_v2_views.sql').read()
conn = psycopg2.connect(
    host='aws-0-us-west-2.pooler.supabase.com', port=6543,
    user=f'postgres.{project_ref}',
    password=os.environ['SUPABASE_DB_PASSWORD'],
    database='postgres', connect_timeout=30,
)
cur = conn.cursor()
cur.execute(sql)
conn.commit()
cur.execute('SELECT COUNT(*) FROM current_gedcom_individuals_v2')
print(f'current_gedcom_individuals_v2 row count: {cur.fetchone()[0]:,}')
cur.execute('SELECT COUNT(*) FROM current_gedcom_families_v2')
print(f'current_gedcom_families_v2 row count: {cur.fetchone()[0]:,}')
cur.execute('SELECT COUNT(DISTINCT gedcom_id) FROM gedcom_individuals_v2')
print(f'distinct gedcom_id in v2 individuals: {cur.fetchone()[0]:,}')
cur.close()
conn.close()
print('Views created.')
"
```

**Sanity check**: `count(current_view)` MUST equal `count(distinct gedcom_id)` in v2.

### 4.2 — RENAME (REVERSIBLE)

```bash
PYTHONPATH=. python scripts/session158b_cutover_rename.py --dry-run
PYTHONPATH=. python scripts/session158b_cutover_rename.py --execute
```

### 4.3 — Smoke + browser verify

```bash
make test-fast                                                          # 4271+ pass
python scripts/production_smoke_test.py --url https://rhodesli.nolanandrewfox.com
```

Chrome MCP browser verify the canonical 6 + GEDCOM-aware pages (READ-ONLY per `.claude/rules/browser-read-only.md`).

If ANY 5xx or "GEDCOM data unavailable" string: ROLLBACK via `--rollback` and end session at 158c-4.

Commit: `feat(session-158c): cutover RENAME v1 → _dropped_session158 (Phase 158b-4.2, REVERSIBLE)`.

## Phase 158c-5 — Wait period (5 min)

```bash
sleep 300
# Re-run smoke tests; pull Sentry/Railway logs
```

If issues: rollback (RENAME back). If clean: proceed.

## Phase 158c-6 — DROP + VACUUM FULL (IRREVERSIBLE)

### 6.0 — User authorization gate (MANDATORY)

Use `AskUserQuestion`:
> "All 5 pre-DROP gates passed (carry / change-history / backfill / backups / rename+wait). The next step DROPs `_dropped_gedcom_individuals_session158`, `_dropped_gedcom_families_session158`, `_dropped_gedcom_change_log_session158` and runs VACUUM FULL on Supabase. After this point, recovery is via R2 archive (~1h) or local pg_dump (~30min). Options: PROCEED / HOLD / ROLLBACK"

If PROCEED:
```bash
PYTHONPATH=. python scripts/session158b_drop_and_vacuum.py --dry-run
PYTHONPATH=. python scripts/session158b_drop_and_vacuum.py --execute
```

Expected: DB size drops from ~2.22 GB to ~600-700 MB.

Commit: `feat(session-158c): DROP v1 + VACUUM FULL (Phase 158b-6, IRREVERSIBLE)`.

## Phase 158c-7 — Post-cutover verification

```bash
PYTHONPATH=. python scripts/session157b_query_timing.py
# Save report at docs/feedback/session-158c-query-timing-postcutover.md
```

Browser verify the canonical 6 pages a final time. Verify Albert Fox change-history query still returns 2 rows.

Commit: `chore(session-158c): post-cutover query timing + verification (Phase 158b-7)`.

## Phase 158c-8 — Track E (DEFER to 159 if non-trivial)

The v2-aware GEDCOM importer design needs new code on the cutover day. The existing v1 importer wrote to v1 tables which are now DROPPED. Choose path A/B/C from 158 prompt §8.3:
- A: Re-create v1 tables temporarily (defeats cutover purpose)
- B: Build v2-aware importer in this session (medium risk)
- C: Skip Track E; defer to 159 (recommended IF design is non-trivial)

Surface design choices to user via `AskUserQuestion` before implementing.

## Phase 158c-9 — Final verification + closeout

Run /session-review skill. Codex final-pass audit MANDATORY. 12-step harness.

## Non-negotiable rules (carried from 158/158b)

1. READ-ONLY on production browsers
2. Codex: `codex exec "<prompt>" </dev/null`. Never `--full-auto`.
3. Commit atomically per phase. /clear at 300+ transcript lines.
4. AD entries for every ML/data decision
5. R2 reversibility re-test BEFORE any irreversible action
6. No DROP unless every gating phase passes
