-- Shadow write table for face detections per photo
-- Maps face_id -> photo_id with detection metadata
-- Created: Session 90b (2026-03-06)

CREATE TABLE IF NOT EXISTS photo_faces (
    face_id TEXT PRIMARY KEY,
    photo_id TEXT REFERENCES photos(photo_id),
    bbox JSONB,
    det_score FLOAT,
    quality FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for photo-based lookups (all faces in a photo)
CREATE INDEX IF NOT EXISTS idx_photo_faces_photo_id ON photo_faces(photo_id);
