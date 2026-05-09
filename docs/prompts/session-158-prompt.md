# Session 158 — PRD-063 Day 3: Cutover + DROP v1 + VACUUM FULL

**Mode**: implementation
**Predecessor**: Session 157b (`docs/assessments/session-157b-assessment.md`, `docs/session_logs/session-157b-log.md`, `docs/feedback/session-157b-day-2-confidence.md`)
**Successor**: TBD — likely a stabilization/UAT-only session if 158 finishes clean
**Critical deadline**: 2026-05-29 — Supabase free-tier 1.1 GB ceiling. Today's run starts the 20-day countdown. Re-confirm via `date -u`.

## Why this session exists

PRD-063 Day 3 cuts over to v2-only reads, drops v1 `gedcom_individuals` + `gedcom_families`, runs `VACUUM FULL`, and validates that the projected ~98% storage reduction lands. 157b Track B4 confidence assessment recommended **PROCEED** (`docs/feedback/session-157b-day-2-confidence.md`).

**BUT — there is one design issue 157b surfaced AFTER the assessment shipped**: v2 currently contains only `is_current=TRUE` rows (a snapshot of "current state"). The historical states (where a person's birth_place was corrected across versions, etc.) are still in v1's `is_current=FALSE` rows. If we DROP v1 without also migrating those historical rows, we permanently lose the ability to answer "what changed for this person over time."

The user's explicit ask: *"I want to make sure we are able to maintain some sense of GEDCOM change over time. We should be able to understand and query what was updated, corrected, or added for a given person without the giant sprawl."*

**This session MUST gate all irreversible actions on proving change-history queryability works. If v2 doesn't have the data needed, Phase 158-2 backfills it. If even that doesn't work, we HOLD the cutover for 158b.**

## Setup

```bash
echo "158" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
bash scripts/harness-check.sh             # warn-only on doc-cap acceptable
make test-fast                             # baseline — must be green (4259 expected)
git log origin/main..HEAD                  # MUST be empty
git pull origin main                       # safety
git status --short                         # nothing meaningful (only .claude/current_session.txt)
date -u                                    # confirm date for deadline math
```

## FIRST ACTION (background subagent) — Retroactive `/session-review` on Session 157b

Same pattern as 157b's first action. Launch a background subagent with the prompt below. Don't block on it — it parallelizes with Phase 158-0.

```
You are the retroactive-/session-review subagent for Session 158. Read:
- docs/assessments/session-157b-assessment.md
- docs/session_logs/session-157b-log.md
- docs/prompts/session-157b-prompt.md
- docs/feedback/session-157b-day-2-confidence.md
- The 18 commits 7e11642d..57ba1603 (read each via `git show <hash> --stat`)

Invoke the /session-review skill against Session 157b. Save output to
docs/feedback/session-157b-retroactive-review.md with provenance header:
  **Reviewer**: /session-review skill (Claude Opus 4.7)
  **Subject**: Session 157b (retroactive)
  **Date**: <today ISO>
  **Commits in scope**: 7e11642d..57ba1603 (18 commits)

Capture: concerns the assessment missed, P0/P1/P2/P3 red flags, gaps
between prompt and shipped work, superficial-work flags (e.g., the curl-
based browser verify vs prompt's "claude-in-chrome MCP" — was that a
shortcut?). Specifically grade: did 157b's PROCEED verdict really clear
the change-history question, or did it punt?

Return: file path, top 3 concerns, auto-fix recommendation. Commit:
"docs(session-158): retroactive /session-review on session 157b"

Work on main directly. Do NOT modify code. Do NOT use --no-verify.
On budget exhaustion: stop and report honestly (Lesson 182).
```

## Pre-flight budget canary (Lesson 182)

This session also fires parallel work in Track 2 (historical backfill if needed). Apply the canary pattern: launch ONE subagent first when parallel work begins, verify >100 tokens AND >30s consumed, only then launch the second.

## Required first reads (in order)

1. `docs/feedback/session-157b-day-2-confidence.md` — the PROCEED verdict and its caveats.
2. `docs/feedback/session-157b-track-e-deferred.md` — Track E carries to 158.
3. `docs/ml/ALGORITHMIC_DECISIONS.md` AD-244 — v2 schema lineage.
4. `docs/prds/063_gedcom_mirror_efficient_redesign.md` — full design.
5. `scripts/session156_backfill_gedcom_v2.py` — the original backfill (only `is_current=TRUE`).
6. `app/gedcom_dual_read.py` — the per-id reader; check whether bulk readers also need wiring.
7. Lessons 173-182 in `tasks/lessons.md`.

## Non-negotiable rules

1. **READ-ONLY on production browsers** (`.claude/rules/browser-read-only.md`).
2. **Codex CLI invocation**: `codex exec "<prompt>" </dev/null`. NEVER `--full-auto`.
3. Commit atomically per phase. /clear between phases at 300+ transcript lines.
4. Every ML decision gets an AD entry. AD-244 already on main. AD-245 likely (dual-read), AD-246 likely (history-backfill strategy), AD-247 likely (cutover sequence).
5. **R2 reversibility test**: re-verify the R2 archives at `gedcom-version-snapshots/2026-05-08-session-156/v9/` are readable BEFORE any irreversible action. If unreadable: STOP, surface to user.
6. `make test-fast` before every commit.
7. **Prefer RENAME over DROP** for the cutover step. RENAME is reversible in seconds; DROP is reversible only via R2 restore (~1h). Keep tables renamed for at least the duration of the session before final DROP.
8. **No DROP unless every gating phase passes.** The session MAY end at "rename + verify" with DROP punted to 158b if any verification fails.

## Concurrent-genealogy-session resilience

Same R1-R9 as 157b. R1 marker file held during:
- Phase 158-2 historical backfill --execute (irreversible writes)
- Phase 158-4 cutover (RENAME)
- Phase 158-6 DROP v1 + VACUUM FULL
- Phase 158-9 Track E GEDCOM upload (irreversible)

Between phases the marker is removed so genealogy sessions can land.

---

## Phase 158-0 — Carry verification + R2 archive readability (~10 min)

```bash
# 1. v2 row counts unchanged from 157b end
python -c "
from dotenv import load_dotenv; load_dotenv()
from app.supabase_data import get_supabase_client
sb = get_supabase_client()
for t in ['gedcom_individuals_v2', 'gedcom_families_v2', 'gedcom_change_manifest']:
    r = sb.table(t).select('*', count='exact').limit(1).execute()
    print(f'{t}: count={r.count}')
# Expected: 21998 / 6741 / 9 (or higher if a concurrent session imported)
"

# 2. v1 still intact
python -c "
from dotenv import load_dotenv; load_dotenv()
from app.supabase_data import get_supabase_client
sb = get_supabase_client()
for t in ['gedcom_individuals', 'gedcom_families']:
    total = sb.table(t).select('*', count='exact').limit(1).execute().count
    current = sb.table(t).select('*', count='exact').eq('is_current', True).limit(1).execute().count
    print(f'{t}: total={total}, is_current=TRUE={current}, historical={total-current}')
"

# 3. Re-run 157b catch-up backfill — should still be 0
python scripts/session157_full_backfill_gedcom_v2.py --dry-run

# 4. Harry + Belle Isle still intact
python -c "
from dotenv import load_dotenv; load_dotenv()
from app.supabase_data import get_supabase_client
sb = get_supabase_client()
h = sb.table('identities').select('anchor_ids,version_id').eq('identity_id','d74cb556-6d44-4288-ade3-1cc8fa2b45a6').execute().data[0]
n = sb.table('identities').select('name,state,metadata').eq('identity_id','ef39908e-283a-4cec-8f72-3ec83bc8d84f').execute().data[0]
print(f'Harry: anchors={len(h[\"anchor_ids\"])}, version_id={h[\"version_id\"]}')
print(f'Belle Isle: name={n[\"name\"]!r}, state={n[\"state\"]}, has_notes={bool(n[\"metadata\"].get(\"notes\"))}')
"

# 5. R2 archive readability — CRITICAL gate before any irreversible action
python -c "
import boto3, os
from dotenv import load_dotenv; load_dotenv()
s3 = boto3.client('s3',
    endpoint_url=f'https://{os.environ[\"R2_ACCOUNT_ID\"]}.r2.cloudflarestorage.com',
    aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'])
bucket = 'rhodesli-photos'
prefix = 'gedcom-version-snapshots/2026-05-08-session-156/'
resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
contents = resp.get('Contents', [])
print(f'R2 archive at {prefix}:')
print(f'  files: {len(contents)}')
total_bytes = sum(o['Size'] for o in contents)
print(f'  total bytes: {total_bytes:,}')
# Spot-check: try reading the v9 manifest
v9_keys = [o['Key'] for o in contents if 'v9/' in o['Key']][:3]
for k in v9_keys:
    head = s3.head_object(Bucket=bucket, Key=k)
    print(f'  {k}: {head[\"ContentLength\"]:,} bytes, etag={head[\"ETag\"]}')
"
```

**Stop conditions** (any of these = HALT, surface to user):
- v2 row counts changed unexpectedly (concurrent session risk — investigate)
- 157b catch-up backfill shows non-zero deltas (run --execute first; re-verify; THEN proceed)
- v1 row counts changed unexpectedly (someone imported between 157b and 158)
- Harry or Belle Isle state diverged (data integrity concern)
- R2 archive missing files OR head_object fails (rollback path broken — DO NOT proceed to any DROP)

If R2 fails, the session goal becomes "fix R2 archive integrity" and 158 cutover punts to 158b. We do NOT drop v1 without a verified rollback path.

---

## Phase 158-1 — Change-history reality check (CRITICAL GATE — ~30 min)

The user's explicit requirement: queryable change-over-time without v1's sprawl. Before ANY cutover, prove this works on v2.

### 1.1 — Pick a known-changed person

We need a person whose data has demonstrably changed across GEDCOM versions. Candidates:
- **Albert Fox `@I143@`** (or whatever his GEDCOM xref is) — likely had Detroit/NYC corrections
- **Esther Burd Fox** — has had spelling corrections (B-U-R-D)
- **Reva Heft** — corrected from Irving's wife to Meyer's wife (Lesson on `feedback_reva_heft_correction.md`)

Resolve their gedcom_ids:

```sql
SELECT gedcom_id, name, surname FROM gedcom_individuals
WHERE surname = 'Fox' AND given_name = 'Albert'
ORDER BY version_id;
```

### 1.2 — Check v1 has multiple versions for them (the change-history corpus)

```sql
SELECT gedcom_id,
       COUNT(*) AS version_count,
       COUNT(DISTINCT payload_hash) AS distinct_states,
       MIN(version_id) AS first_seen,
       MAX(version_id) AS last_seen
FROM gedcom_individuals
WHERE gedcom_id IN ('@I143@', '@I_ESTHER@', '@I_REVA@')  -- replace with real xrefs
GROUP BY gedcom_id;
```

Expected: `version_count >= 7` (one per major version), `distinct_states >= 1` (more than 1 means they changed). If `distinct_states = 1` for ALL test people, change-history is moot (nothing changed) and we can skip the historical backfill.

### 1.3 — Check v2 only has the current state (the gap to close)

```sql
SELECT gedcom_id, COUNT(*) AS row_count, COUNT(DISTINCT payload_hash) AS distinct_states
FROM gedcom_individuals_v2
WHERE gedcom_id IN ('@I143@', '@I_ESTHER@', '@I_REVA@')
GROUP BY gedcom_id;
```

Expected: `row_count = 1`, `distinct_states = 1` per person (because 156 backfill only took `is_current=TRUE`).

### 1.4 — Decide change-tracking strategy

If v1 shows `distinct_states > 1` for any test person AND v2 shows `row_count = 1`: we have a real gap. Choose:

| Option | Approach | Storage cost | Query speed | Reversibility |
|---|---|---|---|---|
| **A. Full historical backfill** (RECOMMENDED) | Backfill `is_current=FALSE` rows from v1 to v2, dedup by payload_hash, set first/last_seen_version per row | v2 grows from 22K to ~30-50K rows (still 4-6× smaller than v1) | per-id query: same as current; per-id-with-history: O(versions) for that person — fast | full — once in v2, change history queries work natively |
| **B. Keep v1 alive for history** | Don't DROP v1 individuals + families; only DROP `gedcom_change_log` (the 1.65M-row noise) | Saves ~300 MB instead of ~700 MB | history queries hit v1 directly | best — nothing dropped beyond change_log |
| **C. R2 archive of historical rows + query helper** | Archive `is_current=FALSE` rows to R2 as compressed JSON; query helper pulls on demand | Saves ~700 MB, history queries are slow (R2 fetch ~500ms) | per-id current: fast; per-id-history: slow (S3 fetch + decompress) | full via R2 |

**Recommendation: Option A.** Backfill ~10-30K additional historical rows. Total v2 ≈ 30-50K vs v1's 196K — still a >4× reduction, AND we get full change-history queryability natively.

User must confirm choice before proceeding. Surface the decision via `AskUserQuestion`.

### 1.5 — Demonstrate the target query (proof of concept on v1)

To prove the query shape works, run it against v1 first (since v1 has all the history):

```sql
-- "Show me Albert Fox's change history"
SELECT version_id, payload_hash, name, given_name, surname,
       birth_date, birth_place, death_date, death_place,
       is_current
FROM gedcom_individuals
WHERE gedcom_id = '@I143@'  -- replace with real Albert xref
ORDER BY version_id;
```

Save output to `docs/feedback/session-158-change-history-proof.md`. Show: this same query against v2 (post-backfill) must return logically equivalent rows (modulo payload_hash dedup — identical adjacent rows collapse).

Commit: `docs(session-158): change-history reality check (Phase 158-1)` — includes the query, the v1 result, the v2 result, and the chosen option (A/B/C) with user confirmation.

---

## Phase 158-2 — Historical backfill (CONDITIONAL on Option A — ~45 min)

Only if Phase 158-1 chose Option A.

### 2.1 — Write `scripts/session158_historical_backfill_gedcom_v2.py`

Mirrors `scripts/session156_backfill_gedcom_v2.py` but reads ALL rows (not filtered by `is_current=TRUE`):

```python
# Read all rows
cur.execute("SELECT * FROM gedcom_individuals")  # no is_current filter

# Aggregate by payload_hash, tracking min/max version_number per hash
aggregated = {}
for row in cur.fetchmany(5000):
    phash = row['payload_hash'] or compute_canonical_hash(row, KEY_FIELDS)
    v_num = version_map[row['version_id']]
    if phash in aggregated:
        agg = aggregated[phash]
        agg['first_seen_version'] = min(agg['first_seen_version'], v_num)
        agg['last_seen_version'] = max(agg['last_seen_version'], v_num)
    else:
        aggregated[phash] = {**row_to_v2_record(row), 'first_seen_version': v_num, 'last_seen_version': v_num}

# INSERT into v2 with ON CONFLICT (payload_hash) DO NOTHING
# (existing rows from 156's is_current=TRUE backfill will not be overwritten;
#  new historical rows for the same gedcom_id will INSERT alongside).
# UPDATE first_seen_version where the existing row's first_seen_version > computed min
# UPDATE last_seen_version where existing < computed max
```

Same script for `gedcom_families`. Defaults to `--dry-run`. Output report to `docs/feedback/session-158-historical-backfill-report.md` with:
- v1 total rows scanned
- unique payload_hashes (this is the post-backfill v2 row count for individuals + families)
- new INSERT count vs already-present (from 156)
- first_seen/last_seen UPDATE counts
- final v2 size estimate

### 2.2 — Run dry-run, surface report

If unique payload_hash count > 100K: STOP. Something is wrong (more historical states than expected — investigate before INSERTing).

If 22K-50K (expected): proceed to --execute.

### 2.3 — Run --execute (R1 marker held)

```bash
touch .claude/parallel_session_active
python scripts/session158_historical_backfill_gedcom_v2.py --execute
rm .claude/parallel_session_active
```

### 2.4 — Re-verify the change-history query on v2

```sql
SELECT first_seen_version, last_seen_version, name, birth_place, death_place
FROM gedcom_individuals_v2
WHERE gedcom_id = '@I143@'
ORDER BY first_seen_version;
```

Expected: multiple rows showing Albert's evolution. Compare to the v1 baseline from Phase 158-1 — counts should match (modulo payload_hash dedup). If they don't: STOP.

### 2.5 — Add helper

`app/gedcom_dual_read.py::get_individual_history(gedcom_id) -> list[dict]`:
- Returns all v2 rows for the gedcom_id sorted by `first_seen_version`
- Each dict: name, given_name, surname, gender, birth_date, birth_place, death_date, death_place, first_seen_version, last_seen_version, payload_hash

3 unit tests:
1. Single-state person (no changes) → returns 1 row
2. Multi-state person → returns N rows in version order
3. Unknown gedcom_id → returns []

Commit: `feat(session-158): historical backfill v1 → v2 + history helper (Phase 158-2)` with AD-246 (historical backfill strategy decision).

---

## Phase 158-3 — Pre-flight backups + R2 fresh snapshot (~15 min)

**This is the irreversibility gate.** No table modifications until this passes.

### 3.1 — Fresh R2 snapshot of v1 individuals + families + change_log

Even though 156's R2 archive is the canonical rollback, take a FRESH snapshot now:
- Captures any 157b/158 changes (should be none, but verify)
- Provides a clean "minutes-ago" baseline

```bash
# Use psycopg2 + COPY TO STDOUT, gzip, upload to R2
python scripts/session158_r2_preflight_snapshot.py --execute
```

Targets:
- `gedcom_individuals` → `gedcom-pre-drop-snapshots/$(date -u +%Y-%m-%d)-session-158/gedcom_individuals.csv.gz`
- `gedcom_families` → same prefix
- `gedcom_change_log` → same prefix
- `gedcom_versions` → same prefix (small but useful for replay context)

Verify each upload via head_object + size check. Compute SHA256 of each gz file locally before upload, verify ETag matches post-upload. Save manifest to `docs/feedback/session-158-r2-preflight-manifest.md`.

### 3.2 — Re-verify both R2 archives are readable

```python
# 156 archive AND 158 fresh snapshot
for prefix in ['gedcom-version-snapshots/2026-05-08-session-156/v9/',
               'gedcom-pre-drop-snapshots/$(date -u +%Y-%m-%d)-session-158/']:
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    for obj in resp['Contents']:
        head = s3.head_object(Bucket=bucket, Key=obj['Key'])
        assert head['ContentLength'] > 0
```

### 3.3 — pg_dump of relevant tables (local backup, in addition to R2)

```bash
mkdir -p backups/session-158
pg_dump --host=aws-0-us-west-2.pooler.supabase.com --port=6543 \
        --username=postgres.fvynibivlphxwfowzkjl \
        --table=gedcom_individuals \
        --table=gedcom_families \
        --table=gedcom_change_log \
        --table=gedcom_versions \
        --table=gedcom_individuals_v2 \
        --table=gedcom_families_v2 \
        --table=gedcom_change_manifest \
        postgres | gzip > backups/session-158/gedcom_pre_drop_$(date -u +%Y%m%dT%H%M%SZ).sql.gz
```

Verify:
- File created and >100 MB (the v1 tables are large)
- Decompresses cleanly: `gunzip -t backups/session-158/*.sql.gz`
- Contains expected table names: `gunzip -c | grep -E "^CREATE TABLE.*gedcom_(individuals|families)"`

Commit: `chore(session-158): pre-flight backups — R2 snapshot + pg_dump (Phase 158-3)`.

---

## Phase 158-4 — Cutover via RENAME (NOT DROP — ~20 min)

Reversible. Tables stay on disk, just renamed. Reads route through dual-read helper which now finds v2 only.

### 4.1 — Wire the bulk loader to v2

`app/relationship_routes.py::_load_gedcom_individuals` currently reads `current_gedcom_individuals` view (which sources from v1's `is_current=TRUE` rows). Replace with:

```python
# Use v2 directly — current state is implicit (v2 only stores deduped current rows
# from the perspective of the user; historical rows are also there but the bulk
# loader only needs the latest state per gedcom_id).
def _v2_bulk_query():
    sb = get_supabase_client()
    return _load_gedcom_rows(
        sb, "gedcom_individuals_v2", _GEDCOM_THIN_FIELDS,
        # Within v2, dedup by gedcom_id taking max(last_seen_version) — but
        # for current-snapshot reads we can just SELECT the latest payload per
        # gedcom_id. SQL: SELECT DISTINCT ON (gedcom_id) ... ORDER BY gedcom_id,
        # last_seen_version DESC. Note: needs a server-side approach.
    )
```

This is non-trivial. Either:
- **(a)** Add a database VIEW `current_gedcom_individuals_v2` that does the DISTINCT ON. Re-point `_load_gedcom_individuals` to read from this view. (Recommended — view is cheap.)
- **(b)** Pull all v2 rows and dedup in Python.
- **(c)** Add `is_current_state BOOLEAN` to v2 and maintain it via trigger / backfill update. (Heaviest — schema change.)

**Recommended: (a)**. Create the view in migration `scripts/migrations/session158_current_v2_view.sql`:

```sql
-- Tiebreaker order matters: when two rows share last_seen_version (e.g., both
-- last seen at v9), prefer the row with the LATER first_seen_version — i.e.,
-- the more recently introduced state. payload_hash is a final deterministic
-- fallback so the view is stable across runs.
CREATE OR REPLACE VIEW current_gedcom_individuals_v2 AS
SELECT DISTINCT ON (gedcom_id) *
FROM gedcom_individuals_v2
ORDER BY gedcom_id, last_seen_version DESC, first_seen_version DESC, payload_hash;

CREATE OR REPLACE VIEW current_gedcom_families_v2 AS
SELECT DISTINCT ON (family_gedcom_id) *
FROM gedcom_families_v2
ORDER BY family_gedcom_id, last_seen_version DESC, first_seen_version DESC, payload_hash;
```

Sanity check after creating each view: `SELECT COUNT(*) FROM current_gedcom_individuals_v2` should equal `COUNT(DISTINCT gedcom_id) FROM gedcom_individuals_v2`.

Apply via `psycopg2`. Verify row counts: `SELECT COUNT(*) FROM current_gedcom_individuals_v2` should equal distinct gedcom_id count.

Update `app/gedcom_dual_read.py` and `app/relationship_routes.py::_load_gedcom_individuals` to read from `current_gedcom_individuals_v2`. Re-run unit tests + `make test-fast`.

Commit: `feat(session-158): current_gedcom_individuals_v2 view + bulk loader rewire (Phase 158-4.1)`.

### 4.2 — RENAME v1 tables (REVERSIBLE)

```sql
-- Inside a single transaction so partial-rename can't happen
BEGIN;
ALTER TABLE gedcom_individuals RENAME TO _dropped_gedcom_individuals_session158;
ALTER TABLE gedcom_families RENAME TO _dropped_gedcom_families_session158;
ALTER TABLE gedcom_change_log RENAME TO _dropped_gedcom_change_log_session158;
DROP VIEW IF EXISTS current_gedcom_individuals;
COMMIT;
```

**To roll back**: `ALTER TABLE _dropped_gedcom_individuals_session158 RENAME TO gedcom_individuals` etc., recreate the view, restart workers.

Apply via `scripts/session158_cutover_rename.py --execute` (with --dry-run default and --rollback flag for the reverse).

Commit: `feat(session-158): cutover RENAME v1 → _dropped_session158 (Phase 158-4.2, REVERSIBLE)`.

### 4.3 — Smoke + browser verify in renamed state

```bash
make test-fast                    # 4259+ pass
python scripts/production_smoke_test.py --url https://rhodesli.nolanandrewfox.com
```

curl-based browser verify of the 6 canonical pages + GEDCOM-aware pages:
- `/` — landing (200)
- `/people` (200)
- `/person/ef39908e-...` — Belle Isle (200, GEDCOM context renders)
- `/person/<albert-id>` — Albert Fox (200, GEDCOM context renders, multiple change states displayed if Phase 158-2 ran)
- `/tree` — full tree (200, no errors in HTMX responses)
- `/tools/search?q=Fox` — search hits v2 (200, results returned)
- `/tools/compare`, `/tools/estimate` (200)
- `/garbage-url` (404)

Save evidence to `docs/feedback/session-158-post-rename-verify.md`.

**Stop conditions**: any 5xx, any "GEDCOM data unavailable" rendered string, any test regression.

If rollback needed: run `scripts/session158_cutover_rename.py --rollback`. Document the failure mode. Session ends here — DROP punts to 158b.

---

## Phase 158-5 — Wait period + sustained validation (~5 min, but counts toward session time)

After successful Phase 158-4: pause for 5 minutes (literally — sleep, then re-verify). This lets any in-flight requests settle and surfaces issues that don't manifest immediately.

```bash
sleep 300
# Re-run the same smoke + browser checks from 4.3
# Pull production logs from Sentry / Railway dashboard — look for any new errors
```

If issues surface: rollback (RENAME back) and end session. If clean: proceed to DROP.

---

## Phase 158-6 — DROP renamed tables + VACUUM FULL (IRREVERSIBLE except via R2/pg_dump — ~15 min)

**Final irreversible step.** Gates:
- [x] Phase 158-1 change-history reality check passed
- [x] Phase 158-2 historical backfill succeeded (if Option A)
- [x] Phase 158-3 R2 + pg_dump backups verified
- [x] Phase 158-4 cutover passed smoke + browser verify
- [x] Phase 158-5 wait period clean

If ANY gate failed: do NOT enter Phase 158-6.

### 6.0 — User authorization gate (MANDATORY)

Before any DROP, present the irreversibility decision to the user via `AskUserQuestion`:

> "All 5 pre-DROP gates passed (carry / change-history / backfill / backups / rename+wait). The next step DROPs `_dropped_gedcom_individuals_session158`, `_dropped_gedcom_families_session158`, `_dropped_gedcom_change_log_session158` and runs VACUUM FULL on Supabase. After this point, recovery is via R2 archive (~1h) or local pg_dump (~30min). Options:
> - PROCEED with DROP + VACUUM FULL now
> - HOLD — stay in renamed state for a longer wait period (24h+); resume via 158b
> - ROLLBACK — RENAME back to v1 names; abandon cutover; investigate"

If user picks PROCEED: continue to 6.1. If HOLD: write a continuation note to `docs/feedback/session-158-hold-decision.md` and stop the session at this phase. If ROLLBACK: run `scripts/session158_cutover_rename.py --rollback`, document the decision, end session.

```sql
BEGIN;
DROP TABLE _dropped_gedcom_individuals_session158;
DROP TABLE _dropped_gedcom_families_session158;
DROP TABLE _dropped_gedcom_change_log_session158;
COMMIT;

-- VACUUM FULL — note this requires AccessExclusiveLock and rewrites the relation
-- Brief downtime expected on each table. Pool the locks carefully.
VACUUM FULL gedcom_individuals_v2;
VACUUM FULL gedcom_families_v2;
VACUUM FULL gedcom_change_manifest;
VACUUM FULL gedcom_records;
VACUUM FULL gedcom_events;
VACUUM FULL gedcom_relationships;
VACUUM FULL gedcom_versions;

-- Re-query DB size
SELECT pg_size_pretty(pg_database_size('postgres'));
```

Apply via `scripts/session158_drop_and_vacuum.py --execute`. Holds R1 marker throughout. Captures pre/post sizes to `docs/feedback/session-158-drop-vacuum-report.md`.

**Expected result**: DB size drops from ~2.22 GB to ~600-700 MB (~70% reduction). If size is >1.0 GB post-VACUUM: investigate which table is unexpectedly large.

Commit: `feat(session-158): DROP v1 individuals + families + change_log + VACUUM FULL (Phase 158-6, IRREVERSIBLE)`.

---

## Phase 158-7 — Post-cutover verification (~15 min)

```bash
# Re-run query timing from 157b to confirm post-cutover parity
python scripts/session157b_query_timing.py
# Save report at docs/session_context/session-158-query-timing-postcutover.md

# Confirm verdict still GREEN (or BETTER — fewer rows in v1 means no v1 fallback ever fires)
```

Browser verify the 6 canonical pages a final time. Confirm Albert Fox change-history query still returns multiple rows.

Commit: `chore(session-158): post-cutover query timing + verification (Phase 158-7)`.

---

## Phase 158-8 — Track E (GEDCOM upload UAT, carried from 157b — ~45 min)

Now that the cutover is complete, we can safely run Track E. Re-fresh-check the GEDCOM file:

### 8.1 — User confirmation + sha256 freshness

```bash
ls -la ~/Downloads/gedcom_20260508/
shasum -a 256 ~/Downloads/gedcom_20260508/Fox_Capeluto_Fogel_Waldorf*.ged
ls -la ~/Downloads/ | grep -i gedcom
```

**ASK THE USER** via `AskUserQuestion`: "Confirm GEDCOM file path + sha256 + that no newer file exists in ~/Downloads/. The file from Session 156 is `Fox_Capeluto_Fogel_Waldorf Family Tree.ged` (sha256 f7832541..., 17.08 MB). Has anything newer been downloaded?"

If newer: re-archive to R2 under new prefix `gedcom-source-snapshots/$(date -u +%Y-%m-%d)-session-158/`. If not: re-use 156's archive.

### 8.2 — Pre-import baseline

Capture current row counts for ALL gedcom_* tables (v1 events/relationships/records still alive; v2 individuals/families/change_manifest). Capture DB size.

### 8.3 — Upload via importer

The v1 importer wrote to v1 tables (which are now DROPPED for individuals + families). Choose:

| Path | Description | Risk |
|---|---|---|
| **A** | Re-create v1 tables from R2 archive temporarily, run v1 importer, then re-do the cutover | High — defeats 158's purpose, requires running cutover twice |
| **B** | Build a v2-aware importer (extends existing for v2 INSERT instead of v1) | Medium — new code on the cutover day, but isolated to import path |
| **C** | Skip Track E this session; defer to 159 once a v2 importer is built | Low — but Track E rolls AGAIN |

**Recommended: B** — build the v2-aware importer in this session. Path A defeats the cutover; Path C delays Track E indefinitely (it's been deferred from 156→157→157b→now).

The v2 importer needs to:
1. Parse the .ged file (re-use existing parser)
2. Compute payload_hash for each individual + family
3. INSERT into v2 with ON CONFLICT (payload_hash) DO NOTHING
4. Update first_seen_version + last_seen_version
5. Write a row to `gedcom_change_manifest` summarizing the version
6. (Possibly) write to v1's still-alive `gedcom_events`, `gedcom_relationships`, `gedcom_records` if the importer historically did so

Surface design choices to user before implementing. The complexity is real — Track E may legitimately roll to 159 if path B's design doesn't fit in the remaining session budget.

### 8.4 — 4 verification points (per user during 155 closeout)

1. Easier to upload — was the rollback path clean if needed?
2. Easier to understand changes per family — query `gedcom_change_manifest` for new version vs prior; query Albert Fox's change history; show before/after for any corrected fields.
3. Storage growth fixed — measure size delta. Expected: small (delta only, dedup catches identical rows).
4. Supabase not broken — `/api/admin/db-size`, `/health`, browser-verify person/tree/search, `pytest tests/test_gedcom_*.py -q --no-header`, `pytest tests/test_data_integrity.py -q --no-header`.

### 8.5 — UAT writeup + commit

`docs/feedback/session-158-gedcom-upload-uat.md`. Commit: `feat(session-158): GEDCOM upload UAT via v2 importer (Phase 158-8)`.

---

## Phase 158-9 — Post-import re-verification (~10 min)

```bash
# Final query timing
python scripts/session157b_query_timing.py
# Final DB size
python -c "..."
# Final harness check
bash scripts/harness-check.sh
```

Browser verify person/tree/search a final time. Confirm Albert Fox / Belle Isle / known recent additions all render correctly.

---

## Track Z — Closeout (~30 min, mandatory 12-step harness)

Per `.claude/rules/session-defaults.md`:

1. Assessment: `docs/assessments/session-158-assessment.md` with full AI Tool Usage section + irreversibility gates table (which gates passed, which failed, what was rolled back if anything)
2. CHANGELOG: bump to v0.99.75 (or v1.0.0 if the cutover warrants a major version mark — propose to user)
3. ROADMAP + SESSION_HISTORY: update both
4. BACKLOG: close items
   - PRD-063-DAY-3-IMPL → CLOSED
   - GEDCOM-V2-OTHER-TABLES → DECISION applied (kept v1 events/relationships/records alive)
   - GEDCOM-UAT-156 → CLOSED (or rolled to 159 if Phase 158-8 didn't complete)
   - Add: any post-cutover stabilization items
5. `git push origin main`
6. Browser verify the canonical 6 pages + GEDCOM-aware pages a final time
7. `git log origin/main..HEAD` empty
8. `git status --short` clean
9. `bash scripts/harness-check.sh` exit 0
10. `bash scripts/backup-memory.sh`
11. Run `/session-review` skill on 158 itself
12. Codex final-pass audit on all 158 commits — **MANDATORY this session** (not "recommended"). The cutover is high-stakes; an independent fresh-context audit catches anything we missed.

---

## Success gates

| Gate | How to check |
|---|---|
| Phase 158-0 carry verification | All 157b deliverables intact; R2 archive readable |
| Phase 158-1 change-history gate | v1 baseline query returns multi-row history; user-chosen strategy committed |
| Phase 158-2 historical backfill (if A) | v2 row count grew to expected; multi-row history query returns matching results |
| Phase 158-3 backups verified | R2 snapshot + pg_dump both readable; SHA256 + ETag match |
| Phase 158-4 cutover smoke + browser PASS | All 6 canonical pages 200; GEDCOM-aware pages render; no 5xx |
| Phase 158-5 wait-period clean | No new errors after sleep 300 |
| Phase 158-6 DROP + VACUUM FULL | DB size drops to <1.0 GB (target 600-700 MB) |
| Phase 158-7 query timing | GREEN verdict still holds |
| Phase 158-8 GEDCOM upload UAT | 4 verification points pass; OR explicit deferral to 159 |
| Phase 158-9 final verification | All canonical pages + change-history queries work |
| Track Z full closeout | All 12 harness steps; codex final-pass mandatory |

## Phase timing estimates

| Phase | Solo-time |
|---|---|
| 158-0 carry verification | 10 min |
| 158-1 change-history reality check | 30 min |
| 158-2 historical backfill (Option A) | 45 min |
| 158-3 pre-flight backups | 15 min |
| 158-4 cutover RENAME | 20 min |
| 158-5 wait + re-verify | 10 min |
| 158-6 DROP + VACUUM FULL | 15 min |
| 158-7 post-cutover verification | 15 min |
| 158-8 Track E GEDCOM upload UAT | 45 min |
| 158-9 final verification | 10 min |
| Z closeout | 30 min + 15 min Codex audit |
| **Total** | **~4h 30min** (with parallelization on backfill + audit ~3h 45min) |

## Stop-and-roll-to-159 conditions

The session is designed with explicit early-exit points. If ANY of the following triggers, end the session cleanly with the appropriate phase as the stopping point:

| Trigger | Stop after | Rolled to 159 |
|---|---|---|
| 158-1 chooses Option B (keep v1 alive) | 158-1 | DROP work re-evaluated; Track E |
| 158-1 chooses Option C (R2 archive history) | 158-2 (R2 archive build) | DROP + VACUUM + Track E |
| 158-2 historical backfill produces wrong row count | 158-2 | redesign; full retry |
| 158-3 backups fail | 158-3 | R2 archive repair; backup verification |
| 158-4 cutover smoke fails | 158-4 (rollback executed) | re-investigate dual-read coverage |
| 158-5 wait period surfaces errors | 158-5 (rollback executed) | new design needed |
| 158-6 VACUUM FULL exceeds 30min OR DB size doesn't drop | 158-7 | investigate before next cutover attempt |
| 158-8 v2 importer design is non-trivial | 158-7 | Track E to 159 (per the original Track E design path C) |

In all stop cases: capture state, document decision, write 159 prompt with the carry-over.

## What to NOT do this session

- DO NOT DROP without all gates passed (see Phase 158-6 gate list).
- DO NOT skip the historical backfill if Option A chosen — change-history is the user's explicit requirement.
- DO NOT use `--full-auto` on Codex.
- DO NOT use `--no-verify` on commits.
- DO NOT modify R2 archive content (read-only).
- DO NOT click action buttons in browser verification (READ-ONLY per browser-read-only.md).
- DO NOT claim Track E completed if path B's importer isn't fully tested — better to defer.
- DO NOT skip the Codex final-pass audit at closeout — high-stakes session warrants the audit.

## Codex CLI invocation reminder

```bash
codex exec "<prompt>" </dev/null    # Form A — recommended
codex exec <<< "<prompt>"           # Form B
echo "<prompt>" | codex exec -      # Form C
```

`~/.codex/config.toml`: model = "gpt-5.5", reasoning_effort = "xhigh". Verify pin freshness via `bash scripts/harness-check.sh` (refreshes if >14 days old).

## Open question for user (BEFORE kicking off)

Phase 158-1 surfaces a strategy decision the user must make:
- (A) Full historical backfill — recommended; ~30-50K v2 rows; full change-history queryability
- (B) Keep v1 alive for individuals/families; only drop change_log; partial storage win
- (C) Archive historical rows to R2; full storage win but slow history queries

The session is designed to ASK at Phase 158-1 (after the v1 baseline query), but if the user wants to pre-decide, that shortens the session. Default unless user pre-states: defer to in-session decision after seeing Albert Fox's actual change-history shape.
