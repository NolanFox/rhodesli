# Session 158b — PRD-063 Day 3 Continuation: redesign Phase 158-2 + cutover

**Mode**: implementation
**Predecessor**: Session 158 (`docs/assessments/session-158-assessment.md`, commits `75dc10e0..dd1f7f59`)
**Successor**: TBD — likely a stabilization/UAT-only session if 158b finishes clean
**Critical deadline**: 2026-05-29 — Supabase free-tier 1.1 GB ceiling. Re-confirm via `date -u`.

## Why this session exists

Session 158 made it through Phase 158-1 (change-history reality check) but stalled on Phase 158-2 (historical backfill) due to Supabase pooler instability. The cutover gates exist for a reason: every phase from 158-3 (backups) through 158-9 (final verify) is gated on 158-2 succeeding.

**The user's central requirement is unchanged**: "I want to maintain some sense of GEDCOM change over time." Session 158-1 proved the gap is real (96.3% of v1 individuals have a 2-state history). The strategy decision was already made: **Option A — full historical backfill into v2**.

158b's job is to land Option A safely, then complete the cutover.

## What 158 shipped that 158b builds on

- **Phase 158-0** ✅ (`75dc10e0`): carry verification — v2 row counts intact, R2 archive readable
- **Phase 158-1** ✅ (`35c9dad6`): change-history reality check + Option A decision via AskUserQuestion
- **Codex 157b audit** ✅ (`ddfbdf35`): 0 P0, 2 P1, 3 P2, 2 P3
- **Dual-read helper P1.1 + P1.2 fixes** ✅ (`8bdc497a`): ordered v2 reads + narrow exception handling + `get_individual_history()` helper + 10 new tests (23 total dual-read tests pass)
- **Phase 158-2 WIP scripts** ⚠️ (`dd1f7f59`): both have known issues (see below)

## What 158 deferred

| Phase | Status |
|---|---|
| 158-2 historical backfill | DEFERRED — pooler unstable + REST script memory bug |
| 158-3 pre-flight backups | DEFERRED — gated on 158-2 |
| 158-4 cutover RENAME + view + bulk-loader rewire | DEFERRED |
| 158-5 wait + sustained validation | DEFERRED |
| 158-6 DROP v1 + VACUUM FULL | DEFERRED |
| 158-7 post-cutover query timing + Chrome MCP browser verify | DEFERRED |
| 158-8 Track E GEDCOM upload UAT | DEFERRED |
| 158-9 final verification | DEFERRED |

## Setup

```bash
echo "158b" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
bash scripts/harness-check.sh
make test-fast                            # baseline — must be green (4259 expected)
git log origin/main..HEAD                 # MUST be empty
git pull origin main
git status --short
date -u                                   # confirm date for deadline math
```

## FIRST ACTION — Re-run Phase 158-0 carry verification + pooler health probe

### A. Re-run Phase 158-0 carry verification (10 min)

```bash
PYTHONPATH=. python scripts/session158_phase0_verify.py
```

This re-validates: v2 row counts unchanged from 158 end (21,998 / 6,741 / 9), v1 still alive (196,645 / 33,324), Harry Fox + Belle Isle anchors intact, R2 archive at `gedcom-version-snapshots/2026-05-08-session-156/` readable. Any drift = a concurrent genealogy session ran between 158 and 158b — investigate before proceeding to writes.

Save output to `docs/feedback/session-158b-carry-verify.md`.

### A.5 Verify Codex 158 final-pass hardening landed cleanly (CRITICAL)

Session 158 closeout shipped commit `6aa87fc7` ("Codex final-pass P1 + P2 + AD-245 + /session-review auto-fixes") which addressed the central change-history-helper bug surfaced in self-review C-0: `INDIVIDUAL_HISTORY_FIELDS` now includes the 6 JSONB columns (`names_json`, `events_json`, `family_as_spouse_json`, `family_as_child_json`, `notes_json`, `citations_json`). This fix MUST be in place before Phase 158b-2 executes, otherwise `get_individual_history()` returns N rows that look identical (since per Phase 158-1 the actual change between distinct payload_hash states lives in JSONB).

Verify the fix is on `main`:

```bash
PYTHONPATH=. python -c "
from app.gedcom_dual_read import INDIVIDUAL_HISTORY_FIELDS
for f in ['names_json', 'events_json', 'family_as_spouse_json', 'family_as_child_json', 'notes_json', 'citations_json']:
    assert f in INDIVIDUAL_HISTORY_FIELDS, f
print('OK — all 6 JSONB fields present')
"
make test-fast    # 25 dual-read tests pass (was 23, +2 new from final-pass)
```

If either check fails, STOP — the fix was lost in a merge somewhere; re-apply from `git show 6aa87fc7` before continuing.

### B. Pooler health probe

Before touching the heavy scripts, verify the pooler is healthy today:

```bash
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
        cur.execute('SELECT id, version_number FROM gedcom_versions')
        rows = cur.fetchall()
        cur.execute('SELECT count(*) FROM gedcom_individuals')
        cnt = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(f'Trial {trial+1}: PASS — {len(rows)} versions, {cnt:,} individuals in {(time.time()-t0)*1000:.0f}ms')
    except Exception as e:
        print(f'Trial {trial+1}: FAIL — {e.__class__.__name__}: {e}')
"
```

**If 3/3 PASS**: pooler healthy today. Proceed with REDESIGN approach below (chunked-write psycopg2).
**If 0-2 PASS**: pooler still unhealthy. Switch to REST API for reads with chunked-write to v2.

## SECOND ACTION — Redesign Phase 158-2 backfill (chunked-write)

**Required pattern**: read AND write in batches; never accumulate full dataset in memory.

```python
# Pseudocode for the new script:
for v_id in version_ids + [None]:  # 9 versions + NULL chunk
    rows = read_chunk(v_id)        # ~22K rows per chunk
    aggregated = aggregate(rows)    # in-memory dict for THIS chunk only
    upsert_to_v2(aggregated)        # immediate write
    aggregated.clear()              # release memory
```

Across 10 chunks, each "in-memory dict" peaks at ~22K rows (~50 MB). Total wall-clock ~10 chunks × ~30s = ~5 min. The ON CONFLICT DO UPDATE handles cross-chunk first/last_seen merging naturally (each upsert sees the prior state via the existing v2 row's first_seen/last_seen).

Decision: write a NEW script `scripts/session158b_historical_backfill_chunked.py`. The existing 158 scripts stay as historical artifacts. Don't try to retrofit them.

Required validations after dry-run shows healthy chunk sizes:
1. Total `unique_payload_hashes` across all chunks should be ~64K individuals + ~13K families (matches Session 158 dry-run estimate)
2. Each chunk's NEW vs UPDATE ratio should be sane (chunks 1-7 should mostly be UPDATEs of existing v2 rows, chunks 8+ + NULL should add new historical states)
3. End-state v2 row count: ~77K total

After --execute: verify Albert Fox change history natively in v2:

```python
PYTHONPATH=. python -c "
from dotenv import load_dotenv; load_dotenv()
from app.gedcom_dual_read import get_individual_history
hist = get_individual_history('@I132123840707@')
print(f'Albert ({len(hist)} states):')
for h in hist:
    print(f'  v{h[\"first_seen_version\"]}-v{h[\"last_seen_version\"]}: hash={h[\"payload_hash\"][:8]}')
"
# Expected: 2 states (v-1/0 to v7 with hash fd1f05bd, v9-v9 with hash 1d77bf67)
```

If exactly 2 states show: PASS. If only 1 state: backfill is incomplete or the dual-read helper P1.1 ordering broke something — investigate.

## Phases 158b-3 through 158b-9

These all carry forward verbatim from `docs/prompts/session-158-prompt.md` (sections "Phase 158-3" through "Phase 158-9"). The prompt is unchanged for these — re-read it as the spec for each phase.

**ALSO consult** `docs/feedback/session-158-prompt-review.md` NOTE-1 through NOTE-9 — 9 lower-priority implementation refinements that the 158 implementer was supposed to consider at run time but never reached (because Phase 158-2 blocked first). Of particular relevance to 158b:
- **NOTE-1**: Albert Fox xref placeholder resolution — actual gedcom_id is `@I132123840707@` (resolved during 158 Phase 158-1; no need to re-resolve).
- **NOTE-2**: Phase 158-2 row count threshold — expected post-backfill v2 individual count is ~64K (per 158 dry-run); if dry-run shows >100K or <22K, STOP and investigate.
- **NOTE-3**: ON CONFLICT update logic — use `ON CONFLICT (payload_hash) DO UPDATE SET first_seen_version = LEAST(...), last_seen_version = GREATEST(...)`. The 158 `_bulk_upsert_psycopg2()` in `scripts/session158_historical_backfill_rest.py` already implements this correctly; reuse.
- **NOTE-6**: Codex audit timing — strongly consider running a Codex audit BETWEEN Phase 158b-4 (RENAME) and Phase 158b-6 (DROP) while still in the reversible state, in addition to the mandatory final-pass.
- **NOTE-7**: Bulk loader cache invalidation post-cutover — call `app.relationship_routes._invalidate_gedcom_cache()` (or equivalent) immediately after Phase 158b-4.1 view rewire.
- **NOTE-9**: gedcom_change_log signal preservation — OPTIONAL one-shot R2 archive of high-signal change_log rows before DROP. User has explicitly chosen full historical backfill (Option A), so per-cell change history beyond per-row is genuinely OPTIONAL — but cheap.

Specific changes for 158b:
- **Phase 158b-4.1 view creation**: the SQL view `current_gedcom_individuals_v2` and `current_gedcom_families_v2` definitions are unchanged. Code changes to bulk loaders are unchanged.
- **Phase 158b-7 browser verify**: USE CHROME MCP (per user choice in 158). No curl substitute.
- **Phase 158b-8 Track E**: still defers a v2-aware importer design decision (path A/B/C from the 158 prompt). User may want to defer Track E to 159 if budget tight.

## Non-negotiable rules (carried from 158)

1. **READ-ONLY on production browsers** (`.claude/rules/browser-read-only.md`).
2. **Codex CLI invocation**: `codex exec "<prompt>" </dev/null`. NEVER `--full-auto`.
3. Commit atomically per phase. /clear between phases at 300+ transcript lines.
4. AD entries for every ML/data decision. AD-244 already on main; AD-245 (chunked-write rationale), AD-246 (historical backfill strategy + dedup behavior), AD-247 (cutover sequence) likely.
5. **R2 reversibility re-test**: confirm 156 R2 archive still readable BEFORE any irreversible action.
6. **No DROP unless every gating phase passes** (including this session's redesigned 158b-2).

## Codex final-pass audit (mandatory, carried from 158)

After all 158b phases complete: run a Codex final-pass audit on the 158 + 158b commits combined. The cutover is high-stakes; an independent fresh-context audit catches anything we missed. Save to `docs/feedback/session-158b-codex-final-pass.md`.

## Stop-and-roll-to-159 conditions

| Trigger | Stop after | Rolled to 159 |
|---|---|---|
| Pooler probe fails 0-2/3 AND REST chunked-write also fails | 158b-2 | redesign with longer cooldown OR escalate to Supabase support |
| Historical backfill row count off by >10% from estimate | 158b-2 | investigate dedup correctness |
| Pre-flight backups fail | 158b-3 | R2 archive repair |
| Cutover smoke fails | 158b-4 (rollback executed) | new dual-read coverage needed |
| Wait period surfaces errors | 158b-5 (rollback executed) | new design needed |
| VACUUM FULL exceeds 30min OR DB size doesn't drop | 158b-7 | investigate before next cutover attempt |
| Track E v2-aware importer design non-trivial | 158b-7 | Track E to 159 (acceptable) |

## Closeout (mandatory 12-step harness)

Per `.claude/rules/session-defaults.md`:

1. Assessment: `docs/assessments/session-158b-assessment.md` with full AI Tool Usage section + irreversibility gates table
2. CHANGELOG: bump to v0.99.76 (or v1.0.0 if cutover warrants — propose to user)
3. ROADMAP + SESSION_HISTORY: update both
4. BACKLOG: close items
   - PRD-063-DAY-3-IMPL → CLOSED
   - HISTORICAL-BACKFILL-REDESIGN-001 → CLOSED
   - GEDCOM-V2-OTHER-TABLES → DECISION applied
   - GEDCOM-UAT-156 → CLOSED (or rolled to 159 if Track E didn't complete)
5. `git push origin main`
6. **Chrome MCP browser verify** the canonical 6 pages + GEDCOM-aware pages
7. `git log origin/main..HEAD` empty
8. `git status --short` clean
9. `bash scripts/harness-check.sh` exit 0
10. `bash scripts/backup-memory.sh`
11. Run `/session-review` skill on 158b itself
12. Codex final-pass audit on combined 158 + 158b commits — **MANDATORY this session**.
