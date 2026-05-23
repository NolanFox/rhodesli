-- Session 162 Phase 1a rollback — restore the previous view definition.
-- Use only if the post-migration EXPLAIN does NOT show partial-index usage
-- after ANALYZE, OR if production /health drops to non-200 within 5 min.

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '15s';

CREATE OR REPLACE VIEW current_gedcom_relationships AS
 SELECT id, individual_gedcom_id, related_gedcom_id, relationship_type,
        family_gedcom_id, created_at, version_id, is_current, edge_key,
        relationship_payload, payload_hash, superseded_by
   FROM gedcom_relationships
  WHERE is_current = true OR is_current IS NULL;

COMMIT;
