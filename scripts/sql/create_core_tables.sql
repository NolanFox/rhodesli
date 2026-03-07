-- Core tables for Rhodesli data model
-- Consolidates photos, identities, and photo_faces schemas
-- Reference: scripts/sql/001_photos_table.sql, 002_identities_table.sql, 003_photo_faces_table.sql
-- Created: Session 91 Track E (2026-03-07)
--
-- NOTE: These tables already exist in Supabase (created in Session 90b).
-- This file is canonical documentation of the schema for the Postgres read flip.

CREATE TABLE IF NOT EXISTS photos (
    photo_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    source TEXT,
    collection TEXT,
    source_url TEXT,
    upload_date TIMESTAMPTZ,
    width INTEGER,
    height INTEGER,
    face_count INTEGER DEFAULT 0,
    uploaded_by TEXT,
    community_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS identities (
    identity_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT,
    state TEXT NOT NULL DEFAULT 'INBOX',
    anchor_ids JSONB DEFAULT '[]',
    candidate_ids JSONB DEFAULT '[]',
    negative_ids JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    version_id INTEGER DEFAULT 1,
    merged_into UUID,
    community_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS photo_faces (
    face_id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL REFERENCES photos(photo_id),
    identity_id UUID REFERENCES identities(identity_id),
    bbox JSONB,
    det_score NUMERIC(6,4),
    quality NUMERIC(6,4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_photos_collection ON photos(collection);
CREATE INDEX IF NOT EXISTS idx_photos_community ON photos(community_id);
CREATE INDEX IF NOT EXISTS idx_identities_state ON identities(state);
CREATE INDEX IF NOT EXISTS idx_identities_merged_into ON identities(merged_into) WHERE merged_into IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_identities_community ON identities(community_id);
CREATE INDEX IF NOT EXISTS idx_photo_faces_photo_id ON photo_faces(photo_id);
CREATE INDEX IF NOT EXISTS idx_photo_faces_identity_id ON photo_faces(identity_id);
