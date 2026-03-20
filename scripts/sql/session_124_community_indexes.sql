-- Session 124: Add indexes for community_id filtering
-- These tables are filtered by community_id but only have composite PKs starting with photo_id/identity_id
CREATE INDEX IF NOT EXISTS idx_photo_communities_community_id
ON photo_communities (community_id);

CREATE INDEX IF NOT EXISTS idx_identity_communities_community_id
ON identity_communities (community_id);
