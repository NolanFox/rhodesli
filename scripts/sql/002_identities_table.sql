-- Shadow write table for identity records
-- Source of truth migration: identities.json -> Supabase identities table
-- Created: Session 90b (2026-03-06)

CREATE TABLE IF NOT EXISTS identities (
    identity_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT,
    state TEXT NOT NULL CHECK (state IN ('CONFIRMED', 'PROPOSED', 'INBOX', 'SKIPPED')),
    anchor_ids JSONB DEFAULT '[]',
    candidate_ids JSONB DEFAULT '[]',
    negative_ids JSONB DEFAULT '[]',
    version_id INTEGER DEFAULT 1,
    merged_into UUID REFERENCES identities(identity_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for state-based queries (browse page filters)
CREATE INDEX IF NOT EXISTS idx_identities_state ON identities(state);

-- Index for merged identity lookups
CREATE INDEX IF NOT EXISTS idx_identities_merged_into ON identities(merged_into)
    WHERE merged_into IS NOT NULL;

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_identities_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS identities_updated_at ON identities;
CREATE TRIGGER identities_updated_at
    BEFORE UPDATE ON identities
    FOR EACH ROW
    EXECUTE FUNCTION update_identities_updated_at();
