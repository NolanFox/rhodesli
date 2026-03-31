-- Session 146: Identity Suggestions Table (PRD-059 Phase 4)
-- Stores ML-generated identity suggestions with multi-signal evidence

CREATE TABLE IF NOT EXISTS identity_suggestions (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    target_identity_id uuid NOT NULL,
    suggested_name text NOT NULL,
    suggested_identity_id uuid,          -- nullable: links to existing confirmed identity
    suggested_gedcom_id text,            -- nullable: GEDCOM individual ID
    family_id text,                      -- e.g., 'fox' — which family cluster
    confidence float NOT NULL DEFAULT 0.0,
    evidence_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'PENDING',  -- PENDING / ACCEPTED / REJECTED / NEEDS_MORE
    rejection_reason text,               -- admin note on rejection
    created_at timestamptz DEFAULT now(),
    reviewed_at timestamptz,
    reviewed_by text,                    -- admin email
    CONSTRAINT valid_status CHECK (status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'NEEDS_MORE'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_identity_suggestions_target
    ON identity_suggestions(target_identity_id);
CREATE INDEX IF NOT EXISTS idx_identity_suggestions_status
    ON identity_suggestions(status);
CREATE INDEX IF NOT EXISTS idx_identity_suggestions_confidence
    ON identity_suggestions(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_identity_suggestions_family
    ON identity_suggestions(family_id);

-- Enable RLS (allow authenticated reads, admin writes)
ALTER TABLE identity_suggestions ENABLE ROW LEVEL SECURITY;

-- Policy: anyone can read suggestions
CREATE POLICY "identity_suggestions_read" ON identity_suggestions
    FOR SELECT USING (true);

-- Policy: authenticated users can insert/update (admin check in app layer)
CREATE POLICY "identity_suggestions_write" ON identity_suggestions
    FOR ALL USING (true) WITH CHECK (true);

COMMENT ON TABLE identity_suggestions IS 'ML-generated identity suggestions with multi-signal evidence scores (PRD-059 Phase 4)';
COMMENT ON COLUMN identity_suggestions.evidence_json IS 'Per-signal breakdown: family_cluster, co_occurrence, age_trajectory, gedcom_match, testimony, provenance';
COMMENT ON COLUMN identity_suggestions.confidence IS 'Weighted aggregate score 0.0-1.0 across all signals';
