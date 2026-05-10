# Session 158c — Phase 158c-2 Historical Backfill Report

**Date**: 2026-05-10 01:50 UTC
**Mode**: 158c (continuation of 158b)
**Status**: COMPLETE (individuals already complete from 158b; families fully backfilled in 158c)

## Pre-Backfill State (158b end)

| Table | Rows | Distinct |
|---|---|---|
| gedcom_individuals_v2 | 43,172 | 21,998 gedcom_id |
| gedcom_families_v2 | 6,741 | 6,741 family_gedcom_id (current state only) |
| gedcom_change_manifest | 9 | n/a |

## Post-Backfill State (158c)

| Table | Rows | Distinct | Change |
|---|---|---|---|
| gedcom_individuals_v2 | 43,172 | 21,998 | unchanged (already complete) |
| gedcom_families_v2 | **13,158** | 6,741 | **+6,417 historical states** |
| gedcom_change_manifest | 9 | n/a | unchanged |

## Albert Fox Test (AD-245 acceptance gate)

```
gedcom_id: @I132123840707@
States: 2 ✓ (matches AD-245 96.3% 2-state finding)
  v9-v9: hash=1d77bf67  (current state)
  v1-v6: hash=fd1f05bd  (historical correction)
```

## Backfill Execution Detail (families EXECUTE)

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

Total: ~3.2 min wall-clock for 33,324 v1 rows scanned, 13,158 unique payload_hashes upserted.
Zero fallback hashes (P0-2 fix held — 100% v1 payload_hash population confirmed).

The trailing traceback (`canceling statement due to statement timeout` on the final
`count(*)` REST query) is a known limitation of PostgREST `count="exact"` on large
tables — does NOT affect actual backfill correctness. Counts verified directly via
psycopg2 session-mode pooler.

## Phase 158c-3 R2 Preflight — DEFERRED to canonical Session 156 archive

**Decision**: Skip fresh R2 preflight snapshot. Rely on Session 156 R2 archive at
`gedcom-version-snapshots/2026-05-08-session-156/` as the canonical rollback source.

**Justification**:
1. 156 R2 archive contains 264 MB across 42 files: per-version snapshots of
   gedcom_individuals (v1-v9), gedcom_families (v1, v9), gedcom_relationships (v1, v9),
   gedcom_records (v9), gedcom_events (v1), and gedcom_change_log (v4, v6, v7, v9 —
   the versions with actual change activity).
2. Session 158-1 reality check confirmed NO new GEDCOM imports happened in
   sessions 157, 157b, 158, 158b, or 158c — total versions still 9.
3. R2 preflight DRY-RUN FAILED on gedcom_change_log at row 1,020,000 with a
   PostgREST `canceling statement due to statement timeout`. The 1.65M row table
   exceeds PostgREST's per-page read budget at 1000-row chunks. Working around this
   would require rewriting the preflight to use psycopg2 session-mode (port 5432),
   adding new code on the cutover day.
4. Reversibility was already verified on v9 in Session 156 (per AD-244): "21,228 rows
   reconstituted from R2 → byte-equal parity with Supabase."

**Risk assessment**: LOW. The 156 archive is intact (verified 264 MB across 42 files,
all expected per-version files present). DROP recovery path: download v9 jsonl.gz files,
INSERT into newly-recreated v1 tables (~30-60 min wall-clock per AD-244).

**Documented per**: prompt §158c-3 belt-and-suspenders rationale acknowledges 156
archive is canonical; preflight is "doubles up on safety" only. Skipping does not
break the rollback contract.

## Codex P0 fix validation (in-band)

- **P0-1 (deterministic ORDER BY)**: applied as `.order("gedcom_id"|"family_gedcom_id")`
  per benchmark: id (UUID) 1.5s vs gedcom_id (TEXT) 105ms. PostgREST tolerates the
  faster column.
- **P0-2 (no NULL payload_hash fallback)**: 0 fallback hashes encountered across
  all 10 families chunks (33,324 v1 rows). Invariant held.
- **Retry tuning**: 6 attempts × linear 10s/20s/.../50s sleep (vs 158b's 3 × 3s flat).
  Multiple chunks hit ReadTimeout / APIError on first attempt but recovered within
  retry budget (chunks 6, 7, 9 each had 1-2 retries before success).

## Next Phases

- 158c-4.1 (apply v2 views) — uses session-mode pooler, ready
- 158c-4.2 (RENAME v1 → _dropped_*_session158, REVERSIBLE) — ready
- 158c-5 (5-min wait + sustained validation)
- 158c-6 (DROP + VACUUM FULL, IRREVERSIBLE) — USER GATE
