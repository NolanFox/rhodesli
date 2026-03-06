-- PRD-029: Media Groups — front/back photo linking
-- Adds media_group_id, media_role, and parent_photo_id to photos table.

ALTER TABLE photos ADD COLUMN IF NOT EXISTS media_group_id UUID;
ALTER TABLE photos ADD COLUMN IF NOT EXISTS media_role TEXT DEFAULT 'front';
ALTER TABLE photos ADD COLUMN IF NOT EXISTS parent_photo_id UUID REFERENCES photos(photo_id);

-- Index for fast group lookups
CREATE INDEX IF NOT EXISTS idx_photos_media_group_id ON photos(media_group_id);
CREATE INDEX IF NOT EXISTS idx_photos_parent_photo_id ON photos(parent_photo_id);

-- Comment: media_group_id defaults to the photo's own photo_id for front images.
-- Back images share the same media_group_id as their front.
-- parent_photo_id is set on back images to point to the front.
