# Session 158e — PRD-063 Day 3 cutover RETRY (post-zombie-cascade)

**Mode**: implementation
**Predecessor**: Session 158d (`docs/assessments/session-158d-assessment.md`,
                                 `docs/feedback/session-158d-rollback.md`,
                                 `docs/feedback/session-158d-cutover-rename.md`)
**Critical deadline**: 2026-05-29 — Supabase free-tier 1.1 GB ceiling.

## Why this session exists

Session 158d landed RENAME successfully but the production app went 502 for
≥ 50+ minutes after `pg_terminate_backend` cascaded into the live worker
connection pool. Per the prompt's hard 5xx rule, 158d rolled back. DB state
is clean (verified) but **the production app did NOT self-heal** by 158d
session close — Railway dashboard showed the 158c deploy as ACTIVE/successful
yet `/health` continued returning 502 with `x-railway-fallback: true`.
Two subsequent automatic redeploys (cutover RENAME commit `b2a5583e` and
closeout commit `b15ae233`) BOTH failed network healthchecks. The Railway
"Online" badge in the UI reflects deploy build state, NOT edge reachability.

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

## FIRST ACTION — RECOVER PRODUCTION (do NOT trust the Railway "ACTIVE" badge)

The 158d session ended with the app in a degraded state: Railway shows 158c
deploy as "ACTIVE" but `/health` returns 502. The Railway dashboard's "Online"
badge means the deploy artifact succeeded; it does NOT mean the public URL
serves traffic. Trust ONLY the HTTP probe.

### ROOT CAUSE (diagnosed via `railway logs` at 03:39Z, post-158d):

```
WARNING:core.registry:IdentityRegistry.load_from_postgres failed:
{'message': 'Could not query the database for the schema cache. Retrying.',
 'code': 'PGRST002', 'hint': None, 'details': None}
[data] Registry load failed (attempt 1/3): Supabase identity load unavailable
[data] Retrying in 10s...  (then 20s)  ... RuntimeError: app crashes
```

Direct REST API probe (Supabase service-role) returned PGRST002 on 3/3 trials
across `identities`, `date_labels` tables. PostgREST's schema cache is stuck
in a broken state after 158d's RENAME + ROLLBACK churn.

`NOTIFY pgrst, 'reload schema'` from psycopg2 was issued at 03:39Z and did NOT
recover the cache. **The Supabase PostgREST service likely needs a manual
restart from the Supabase dashboard.** Path: Supabase Project → Settings →
API → "Restart project" (or Database → Replication → Reload schema cache).

### 1A-PRE. Fix PostgREST schema cache (REQUIRED first)

```bash
# Probe REST API directly — must return 200 / count for `identities`:
source venv/bin/activate && PYTHONPATH=. python -c "
import os, sys, time
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')
from supabase import create_client
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
for trial in range(3):
    t0 = time.time()
    try:
        r = sb.table('identities').select('identity_id', count='exact').limit(1).execute()
        ms = (time.time()-t0)*1000
        print(f'  Trial {trial+1}: PASS in {ms:.0f}ms (count={r.count})')
    except Exception as e:
        ms = (time.time()-t0)*1000
        print(f'  Trial {trial+1}: FAIL in {ms:.0f}ms: {str(e)[:120]}')
    time.sleep(2)
"
```

If 3/3 PASS → schema cache OK, proceed to 1A.
If any FAIL with `PGRST002` → user must restart Supabase PostgREST:
1. **User action** (Supabase dashboard): Project → Settings → API → "Restart"
   OR Database → Extensions → toggle `pg_cron` off+on (forces config reload).
   Easiest: Settings → "Pause" then "Resume" the project.
2. After Supabase restart, re-run the REST probe. Must be 3/3 PASS before
   proceeding.
3. If `NOTIFY pgrst, 'reload schema'` is preferred, run from psycopg2:
   ```python
   conn.autocommit = True
   cur.execute("NOTIFY pgrst, 'reload schema'")
   cur.execute("NOTIFY pgrst, 'reload config'")
   ```
   Note: Session 158d tried this and it did NOT recover. Dashboard restart
   is more reliable.

### 1A. Probe — does the live URL actually work?

```bash
curl -s -o /dev/null --max-time 25 -w "code=%{http_code} time=%{time_total}\n" \
    https://rhodesli.nolanandrewfox.com/health
```

If `code == 200`: skip to 1D.
If `code != 200` OR response shows `x-railway-fallback: true`: continue to 1B.

### 1B. Force a clean container restart via Railway dashboard

Manual user action required (the Railway CLI token is expired per 158d):
1. Open Railway dashboard → rhodesli project → rhodesli service
2. Click the most recent ACTIVE deploy (likely the 158c docs commit)
3. Use "Redeploy" to force a fresh container, OR
4. Stop the service, wait 30s, Start the service

### 1C. Wait for healthy edge response

```bash
# Poll every 15s until HTTP 200 (max 5 min)
for i in $(seq 1 20); do
    code=$(curl -s -o /dev/null --max-time 25 -w "%{http_code}" \
        https://rhodesli.nolanandrewfox.com/health)
    echo "$(date -u +%H:%M:%S) attempt=$i code=$code"
    [ "$code" = "200" ] && break
    sleep 15
done
```

If still 502 after 5 minutes: STOP. Escalate to user — do not attempt cutover.

### 1D. Verify a FRESH deploy from `main` can build and run

This is critical. The 158d closeout deploy FAILED healthchecks. Before any
cutover work, confirm a fresh container can start cleanly:

```bash
git commit --allow-empty -m "chore(session-158e): trigger fresh deploy verify"
git push origin main
```

Then watch Railway dashboard for the new deploy to either:
- **Succeed** (Deployment successful) → proceed
- **Fail healthchecks** → STOP. The app has a startup issue independent of
  cutover. Diagnose via Railway logs (`railway logs --service rhodesli`)
  before attempting any further DB work.

Verify post-deploy:
```bash
curl -s --max-time 25 https://rhodesli.nolanandrewfox.com/health  # must return 200
# Confirm 3 sequential 200s over 1 minute
for i in 1 2 3; do
    curl -s -o /dev/null --max-time 20 -w "%{http_code}\n" \
        https://rhodesli.nolanandrewfox.com/health
    sleep 20
done
```

All 3 must be 200. If any 502/error: STOP, escalate.

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

**Recommended: MAINTENANCE WINDOW.** Session 158d's experience showed that
fresh deploys can fail healthchecks while the underlying connection pool is
disturbed, AND that the FRESH-DEPLOY path doesn't reliably shed zombies
when there's any contention. A maintenance window gives a clean slate.

Use `AskUserQuestion`:

> "Cutover retry needs to clear zombie backends without crashing the production
> app. Two paths:
> A) MAINTENANCE WINDOW (Recommended): Stop Railway service ~2 min, terminate
>    zombies + RENAME, restart Railway service. ~5 min downtime, but proven
>    safe because no live workers can hold zombie aliases.
> B) FRESH-DEPLOY APPROACH: Push empty commit to trigger Railway redeploy,
>    wait for fresh workers, terminate zombies, then RENAME. App stays
>    available but Session 158d showed fresh deploys can also fail when pool
>    is disturbed — higher risk of cascading 502.
> Options: MAINTENANCE / FRESH-DEPLOY / HOLD."

## Phase 158e-3 — Execute chosen path

### If MAINTENANCE (recommended):

1. **User action**: Stop the rhodesli Railway service (Railway dashboard →
   rhodesli service → Settings → "Stop service" or scale to 0 replicas).
   Wait until `/health` returns connection-refused / no response.
2. **Verify production is offline**: `curl --max-time 10 https://rhodesli.nolanandrewfox.com/health`
   should fail to connect or return Railway's "service unavailable" page
   (NOT `x-railway-fallback`). If it still serves traffic from the old
   container, wait longer.
3. **Pooler health**: 3 sequential `SELECT 1` connections via session-mode
   port 5432 (use the pooler probe pattern from
   `docs/feedback/session-158d-cutover-rename.md`). Must be 3/3 PASS.
4. **Re-scan zombies**: production is offline now, any zombies in
   `pg_stat_activity` are pure stragglers. Document count.
5. **Terminate zombies** with the filter pattern from 158d:
   ```python
   query = """
       SELECT pid FROM pg_stat_activity
       WHERE datname = 'postgres'
         AND state = 'idle in transaction'
         AND state_change < NOW() - INTERVAL '1 hour'
         AND (query LIKE '%gedcom_individuals%' OR query LIKE '%backfill_gedcom%')
   """
   # for each pid: SELECT pg_terminate_backend(pid)
   ```
6. **Run RENAME**: `PYTHONPATH=. python scripts/session158b_cutover_rename.py --execute`
   With zombies clear AND production offline, this should land in < 1s.
7. **User action**: Restart the rhodesli Railway service.
8. **Verify health**: 3 sequential 200s over 1 minute. If any 5xx:
   ROLLBACK via `--rollback`, escalate to user.
9. **Total downtime budget**: target ≤ 8 minutes from stop to verified-200.

### If FRESH-DEPLOY (higher risk per Session 158d learnings):

1. `git commit --allow-empty -m "chore: trigger fresh deploy for 158e cutover" && git push`
2. Wait for Railway deploy completion AND verify /health = 200 over 1 min.
   If the deploy fails healthchecks (as 158d's deploys did), STOP and switch
   to MAINTENANCE.
3. After fresh workers are confirmed healthy, run zombie cleanup carefully:
   filter MUST exclude any session created after the fresh-deploy timestamp.
4. Run RENAME with retries (max 3 on lock_timeout).
5. Verify /health stays 200 throughout — poll every 15s during RENAME.
6. If app goes 502 at any point: ROLLBACK immediately.

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
  redeployed AND been verified-healthy since then, the new worker pool should
  be clean. If NOT verified, assume zombies may still exist (158d ended with
  production 502 — never confirmed clean).
- **Production app at 158d session close**: 502 with `x-railway-fallback: true`
  for ≥ 50+ minutes. Railway dashboard showed 158c deploy as "ACTIVE" but edge
  could not reach upstream. Two automatic redeploys (cutover RENAME commit and
  closeout commit) BOTH failed network healthchecks. **Manual Railway service
  restart is the most likely required first step in 158e.**
- Pooler at 158d session close: HEALTHY (3/3 PASS, latency 642ms-16s).
  Supabase side is stable; the issue is entirely Railway/app-side container
  startup.

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
