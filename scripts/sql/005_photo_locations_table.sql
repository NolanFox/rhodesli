-- Shadow write table for Gemini location estimation results
-- One row per photo with lat/lng and location metadata
-- Created: Session 90b (2026-03-06)

CREATE TABLE IF NOT EXISTS photo_locations (
    photo_id TEXT PRIMARY KEY REFERENCES photos(photo_id),
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    location_name TEXT,
    location_estimate TEXT,
    confidence TEXT,
    geocoded_from TEXT,
    raw_response JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_photo_locations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS photo_locations_updated_at ON photo_locations;
CREATE TRIGGER photo_locations_updated_at
    BEFORE UPDATE ON photo_locations
    FOR EACH ROW
    EXECUTE FUNCTION update_photo_locations_updated_at();
