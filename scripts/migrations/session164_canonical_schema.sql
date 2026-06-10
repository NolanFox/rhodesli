-- =====================================================================
-- Session 164 — Canonical GEDCOM schema (PRD-064 Option B-plus)
-- =====================================================================
-- DDL ONLY. This file is NOT applied automatically. It is applied by the
-- one-off migration script (session164_migrate_to_current_state.py) after a
-- verified R2 snapshot of the v2 tables.
--
-- Design (plan R1, Codex P0-5 / P1-5):
--   * Current-state ONLY — one row per entity, community-scoped composite PK.
--     The 2x state duplication of gedcom_individuals_v2 (267 MB / 43,172 rows)
--     is eliminated; canonical holds ~one v2 state (~135 MB).
--   * NO duplicated `payload` JSONB blob in the DB. The lossless full payload
--     lives only in R2 history artifacts. The typed columns are exactly what
--     the app reads today; `payload_hash` ties each DB row to its R2 payload.
--   * Composite (community_id, <natural_id>) keys so entities can't collide
--     across communities.
-- =====================================================================


-- ---------------------------------------------------------------------
-- gedcom_individuals — canonical current-state, one row per gedcom_id
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gedcom_individuals (
    community_id text NOT NULL DEFAULT 'rhodesli',
    gedcom_id    text NOT NULL,                 -- @I...@ xref
    name         text,
    given_name   text,
    surname      text,
    gender       text,
    birth_date   text,
    birth_place  text,
    death_date   text,
    death_place  text,
    names_json            jsonb DEFAULT '[]'::jsonb,
    events_json           jsonb DEFAULT '[]'::jsonb,
    family_as_spouse_json jsonb DEFAULT '[]'::jsonb,
    family_as_child_json  jsonb DEFAULT '[]'::jsonb,
    notes_json            jsonb DEFAULT '[]'::jsonb,
    citations_json        jsonb DEFAULT '[]'::jsonb,
    payload_hash   text NOT NULL,               -- canonical_payload_hash (THE hash); R2 payload key
    version_number integer NOT NULL,            -- version that last wrote this row
    updated_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (community_id, gedcom_id)        -- one row per entity, community-scoped
);

-- Fast SQL filters used by the app (surname search, xref lookup).
CREATE INDEX IF NOT EXISTS idx_gedcom_individuals_surname
    ON gedcom_individuals (community_id, surname);
CREATE INDEX IF NOT EXISTS idx_gedcom_individuals_gedcom_id
    ON gedcom_individuals (gedcom_id);


-- ---------------------------------------------------------------------
-- gedcom_families — canonical current-state, one row per family_gedcom_id
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gedcom_families (
    community_id     text NOT NULL DEFAULT 'rhodesli',
    family_gedcom_id text NOT NULL,             -- @F...@ xref
    husband_xref     text,
    wife_xref        text,
    children_xrefs_json jsonb DEFAULT '[]'::jsonb,
    marriage_event_json jsonb,
    events_json         jsonb DEFAULT '[]'::jsonb,
    notes_json          jsonb DEFAULT '[]'::jsonb,
    citations_json      jsonb DEFAULT '[]'::jsonb,
    payload_hash   text NOT NULL,
    version_number integer NOT NULL,
    updated_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (community_id, family_gedcom_id)
);

CREATE INDEX IF NOT EXISTS idx_gedcom_families_family_gedcom_id
    ON gedcom_families (family_gedcom_id);


-- ---------------------------------------------------------------------
-- gedcom_relationships — re-use existing table; add canonical columns.
-- ---------------------------------------------------------------------
-- These are additive + idempotent. The table is already current-only
-- (Session 163 pruned superseded rows: 140,796 rows, all is_current=true,
-- edge_key 1:1). community_id added for parity with the canonical tables.
ALTER TABLE gedcom_relationships
    ADD COLUMN IF NOT EXISTS community_id   text DEFAULT 'rhodesli',
    ADD COLUMN IF NOT EXISTS version_number integer;

-- NOTE: The DROP of the legacy versioning columns (is_current, version_id,
-- superseded_by) is performed by the migration SCRIPT after the canonical
-- backfill is verified — NOT here, so this DDL stays safe to run standalone
-- and idempotent. The migration script runs the equivalent of:
--     ALTER TABLE gedcom_relationships
--         DROP COLUMN IF EXISTS is_current,
--         DROP COLUMN IF EXISTS version_id,
--         DROP COLUMN IF EXISTS superseded_by;
-- (kept commented here for documentation only).

-- Composite community-scoped uniqueness on the relationship edge.
-- edge_key is already 1:1; scope it by community for parity.
CREATE UNIQUE INDEX IF NOT EXISTS uq_gedcom_relationships_community_edge
    ON gedcom_relationships (community_id, edge_key);


-- ---------------------------------------------------------------------
-- gedcom_versions — manifest; extend with artifact provenance.
-- ---------------------------------------------------------------------
-- All additive + idempotent. status='applied' rows reference live entity
-- rows; the atomic importer NEVER writes 'failed' rows (a failed import
-- rolls back to ZERO rows, including no version row). Historical 'failed'
-- rows from the old importer remain as audit metadata referencing nothing.
ALTER TABLE gedcom_versions
    ADD COLUMN IF NOT EXISTS raw_artifact_sha256      text,  -- sha256(raw.ged.gz compressed bytes); NULL for compensating
    ADD COLUMN IF NOT EXISTS snapshot_artifact_sha256 text,  -- sha256(snapshot.jsonl.gz compressed bytes)
    ADD COLUMN IF NOT EXISTS diff_artifact_sha256     text,  -- sha256(diff.json.gz compressed bytes)
    ADD COLUMN IF NOT EXISTS artifact_prefix          text,  -- R2 key prefix for this version's artifacts
    ADD COLUMN IF NOT EXISTS diff_summary             jsonb, -- {<type>:{added,modified,removed,ids:{...}}} (IDs only)
    ADD COLUMN IF NOT EXISTS artifact_format          text DEFAULT 'v1';  -- 'v1' (new) | 'legacy' (pre-Session-164)

-- One applied import per (community, source_hash). Re-importing an identical
-- GEDCOM is a no-op detected under the advisory lock; this index is the
-- structural backstop (Codex P1-1). Partial: only 'applied' rows are unique,
-- so historical 'failed' duplicates don't trip it.
CREATE UNIQUE INDEX IF NOT EXISTS uq_gedcom_versions_applied_source_hash
    ON gedcom_versions (community_id, source_hash)
    WHERE status = 'applied';
