-- Rhodesli Supabase Migration 003: Rich GEDCOM Mirror
-- Session 98: preserve full GEDCOM lineage instead of only thin individual rows

-- ============================================================
-- gedcom_versions: richer import metadata
-- ============================================================
ALTER TABLE gedcom_versions
    ADD COLUMN IF NOT EXISTS source_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS media_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS record_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS source_manifest JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'applied';

-- ============================================================
-- gedcom_individuals: allow versioned duplicates + rich payload mirror
-- ============================================================
ALTER TABLE gedcom_individuals
    DROP CONSTRAINT IF EXISTS gedcom_individuals_gedcom_id_key;

ALTER TABLE gedcom_individuals
    ADD COLUMN IF NOT EXISTS birth_event_json JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS death_event_json JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS events_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS family_as_spouse_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS family_as_child_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS names_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS notes_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS citations_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS media_refs_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS custom_tags_json JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS raw_record_key TEXT,
    ADD COLUMN IF NOT EXISTS raw_record_json JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS record_hash TEXT,
    ADD COLUMN IF NOT EXISTS payload_hash TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_gedcom_individuals_current
    ON gedcom_individuals(gedcom_id)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_gedcom_individuals_payload_hash
    ON gedcom_individuals(payload_hash);

-- ============================================================
-- gedcom_events: stable event identity + full event payload
-- ============================================================
ALTER TABLE gedcom_events
    ADD COLUMN IF NOT EXISTS event_key TEXT,
    ADD COLUMN IF NOT EXISTS value TEXT,
    ADD COLUMN IF NOT EXISTS type_label TEXT,
    ADD COLUMN IF NOT EXISTS notes_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS citations_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS media_refs_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS raw_tag TEXT,
    ADD COLUMN IF NOT EXISTS raw_node_json JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS payload_hash TEXT,
    ADD COLUMN IF NOT EXISTS superseded_by UUID;

CREATE UNIQUE INDEX IF NOT EXISTS uq_gedcom_events_current
    ON gedcom_events(event_key)
    WHERE is_current = TRUE AND event_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_gedcom_events_payload_hash
    ON gedcom_events(payload_hash);

-- ============================================================
-- gedcom_relationships: stable edge identity + payload mirror
-- ============================================================
ALTER TABLE gedcom_relationships
    ADD COLUMN IF NOT EXISTS edge_key TEXT,
    ADD COLUMN IF NOT EXISTS relationship_payload JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS payload_hash TEXT,
    ADD COLUMN IF NOT EXISTS superseded_by UUID;

CREATE UNIQUE INDEX IF NOT EXISTS uq_gedcom_relationships_current
    ON gedcom_relationships(edge_key)
    WHERE is_current = TRUE AND edge_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_gedcom_relationships_payload_hash
    ON gedcom_relationships(payload_hash);

-- ============================================================
-- New Table: gedcom_families
-- ============================================================
CREATE TABLE IF NOT EXISTS gedcom_families (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_gedcom_id TEXT NOT NULL,
    husband_xref TEXT,
    wife_xref TEXT,
    children_xrefs_json JSONB DEFAULT '[]'::jsonb,
    marriage_event_json JSONB DEFAULT '{}'::jsonb,
    events_json JSONB DEFAULT '[]'::jsonb,
    notes_json JSONB DEFAULT '[]'::jsonb,
    citations_json JSONB DEFAULT '[]'::jsonb,
    media_refs_json JSONB DEFAULT '[]'::jsonb,
    custom_tags_json JSONB DEFAULT '{}'::jsonb,
    raw_record_key TEXT,
    raw_record_json JSONB DEFAULT '{}'::jsonb,
    record_hash TEXT,
    payload_hash TEXT,
    version_id UUID REFERENCES gedcom_versions(id),
    superseded_by UUID,
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_gedcom_families_current
    ON gedcom_families(family_gedcom_id)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_gedcom_families_version
    ON gedcom_families(version_id);

-- ============================================================
-- New Table: gedcom_sources
-- ============================================================
CREATE TABLE IF NOT EXISTS gedcom_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_xref TEXT NOT NULL,
    title TEXT,
    author TEXT,
    publication TEXT,
    repository_xref TEXT,
    notes_json JSONB DEFAULT '[]'::jsonb,
    urls_json JSONB DEFAULT '[]'::jsonb,
    raw_record_key TEXT,
    raw_record_json JSONB DEFAULT '{}'::jsonb,
    record_hash TEXT,
    payload_hash TEXT,
    version_id UUID REFERENCES gedcom_versions(id),
    superseded_by UUID,
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_gedcom_sources_current
    ON gedcom_sources(source_xref)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_gedcom_sources_version
    ON gedcom_sources(version_id);

-- ============================================================
-- New Table: gedcom_media_objects
-- ============================================================
CREATE TABLE IF NOT EXISTS gedcom_media_objects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    media_xref TEXT NOT NULL,
    file TEXT,
    form TEXT,
    title TEXT,
    media_type TEXT,
    notes_json JSONB DEFAULT '[]'::jsonb,
    urls_json JSONB DEFAULT '[]'::jsonb,
    raw_record_key TEXT,
    raw_record_json JSONB DEFAULT '{}'::jsonb,
    record_hash TEXT,
    payload_hash TEXT,
    version_id UUID REFERENCES gedcom_versions(id),
    superseded_by UUID,
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_gedcom_media_current
    ON gedcom_media_objects(media_xref)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_gedcom_media_version
    ON gedcom_media_objects(version_id);

-- ============================================================
-- New Table: gedcom_records
-- ============================================================
CREATE TABLE IF NOT EXISTS gedcom_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_key TEXT NOT NULL,
    record_type TEXT NOT NULL,
    xref_id TEXT,
    record_hash TEXT NOT NULL,
    payload_hash TEXT,
    raw_text TEXT NOT NULL,
    root_json JSONB DEFAULT '{}'::jsonb,
    version_id UUID REFERENCES gedcom_versions(id),
    superseded_by UUID,
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_gedcom_records_current
    ON gedcom_records(record_key)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_gedcom_records_version
    ON gedcom_records(version_id);

CREATE INDEX IF NOT EXISTS idx_gedcom_records_type
    ON gedcom_records(record_type);

-- ============================================================
-- New Table: gedcom_entity_redirects
-- ============================================================
CREATE TABLE IF NOT EXISTS gedcom_entity_redirects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id TEXT NOT NULL DEFAULT 'rhodesli',
    entity_type TEXT NOT NULL,
    old_key TEXT NOT NULL,
    new_key TEXT NOT NULL,
    version_id UUID REFERENCES gedcom_versions(id),
    redirect_type TEXT NOT NULL DEFAULT 'rekey_redirect',
    match_score DOUBLE PRECISION,
    match_basis_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_gedcom_entity_redirects_old_key
    ON gedcom_entity_redirects(community_id, entity_type, old_key);

CREATE INDEX IF NOT EXISTS idx_gedcom_entity_redirects_new_key
    ON gedcom_entity_redirects(community_id, entity_type, new_key);

CREATE INDEX IF NOT EXISTS idx_gedcom_entity_redirects_version
    ON gedcom_entity_redirects(version_id);

-- ============================================================
-- Current-state views
-- ============================================================
CREATE OR REPLACE VIEW current_gedcom_individuals AS
SELECT * FROM gedcom_individuals
WHERE is_current = TRUE OR is_current IS NULL;

CREATE OR REPLACE VIEW current_gedcom_events AS
SELECT * FROM gedcom_events
WHERE is_current = TRUE OR is_current IS NULL;

CREATE OR REPLACE VIEW current_gedcom_relationships AS
SELECT * FROM gedcom_relationships
WHERE is_current = TRUE OR is_current IS NULL;

CREATE OR REPLACE VIEW current_gedcom_families AS
SELECT * FROM gedcom_families
WHERE is_current = TRUE OR is_current IS NULL;

CREATE OR REPLACE VIEW current_gedcom_sources AS
SELECT * FROM gedcom_sources
WHERE is_current = TRUE OR is_current IS NULL;

CREATE OR REPLACE VIEW current_gedcom_media_objects AS
SELECT * FROM gedcom_media_objects
WHERE is_current = TRUE OR is_current IS NULL;

CREATE OR REPLACE VIEW current_gedcom_records AS
SELECT * FROM gedcom_records
WHERE is_current = TRUE OR is_current IS NULL;

CREATE OR REPLACE VIEW current_gedcom_entity_redirects AS
SELECT * FROM gedcom_entity_redirects;

-- ============================================================
-- Safe backfill defaults for legacy rows
-- ============================================================
UPDATE gedcom_individuals SET is_current = TRUE WHERE is_current IS NULL;
UPDATE gedcom_events SET is_current = TRUE WHERE is_current IS NULL;
UPDATE gedcom_relationships SET is_current = TRUE WHERE is_current IS NULL;
