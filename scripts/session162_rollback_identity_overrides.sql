-- Session 162 Phase 3 rollback — recreate identity_overrides
-- (only the structure; rows from R2 snapshot if needed, but the table was empty).
--
-- Re-applies the original Session 59C migration001 lines 14-29 + 84 (RLS).

BEGIN;
SET LOCAL lock_timeout = '30s';
SET LOCAL statement_timeout = '60s';

CREATE TABLE IF NOT EXISTS identity_overrides (
    identity_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    name TEXT,
    merged_into TEXT,
    data JSONB NOT NULL,
    -- Codex post-exec P1-1: original supabase_migration_001.sql had DEFAULT 'admin' on updated_by
    updated_by TEXT DEFAULT 'admin',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_identity_overrides_state
    ON identity_overrides(state);
CREATE INDEX IF NOT EXISTS idx_identity_overrides_merged
    ON identity_overrides(merged_into) WHERE merged_into IS NOT NULL;

-- Codex P1.5 — restore RLS that was missing from the original v1 rollback plan
ALTER TABLE identity_overrides ENABLE ROW LEVEL SECURITY;

COMMIT;
