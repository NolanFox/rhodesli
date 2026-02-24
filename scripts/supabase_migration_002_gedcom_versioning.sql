-- Rhodesli Supabase Migration 002: GEDCOM Temporal Versioning
-- AD-163: Track GEDCOM import versions, field-level changes, re-enrichment queue
-- Run this in the Supabase SQL Editor.
--
-- Purpose: When Nolan re-imports a GEDCOM after updating Ancestry,
-- the system intelligently merges changes without losing history.
-- Old data is never deleted, only superseded. The app always reads
-- "current" state via views.

-- ============================================================
-- Table 1: gedcom_versions
-- Each GEDCOM import creates a new version entry.
-- ============================================================
CREATE TABLE IF NOT EXISTS gedcom_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_number INTEGER NOT NULL,
    community_id TEXT NOT NULL DEFAULT 'rhodesli',
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    imported_by TEXT DEFAULT 'admin',
    source_file TEXT,
    source_hash TEXT,                          -- SHA256 of the GEDCOM file
    individual_count INTEGER DEFAULT 0,
    family_count INTEGER DEFAULT 0,
    summary JSONB DEFAULT '{}'::jsonb,         -- {added: N, modified: N, removed: N, unchanged: N}
    notes TEXT,
    UNIQUE(community_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_gedcom_versions_community
    ON gedcom_versions(community_id, version_number DESC);

-- ============================================================
-- Alter existing tables: add version columns
-- ============================================================

-- gedcom_individuals: add version tracking
ALTER TABLE gedcom_individuals
    ADD COLUMN IF NOT EXISTS version_id UUID REFERENCES gedcom_versions(id),
    ADD COLUMN IF NOT EXISTS superseded_by UUID,
    ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_gedcom_individuals_current
    ON gedcom_individuals(is_current) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_gedcom_individuals_version
    ON gedcom_individuals(version_id);

-- gedcom_events: add version tracking
ALTER TABLE gedcom_events
    ADD COLUMN IF NOT EXISTS version_id UUID REFERENCES gedcom_versions(id),
    ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_gedcom_events_current
    ON gedcom_events(is_current) WHERE is_current = TRUE;

-- gedcom_relationships: add version tracking
ALTER TABLE gedcom_relationships
    ADD COLUMN IF NOT EXISTS version_id UUID REFERENCES gedcom_versions(id),
    ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_gedcom_relationships_current
    ON gedcom_relationships(is_current) WHERE is_current = TRUE;

-- ============================================================
-- Table 2: gedcom_change_log
-- Field-level change tracking between versions.
-- ============================================================
CREATE TABLE IF NOT EXISTS gedcom_change_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID NOT NULL REFERENCES gedcom_versions(id),
    change_type TEXT NOT NULL,          -- 'added', 'modified', 'removed'
    entity_type TEXT NOT NULL,          -- 'individual', 'event', 'relationship'
    xref_id TEXT NOT NULL,              -- GEDCOM XREF identifier
    field_name TEXT,                    -- which field changed (NULL for adds/removes)
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gedcom_change_log_version
    ON gedcom_change_log(version_id);
CREATE INDEX IF NOT EXISTS idx_gedcom_change_log_xref
    ON gedcom_change_log(xref_id);

-- ============================================================
-- Table 3: gedcom_enrichment_queue
-- Photos that need re-enrichment due to GEDCOM changes.
-- Gatekeeper pattern: queued for admin review, not auto-run.
-- ============================================================
CREATE TABLE IF NOT EXISTS gedcom_enrichment_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id TEXT NOT NULL,
    identity_id TEXT NOT NULL,
    gedcom_id TEXT NOT NULL,
    trigger TEXT NOT NULL DEFAULT 'gedcom_update',  -- gedcom_update, model_upgrade, manual_rerun
    reason TEXT,                                     -- human-readable reason
    version_id UUID REFERENCES gedcom_versions(id),
    status TEXT NOT NULL DEFAULT 'pending',           -- pending, completed, skipped
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_enrichment_queue_status
    ON gedcom_enrichment_queue(status) WHERE status = 'pending';

-- ============================================================
-- Views: Always show current state
-- ============================================================

-- All Gemini queries, GEDCOM searches, and enrichment pipeline
-- should read from these views, never the raw tables.
CREATE OR REPLACE VIEW current_gedcom_individuals AS
SELECT * FROM gedcom_individuals
WHERE is_current = TRUE OR is_current IS NULL;

CREATE OR REPLACE VIEW current_gedcom_events AS
SELECT * FROM gedcom_events
WHERE is_current = TRUE OR is_current IS NULL;

CREATE OR REPLACE VIEW current_gedcom_relationships AS
SELECT * FROM gedcom_relationships
WHERE is_current = TRUE OR is_current IS NULL;

-- ============================================================
-- Backfill: Mark all existing rows as version NULL, is_current=TRUE
-- This is safe to run multiple times.
-- ============================================================
UPDATE gedcom_individuals SET is_current = TRUE WHERE is_current IS NULL;
UPDATE gedcom_events SET is_current = TRUE WHERE is_current IS NULL;
UPDATE gedcom_relationships SET is_current = TRUE WHERE is_current IS NULL;

-- ============================================================
-- RLS
-- ============================================================
ALTER TABLE gedcom_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE gedcom_change_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE gedcom_enrichment_queue ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Verification query
-- ============================================================
-- SELECT
--     (SELECT COUNT(*) FROM gedcom_versions) as versions,
--     (SELECT COUNT(*) FROM gedcom_individuals WHERE is_current = TRUE) as current_individuals,
--     (SELECT COUNT(*) FROM gedcom_change_log) as change_log_entries,
--     (SELECT COUNT(*) FROM gedcom_enrichment_queue WHERE status = 'pending') as pending_enrichments;
