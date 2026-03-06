-- Shadow write table for photo metadata
-- Source of truth migration: photo_index.json -> Supabase photos table
-- Created: Session 90b (2026-03-06)

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
    job_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for collection-based queries
CREATE INDEX IF NOT EXISTS idx_photos_collection ON photos(collection);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_photos_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS photos_updated_at ON photos;
CREATE TRIGGER photos_updated_at
    BEFORE UPDATE ON photos
    FOR EACH ROW
    EXECUTE FUNCTION update_photos_updated_at();
