-- Global Person Links: cross-community identity linking
-- Enables the same person to be recognized across multiple photo archives.
-- link_type: 'confirmed' (human verified) | 'proposed' (ML suggested)
-- Created: Session 91 Track E (2026-03-07)

CREATE TABLE IF NOT EXISTS global_person_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    global_person_id UUID NOT NULL,
    community_id UUID NOT NULL REFERENCES communities(id),
    identity_id UUID NOT NULL,
    link_type TEXT NOT NULL,
    confidence NUMERIC(5,4),
    linked_by TEXT,
    evidence JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(community_id, identity_id)
);

CREATE INDEX IF NOT EXISTS idx_gpl_global ON global_person_links(global_person_id);
CREATE INDEX IF NOT EXISTS idx_gpl_identity ON global_person_links(identity_id);
CREATE INDEX IF NOT EXISTS idx_gpl_community ON global_person_links(community_id);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_gpl_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS gpl_updated_at ON global_person_links;
CREATE TRIGGER gpl_updated_at
    BEFORE UPDATE ON global_person_links
    FOR EACH ROW
    EXECUTE FUNCTION update_gpl_updated_at();
