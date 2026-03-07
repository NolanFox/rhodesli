-- PRD-029: Media Groups — front/back photo linking (alternate migration file)
-- Adds media_group_id, media_role, parent_photo_id, back_image, back_transcription to photos table.

ALTER TABLE photos ADD COLUMN IF NOT EXISTS media_group_id TEXT;
ALTER TABLE photos ADD COLUMN IF NOT EXISTS media_role TEXT DEFAULT 'front';
ALTER TABLE photos ADD COLUMN IF NOT EXISTS parent_photo_id TEXT;
ALTER TABLE photos ADD COLUMN IF NOT EXISTS back_image TEXT;
ALTER TABLE photos ADD COLUMN IF NOT EXISTS back_transcription TEXT;

-- Index for fast group lookups
CREATE INDEX IF NOT EXISTS idx_photos_media_group_id ON photos(media_group_id);
CREATE INDEX IF NOT EXISTS idx_photos_parent_photo_id ON photos(parent_photo_id);
