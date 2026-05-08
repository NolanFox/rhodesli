-- Rhodesli Migration: GEDCOM Mirror Efficient Redesign (PRD-063 §6 Step 2)
--
-- Session 156 — Track B4
-- Date: 2026-05-08
--
-- Creates the v2 schema described in PRD-063 §4. Purely ADDITIVE: v1 tables
-- (gedcom_individuals, gedcom_families, gedcom_change_log) remain untouched
-- and authoritative for production reads through Sessions 156-157.
--
-- Cutover to v2 reads happens in Session 158, after dual-read confidence
-- pass in Session 157. v1 tables are dropped only after a 7-day cooling-off
-- per PRD-063 §6 Step 6.
--
-- §3 functional requirements satisfied: every read path will be backed by
-- a smaller (~22K vs 196K rows) canonical table with payload_hash UNIQUE
-- as the dedup ledger. See PRD-063 §4.1, §4.2, §4.4.
--
-- Mechanism mapping (PRD-063 §4):
--   §4.1 Hash-based dedup at INSERT --> payload_hash UNIQUE constraint below
--   §4.2 Single canonical row per gedcom_id + R2 versioned archive --> v2 tables
--   §4.4 Per-import change manifest --> gedcom_change_manifest below
--   §4.5 Drop unused indexes --> v2 includes only essential indexes per PRD
--
-- Rollback: DROP TABLE IF EXISTS gedcom_individuals_v2, gedcom_families_v2,
--          gedcom_change_manifest CASCADE;

-- ============================================================
-- Table: gedcom_individuals_v2
-- Single canonical row per gedcom_id (collapses 196K v1 rows into ~22K).
-- payload_hash UNIQUE enables INSERT-time dedup across re-imports.
-- first_seen_version / last_seen_version replace per-row versioning.
-- raw_record_json + root_json + raw_text dropped per PRD-063 §4.3 (archived
-- on R2 instead).
-- ============================================================
CREATE TABLE IF NOT EXISTS gedcom_individuals_v2 (
    id BIGSERIAL PRIMARY KEY,
    gedcom_id TEXT NOT NULL,
    name TEXT,
    given_name TEXT,
    surname TEXT,
    gender TEXT,
    birth_date TEXT,
    birth_place TEXT,
    death_date TEXT,
    death_place TEXT,
    -- Structured JSON payloads kept (parsed, not raw GEDCOM text):
    names_json JSONB DEFAULT '[]'::jsonb,
    events_json JSONB DEFAULT '[]'::jsonb,
    family_as_spouse_json JSONB DEFAULT '[]'::jsonb,
    family_as_child_json JSONB DEFAULT '[]'::jsonb,
    notes_json JSONB DEFAULT '[]'::jsonb,
    citations_json JSONB DEFAULT '[]'::jsonb,
    -- Dedup + versioning ledger:
    payload_hash TEXT NOT NULL,
    first_seen_version INTEGER NOT NULL,
    last_seen_version INTEGER NOT NULL,
    -- Provenance:
    community_id TEXT NOT NULL DEFAULT 'rhodesli',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Constraints:
    CONSTRAINT uq_gedcom_individuals_v2_payload_hash UNIQUE (payload_hash)
);

CREATE INDEX IF NOT EXISTS idx_gedcom_individuals_v2_gedcom_id
    ON gedcom_individuals_v2 (gedcom_id);

CREATE INDEX IF NOT EXISTS idx_gedcom_individuals_v2_surname
    ON gedcom_individuals_v2 (surname);

COMMENT ON TABLE gedcom_individuals_v2 IS
    'PRD-063 §4.2: canonical individual rows. One row per (gedcom_id, payload_hash). '
    'Replaces the 196K-row gedcom_individuals v1 table. v1 remains for backfill '
    'reconciliation through Session 157.';
COMMENT ON COLUMN gedcom_individuals_v2.payload_hash IS
    'SHA256 of canonical JSON of identifying fields. UNIQUE — enables INSERT-time '
    'dedup across re-imports. PRD-063 §4.1.';
COMMENT ON COLUMN gedcom_individuals_v2.first_seen_version IS
    'Minimum gedcom_versions.version_number where this payload_hash first appeared.';
COMMENT ON COLUMN gedcom_individuals_v2.last_seen_version IS
    'Maximum gedcom_versions.version_number where this payload_hash last appeared.';

-- ============================================================
-- Table: gedcom_families_v2
-- Single canonical row per family_gedcom_id. Same structure as v1
-- gedcom_families minus raw_record_json, plus payload_hash UNIQUE.
-- ============================================================
CREATE TABLE IF NOT EXISTS gedcom_families_v2 (
    id BIGSERIAL PRIMARY KEY,
    family_gedcom_id TEXT NOT NULL,
    husband_xref TEXT,
    wife_xref TEXT,
    children_xrefs_json JSONB DEFAULT '[]'::jsonb,
    marriage_event_json JSONB DEFAULT '{}'::jsonb,
    events_json JSONB DEFAULT '[]'::jsonb,
    notes_json JSONB DEFAULT '[]'::jsonb,
    citations_json JSONB DEFAULT '[]'::jsonb,
    -- Dedup + versioning ledger:
    payload_hash TEXT NOT NULL,
    first_seen_version INTEGER NOT NULL,
    last_seen_version INTEGER NOT NULL,
    -- Provenance:
    community_id TEXT NOT NULL DEFAULT 'rhodesli',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Constraints:
    CONSTRAINT uq_gedcom_families_v2_payload_hash UNIQUE (payload_hash)
);

CREATE INDEX IF NOT EXISTS idx_gedcom_families_v2_family_gedcom_id
    ON gedcom_families_v2 (family_gedcom_id);

COMMENT ON TABLE gedcom_families_v2 IS
    'PRD-063 §4.2: canonical family rows. payload_hash UNIQUE enables dedup. '
    'Replaces the 33K-row gedcom_families v1 table.';

-- ============================================================
-- Table: gedcom_change_manifest
-- Replaces 1.65M-row gedcom_change_log with ONE row per import. Per PRD-063
-- §4.4: a per-version summary blob captures everything we need (counts of
-- added/changed/removed individuals + families) for the genealogy UX use
-- case "what changed for this family between versions" without the per-row
-- explosion.
-- ============================================================
CREATE TABLE IF NOT EXISTS gedcom_change_manifest (
    id BIGSERIAL PRIMARY KEY,
    version_number INTEGER NOT NULL,
    community_id TEXT NOT NULL DEFAULT 'rhodesli',
    imported_at TIMESTAMPTZ NOT NULL,
    -- Summary metadata: counts + per-entity-type rollups
    -- Example structure:
    --   { "individuals": {"added": 12, "modified": 87, "removed": 0, "unchanged": 21899},
    --     "families":    {"added": 3,  "modified": 14, "removed": 0, "unchanged": 33307},
    --     "by_surname":  {"Fox": {"added": 2, "modified": 1}, ...} }
    summary_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Source provenance for round-tripping with R2 archive:
    source_file TEXT,
    source_hash TEXT,
    -- Provenance:
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Constraints:
    CONSTRAINT uq_gedcom_change_manifest_version
        UNIQUE (community_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_gedcom_change_manifest_version_number
    ON gedcom_change_manifest (version_number);

COMMENT ON TABLE gedcom_change_manifest IS
    'PRD-063 §4.4: one row per GEDCOM import. Replaces the 1.65M-row '
    'gedcom_change_log table. summary_jsonb holds per-entity-type and '
    'per-surname change counts for the "what changed in this family" UX.';

-- ============================================================
-- Provenance assertion: surface the v2 tables in pg_class
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE 'gedcom_individuals_v2 created: %', to_regclass('public.gedcom_individuals_v2');
    RAISE NOTICE 'gedcom_families_v2 created: %',    to_regclass('public.gedcom_families_v2');
    RAISE NOTICE 'gedcom_change_manifest created: %', to_regclass('public.gedcom_change_manifest');
END $$;
