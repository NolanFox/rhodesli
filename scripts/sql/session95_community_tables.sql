-- Session 95: Community infrastructure tables for PRD-035
-- Creates photo_communities, identity_communities, upload_batches tables
-- and adds new columns to communities and photos tables.

-- 1. Enhance communities table with landing page columns
ALTER TABLE communities ADD COLUMN IF NOT EXISTS landing_title TEXT;
ALTER TABLE communities ADD COLUMN IF NOT EXISTS landing_subtitle TEXT;
ALTER TABLE communities ADD COLUMN IF NOT EXISTS landing_hero_style TEXT;
ALTER TABLE communities ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT true;
ALTER TABLE communities ADD COLUMN IF NOT EXISTS created_by UUID;

-- 2. Photo-community many-to-many
CREATE TABLE IF NOT EXISTS photo_communities (
    photo_id TEXT NOT NULL,
    community_id UUID NOT NULL REFERENCES communities(id),
    added_at TIMESTAMPTZ DEFAULT now(),
    added_by UUID,
    PRIMARY KEY (photo_id, community_id)
);

-- 3. Identity-community many-to-many
CREATE TABLE IF NOT EXISTS identity_communities (
    identity_id UUID NOT NULL,
    community_id UUID NOT NULL REFERENCES communities(id),
    is_primary BOOLEAN DEFAULT false,
    added_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (identity_id, community_id)
);

-- 4. Upload batches
CREATE TABLE IF NOT EXISTS upload_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id UUID NOT NULL REFERENCES communities(id),
    uploaded_by UUID,
    source_description TEXT,
    date_range_hint TEXT,
    location_hint TEXT,
    notes TEXT,
    photo_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 5. Link photos to their upload batch
ALTER TABLE photos ADD COLUMN IF NOT EXISTS upload_batch_id UUID;

-- 6. Seed Fox Family community
INSERT INTO communities (slug, name, description, admin_emails, r2_prefix, landing_title, landing_subtitle)
VALUES ('fox-family', 'Fox Family Archive',
        'Preserving our family''s visual history through digitized photos',
        ARRAY['NolanFox@gmail.com'], 'fox_photos/',
        'Fox Family Archive', 'Preserving our family''s visual history')
ON CONFLICT (slug) DO NOTHING;

-- 7. Update Rhodes community with landing page fields
UPDATE communities
SET landing_title = 'Jewish Community of Rhodes',
    landing_subtitle = 'Heritage photo archive for the Sephardic Jewish community of Rhodes'
WHERE slug = 'rhodes' AND landing_title IS NULL;
