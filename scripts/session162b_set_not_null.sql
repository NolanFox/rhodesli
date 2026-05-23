-- Session 162 Phase 1b — Add NOT NULL constraint on gedcom_relationships.is_current
--
-- Structural prevention of NULL re-introduction that would re-defeat the
-- partial index after Phase 1a's view fix.
--
-- Phase 1a already replaced the view to filter by `is_current = true`, so
-- callers no longer rely on NULL semantics. Pre-session diagnosis and
-- Phase 1b preflight both confirm 0 NULL rows.
--
-- ALTER COLUMN SET NOT NULL takes an AccessExclusiveLock on the table for
-- the duration of the verification scan. On 872k rows + minor bloat we
-- expect 30-60s. lock_timeout='10s' aborts cleanly if app traffic is hot;
-- statement_timeout='60s' bounds the post-lock scan.
--
-- Rollback: see scripts/session162b_rollback_not_null.sql (drops the constraint)

BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';

-- Final safety gate inside the transaction
DO $$
DECLARE n bigint;
BEGIN
  SELECT COUNT(*) INTO n FROM gedcom_relationships WHERE is_current IS NULL;
  IF n > 0 THEN
    RAISE EXCEPTION 'gedcom_relationships has % NULL is_current rows; aborting', n;
  END IF;
END $$;

ALTER TABLE gedcom_relationships ALTER COLUMN is_current SET NOT NULL;

COMMIT;
