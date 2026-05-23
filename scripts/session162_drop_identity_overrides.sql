-- Session 162 Phase 3 — DROP identity_overrides
--
-- Preconditions verified in Phase 2 (see session-162-identity-overrides-investigation.md):
--   - 0 live rows
--   - 0 external dependents (pg_depend deptype != 'i')
--   - All active query callers in scripts/* removed
--   - migrate_to_supabase.py archived
--   - R2 snapshot at r2://rhodesli-photos/backups/session162/identity_overrides_snapshot.json.gz
--
-- Rollback: see scripts/session162_rollback_identity_overrides.sql
-- (recreates table + 2 indexes + RLS — Codex P1.5 caught the missing RLS line).

BEGIN;
SET LOCAL lock_timeout = '30s';
SET LOCAL statement_timeout = '60s';

DROP TABLE IF EXISTS identity_overrides;

COMMIT;
