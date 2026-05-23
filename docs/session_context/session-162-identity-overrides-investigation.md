# Session 162 Phase 2 — `identity_overrides` Investigation

**Captured**: 2026-05-23 UTC

## TL;DR

`identity_overrides` table has 0 live rows. Last meaningful write happened pre-Session-130 (2026-03-21). Since then it's been:
- Polled in tight loop by `data_integrity_report.py` and `data_integrity_audit.py` (18,158 reads in 165 days = 110/day)
- Stale-written by `scripts/migrate_to_supabase.py` (a Session 59C one-shot tool that nobody should re-run)
- Fully deprecated in app code (`app/supabase_data.py` has 3 no-op stubs)

Codex post-execution audit recommended the table is safe to DROP. This investigation phase confirms.

## Evidence

### pg_depend preflight
```
external dependents (deptype != 'i'): 0
- public.idx_identity_overrides_state (deptype=a, owned-by-table)
- public.idx_identity_overrides_merged (deptype=a, owned-by-table)
```
No views, no foreign keys, no other tables reference it. Safe to DROP.

### Code references (all updated this phase)

| File | Lines | Disposition |
|------|-------|-------------|
| `app/supabase_data.py` 118-120, 281-282, 1269-1270 | DEPRECATED stubs since Session 130 | KEEP (backwards-compat) |
| `app/main.py` 1834 | historical comment | KEEP (historical comment) |
| `scripts/supabase_migration_001.sql` 10-29, 84, 97 | original migration + RLS line | KEEP (historical) |
| `scripts/migrate_to_supabase.py` 70, 99, 245 | active WRITER (one-shot tool) | **ARCHIVED → `scripts/_archive/migrate_to_supabase_session59C.py`** |
| `scripts/data_integrity_report.py` 122, 165 | active reader | **PATCHED — table removed from query list; cross-check stubbed** |
| `scripts/data_integrity_audit.py` 22, 368-374 | active reader | **PATCHED — divergence check stubbed to no-op** |
| `tests/test_data_layer_invariants.py` (multiple) | structural tests that ENFORCE non-usage | KEEP (these tests are the safety net) |

### R2 snapshot

```
bucket: rhodesli-photos
key: backups/session162/identity_overrides_snapshot.json.gz
size: 465 bytes (gz) / 1,583 bytes (raw)
rows: 0
captured_at: 2026-05-23T03:04:56Z
```
Schema + indexes + 0 rows preserved. Recovery script if ever needed: replay `scripts/supabase_migration_001.sql` lines 10-29 (CREATE TABLE + 2 indexes), line 84 (`ENABLE ROW LEVEL SECURITY`), restore rows from R2 (empty).

### Why this table is safe to drop

- Zero live rows since Session 130 (~2 months)
- App code reads (`load_identity_overrides_from_supabase`) explicitly return `{}` since Session 130
- App code writes (`sync_identity_overrides`) explicitly return `None` since Session 130
- Tests in `test_data_layer_invariants.py` ENFORCE that production code does not query the table
- The only active query callers are periodic scripts not on the request path

## What changes in Phase 3 (DROP)

If user approves the PROCEED GATE:
1. `BEGIN; SET LOCAL lock_timeout='30s'; DROP TABLE IF EXISTS identity_overrides; COMMIT;`
2. Add `tests/test_session162_identity_overrides_dropped.py` (live-DB marker test + static grep test for new offenders)

## What changes if user declines

Phase 3 is deferred to a future session. Phase 2 cleanup is still net-positive:
- `migrate_to_supabase.py` no longer runnable (archived) — closes a footgun
- Integrity scripts no longer poll a dead table
- The table itself stays but is no-op for app reads/writes

The Disk IO win from Phase 1a stands either way; Phase 3 is incremental cleanup.

## Recommendation

**PROCEED with Phase 3 DROP.** Risk profile: extremely low (empty table, 0 dependents, snapshot in R2, all code paths patched).
