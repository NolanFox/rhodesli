-- Shadow write table for Gemini date estimation results
-- One row per photo with estimated date/decade
-- Created: Session 90b (2026-03-06)

CREATE TABLE IF NOT EXISTS date_labels (
    photo_id TEXT PRIMARY KEY REFERENCES photos(photo_id),
    estimated_decade INTEGER,
    best_year_estimate INTEGER,
    confidence TEXT,
    model_used TEXT,
    labeled_by TEXT DEFAULT 'gemini',
    raw_response JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_date_labels_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS date_labels_updated_at ON date_labels;
CREATE TRIGGER date_labels_updated_at
    BEFORE UPDATE ON date_labels
    FOR EACH ROW
    EXECUTE FUNCTION update_date_labels_updated_at();
