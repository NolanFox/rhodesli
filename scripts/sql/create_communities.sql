-- Communities table for multi-tenant support (GlobalPersonID schema)
-- Each community represents a distinct photo archive with its own identities.
-- Created: Session 91 Track E (2026-03-07)

CREATE TABLE IF NOT EXISTS communities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    admin_emails TEXT[],
    r2_prefix TEXT NOT NULL,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_communities_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS communities_updated_at ON communities;
CREATE TRIGGER communities_updated_at
    BEFORE UPDATE ON communities
    FOR EACH ROW
    EXECUTE FUNCTION update_communities_updated_at();
