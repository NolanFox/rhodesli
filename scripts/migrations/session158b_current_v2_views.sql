-- Session 158b Phase 158-4.1 — current_gedcom_*_v2 views
--
-- Provides stable "current state" reads from the deduped v2 tables.
-- After Phase 158-2 completes, v2 contains both current AND historical
-- payload_hashes. The bulk loaders (request path) need only the current
-- state per gedcom_id / family_gedcom_id.
--
-- Tiebreaker order for DISTINCT ON:
--   1. last_seen_version DESC — most-recently-current state wins
--   2. first_seen_version DESC — among ties on last_seen, newer-introduced
--   3. payload_hash — deterministic final tiebreak
--
-- Sanity check after creation:
--   SELECT COUNT(*) FROM current_gedcom_individuals_v2;
--   SELECT COUNT(DISTINCT gedcom_id) FROM gedcom_individuals_v2;
--   These two MUST be equal. If they're not, the tiebreaker isn't doing
--   what we expect — investigate before relying on the view.
--
-- Apply via psycopg2 (or via Supabase SQL editor in the dashboard if
-- pooler is degraded today).

CREATE OR REPLACE VIEW current_gedcom_individuals_v2 AS
SELECT DISTINCT ON (gedcom_id) *
FROM gedcom_individuals_v2
ORDER BY gedcom_id, last_seen_version DESC, first_seen_version DESC, payload_hash;

CREATE OR REPLACE VIEW current_gedcom_families_v2 AS
SELECT DISTINCT ON (family_gedcom_id) *
FROM gedcom_families_v2
ORDER BY family_gedcom_id, last_seen_version DESC, first_seen_version DESC, payload_hash;

-- Read-only access for service role
GRANT SELECT ON current_gedcom_individuals_v2 TO anon, authenticated, service_role;
GRANT SELECT ON current_gedcom_families_v2 TO anon, authenticated, service_role;
