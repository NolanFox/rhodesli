-- Session 162 Phase 1a — Replace current_gedcom_relationships view
--
-- The view's WHERE clause "is_current = true OR is_current IS NULL"
-- defeats the partial index idx_gedcom_relationships_current
-- WHERE (is_current = true). The OR ... IS NULL predicate forces a seq
-- scan over all 872,738 rows instead of an index scan over the 140,796
-- current rows.
--
-- Pre-session diagnosis confirmed:
--   - 0 NULL rows on gedcom_relationships.is_current
--   - 731,942 false + 140,796 true (the defensive IS NULL clause was over-engineering)
--   - 348,055 historical view calls × 754 ms mean = 73.9% of all DB disk reads
--
-- CREATE OR REPLACE VIEW takes no exclusive lock on the underlying table;
-- it's effectively metadata-only at the catalog level. lock_timeout '5s'
-- is more than enough; statement_timeout '15s' bounds in case of catalog
-- contention.
--
-- Rollback: see scripts/session162a_rollback_view.sql

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '15s';

CREATE OR REPLACE VIEW current_gedcom_relationships AS
 SELECT id, individual_gedcom_id, related_gedcom_id, relationship_type,
        family_gedcom_id, created_at, version_id, is_current, edge_key,
        relationship_payload, payload_hash, superseded_by
   FROM gedcom_relationships
  WHERE is_current = true;

COMMIT;
