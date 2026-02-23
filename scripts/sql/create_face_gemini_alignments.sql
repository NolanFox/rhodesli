-- Face Gemini Alignments table (AD-152)
-- Stores per-photo alignment data from Gemini coordinate bridging (PRD-015)
-- Source of truth: Supabase (JSON file is cache-only)

CREATE TABLE IF NOT EXISTS face_gemini_alignments (
    photo_id TEXT PRIMARY KEY,
    alignment_data JSONB NOT NULL,
    model_used TEXT,
    cost NUMERIC(10, 6),
    tokens_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_fga_model ON face_gemini_alignments(model_used);
CREATE INDEX IF NOT EXISTS idx_fga_created ON face_gemini_alignments(created_at);

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_face_alignment_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS face_alignment_updated ON face_gemini_alignments;
CREATE TRIGGER face_alignment_updated
    BEFORE UPDATE ON face_gemini_alignments
    FOR EACH ROW
    EXECUTE FUNCTION update_face_alignment_timestamp();
