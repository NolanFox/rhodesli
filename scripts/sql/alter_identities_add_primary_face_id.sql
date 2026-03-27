-- Session 141: Add primary_face_id column for hero face picker (FB-007)
-- Allows admin to override quality-based face selection with a manually chosen face.
-- Nullable text column — NULL means use quality-based selection (default behavior).

ALTER TABLE identities ADD COLUMN IF NOT EXISTS primary_face_id TEXT;

COMMENT ON COLUMN identities.primary_face_id IS 'Admin-chosen hero face ID. When set, overrides quality-based selection in get_best_face_id(). Session 141 FB-007.';
