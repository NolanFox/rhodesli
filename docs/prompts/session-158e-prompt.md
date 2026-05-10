# Session 158e — PRD-063 Day 3 cutover RETRY (post-zombie-cascade)

**Mode**: implementation
**Predecessor**: Session 158d (`docs/assessments/session-158d-assessment.md`,
                                 `docs/feedback/session-158d-rollback.md`,
                                 `docs/feedback/session-158d-cutover-rename.md`)
**Critical deadline**: 2026-05-29 — Supabase free-tier 1.1 GB ceiling.

## Why this session exists

Session 158d landed RENAME successfully but the production app went 502 for
≥ 10 minutes after `pg_terminate_backend` cascaded into the live worker
connection pool. Per the prompt's hard 5xx rule, 158d rolled back. DB state
is clean (verified) but the app may still be recovering from the cascade
when 158e begins.

Lesson 185 (NEW): `pg_terminate_backend` on a hot pool crashes the app. Cutover
must NOT terminate connections while the production app is hot. Either redeploy
first to shed zombies, or take a maintenance window.

## Setup

```bash
echo "158e" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast                            # baseline — 4269 expected
git log origin/main..HEAD                 # should be empty post-158d push
git pull origin main
date -u
```

## FIRST ACTION — Verify production has recovered

```bash
curl -s -o /dev/null -w "code=%{http_code} time=%{time_total}\n" \
    https://rhodesli.nolanandrewfox.com/health
```

If `code != 200`:
1. Check Railway dashboard. If a deploy is in progress, wait.
2. If no deploy and app is in crash loop, restart via Railway dashboard.
3. Do NOT proceed with cutover until /health returns 200 and you have
   confirmed via 3 sequential 200 responses over 1 minute.

## Phase 158e-0 — Verify DB state

```bash
PYTHONPATH=. python -c "
import os, sys; sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('.env')
import psycopg2
url = os.environ['SUPABASE_URL']
project_ref = url.replace('https://','').split('.')[0]
conn = psycopg2.connect(host='aws-0-us-west-2.pooler.supabase.com', port=5432,
    user=f'postgres.{project_ref}', password=os.environ['SUPABASE_DB_PASSWORD'],
    database='postgres', connect_timeout=60)
cur = conn.cursor()
cur.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND (table_name LIKE 'gedcom_%' OR table_name LIKE '_dropped_%') ORDER BY table_name\")
print([r[0] for r in cur.fetchall()])
"
```

Must show v1 alive 3/3, no `_dropped_*_session158`. v2: 3/3.

## Phase 158e-1 — Pre-flight zombie scan (DO NOT TERMINATE YET)

```bash
PYTHONPATH=. python -c "
import os, sys; sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('.env')
import psycopg2
url = os.environ['SUPABASE_URL']; project_ref = url.replace('https://','').split('.')[0]
conn = psycopg2.connect(host='aws-0-us-west-2.pooler.supabase.com', port=5432,
    user=f'postgres.{project_ref}', password=os.environ['SUPABASE_DB_PASSWORD'],
    database='postgres', connect_timeout=60)
cur = conn.cursor()
cur.execute(\"\"\"SELECT count(*), MIN(state_change) FROM pg_stat_activity
    WHERE state='idle in transaction' AND state_change < NOW()-INTERVAL '1 hour'
    AND (query LIKE '%gedcom_individuals%' OR query LIKE '%backfill_%')\"\"\")
print('zombies:', cur.fetchone())
"
```

Document zombie count BEFORE any action.

## Phase 158e-2 — Choose path (USER GATE)

Use `AskUserQuestion`:

> "Cutover retry needs to clear zombie backends without crashing the production
> app. Two paths:
> A) MAINTENANCE WINDOW: Stop Railway service ~2 min, terminate zombies + RENAME,
>    restart Railway service. ~5 min downtime.
> B) FRESH-DEPLOY APPROACH: Trigger Railway redeploy (pushes a no-op commit),
>    wait for fresh workers, terminate zombies, then RENAME. App stays available
>    but a small window of disruption is possible.
> Options: MAINTENANCE / FRESH-DEPLOY / HOLD."

## Phase 158e-3 — Execute chosen path

### If MAINTENANCE:

1. User stops Railway service (manually via dashboard, or `railway down`)
2. Confirm /health returns connection refused / 503
3. Run zombie cleanup (Session 158d code in `docs/feedback/session-158d-cutover-rename.md`)
4. Run `python scripts/session158b_cutover_rename.py --execute` (max 3 retries
   on lock_timeout — if zombies are clear, RENAME should land in <1s)
5. User restarts Railway service
6. Verify /health = 200 over 1 minute

### If FRESH-DEPLOY:

1. `git commit --allow-empty -m "chore: trigger redeploy for 158e cutover" && git push`
2. Wait for Railway deploy completion (poll /health for 200 with new release)
3. Run zombie cleanup (their references should now be gone from the new pool)
4. Run RENAME with retries
5. Verify /health stays 200 throughout

## Phase 158e-4 — Wait period (5 min, monitor /health)

```bash
# Poll every 30s for 5 min — must stay 200 throughout
```

If any 5xx: ROLLBACK via `--rollback`, end session, escalate.

## Phase 158e-5 — DROP + VACUUM FULL (USER GATE, IRREVERSIBLE)

Use `AskUserQuestion` (same wording as 158d-5):

> "All gates passed (carry / change-history / backfill / views / rename / wait).
> Next step DROPs the 3 _dropped_*_session158 tables and runs VACUUM FULL.
> After this, recovery is via R2 archive (~1h) or local pg_dump (~30min).
> Options: PROCEED / HOLD / ROLLBACK"

If PROCEED:

```bash
PYTHONPATH=. python scripts/session158b_drop_and_vacuum.py --dry-run
PYTHONPATH=. python scripts/session158b_drop_and_vacuum.py --execute
```

Expected: ~2,564 MB → ~600-700 MB.

## Phase 158e-6 — Post-cutover verification

Browser verify 6 canonical pages READ-ONLY. Albert Fox 2-state query
(`@I132123840707@` v9-v9 hash=1d77bf67, v1-v6 hash=fd1f05bd).

## Phase 158e-7 — Closeout

/session-review, Codex final-pass audit on 158d+158e diff, CHANGELOG, ROADMAP,
BACKLOG, SESSION_HISTORY (entries for 158d and 158e), git push.

## Critical state inherited from 158d

- DB rolled back: v1 alive 3/3, no `_dropped_*_session158`, v2 3/3
- Patches in main: cutover_rename SET LOCAL lock/statement_timeout, drop_and_vacuum
  SET LOCAL + re-raise on VACUUM error, apply_v2_views commit-after-sanity
- 16 zombies from 158b were terminated in 158d at 02:23Z; if production has
  redeployed since then, the new worker pool should be clean
- Production app may need manual restart if it didn't self-heal post-rollback

## Lesson 185 (NEW from 158d)

**Never `pg_terminate_backend` on a pool aliased by a hot production app.**
The app's connection-pool entries become invalid; workers crash on next query;
restart cascade hits Railway's max-restart limit; site goes 502.

Mitigation:
1. Redeploy first to shed worker generations (their pool refs die naturally),
   THEN terminate any remaining zombies.
2. OR: maintenance window — service offline → terminate → DDL → service online.

## Non-negotiable rules (carried)

1. READ-ONLY on production browsers
2. Codex: `codex exec "<prompt>" </dev/null`. Never `--full-auto`.
3. Commit atomically per phase. /clear at 300+ transcript lines.
4. AD entries for every ML/data decision.
5. R2 reversibility re-test BEFORE any irreversible action.
6. No DROP unless every gating phase passes.
7. **NEW**: No `pg_terminate_backend` on a hot production pool.
