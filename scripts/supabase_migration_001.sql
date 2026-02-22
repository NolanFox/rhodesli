-- Rhodesli Supabase Migration 001: User Data Tables
-- AD-135: Migrate user-entered data to Supabase
-- Run this in the Supabase SQL Editor:
--   https://supabase.com/dashboard/project/fvynibivlphxwfowzkjl/sql/new
--
-- These tables store user-entered data that must survive deploys.
-- JSON files become read caches rebuilt from Supabase on startup.

-- ============================================================
-- Table 1: identity_overrides
-- Stores the complete identity record for any user-modified identity.
-- On startup sync: replaces the bundled identity with this version.
-- ============================================================
CREATE TABLE IF NOT EXISTS identity_overrides (
    identity_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,                    -- CONFIRMED, CONTESTED, SKIPPED, etc.
    name TEXT,                              -- user-assigned name
    merged_into TEXT,                       -- target identity_id if merged
    data JSONB NOT NULL,                    -- complete identity record
    updated_by TEXT DEFAULT 'admin',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_identity_overrides_state
    ON identity_overrides(state);
CREATE INDEX IF NOT EXISTS idx_identity_overrides_merged
    ON identity_overrides(merged_into) WHERE merged_into IS NOT NULL;

-- ============================================================
-- Table 2: annotations
-- Community-submitted annotations (name suggestions, bios, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS annotations (
    annotation_id TEXT PRIMARY KEY,
    identity_id TEXT,                       -- target identity (nullable)
    photo_id TEXT,                          -- target photo (nullable)
    type TEXT,                              -- name_suggestion, bio, date, location, etc.
    status TEXT DEFAULT 'pending',          -- pending, approved, rejected, pending_unverified
    data JSONB NOT NULL,                    -- complete annotation record
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_annotations_status
    ON annotations(status);

-- ============================================================
-- Table 3: relationships
-- Person-to-person relationships (spouse, parent-child, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS relationships (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    person_a TEXT NOT NULL,                 -- identity_id
    person_b TEXT NOT NULL,                 -- identity_id
    relationship_type TEXT NOT NULL,        -- spouse, parent, child, sibling
    source TEXT DEFAULT 'human',            -- human, gedcom
    data JSONB NOT NULL,                    -- complete relationship record
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_relationships_persons
    ON relationships(person_a, person_b);

-- ============================================================
-- Table 4: gedcom_matches
-- GEDCOM individual → identity match decisions
-- ============================================================
CREATE TABLE IF NOT EXISTS gedcom_matches (
    xref_id TEXT PRIMARY KEY,               -- GEDCOM individual XREF
    identity_id TEXT,                       -- matched identity (null if unmatched)
    decision TEXT,                          -- confirmed, rejected, skipped, pending
    data JSONB NOT NULL,                    -- complete match record
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gedcom_matches_identity
    ON gedcom_matches(identity_id) WHERE identity_id IS NOT NULL;

-- ============================================================
-- Row Level Security (RLS)
-- Service role key bypasses RLS, so the app can read/write freely.
-- Public access is blocked by default.
-- ============================================================
ALTER TABLE identity_overrides ENABLE ROW LEVEL SECURITY;
ALTER TABLE annotations ENABLE ROW LEVEL SECURITY;
ALTER TABLE relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE gedcom_matches ENABLE ROW LEVEL SECURITY;

-- Service role has full access (used by the app)
-- No public policies = no anonymous access via anon key
-- The app always uses SUPABASE_SERVICE_ROLE_KEY which bypasses RLS

-- ============================================================
-- Verification query (run after migration to check counts)
-- ============================================================
-- SELECT
--     (SELECT COUNT(*) FROM identity_overrides) as identity_overrides,
--     (SELECT COUNT(*) FROM annotations) as annotations,
--     (SELECT COUNT(*) FROM relationships) as relationships,
--     (SELECT COUNT(*) FROM gedcom_matches) as gedcom_matches;
