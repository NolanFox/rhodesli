-- Session 162 Phase 1b rollback — drop NOT NULL constraint
-- Use only if a downstream caller surfaces a need to write NULL is_current values
-- (none expected; column had 0 NULLs at constraint-creation time).

BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';

ALTER TABLE gedcom_relationships ALTER COLUMN is_current DROP NOT NULL;

COMMIT;
