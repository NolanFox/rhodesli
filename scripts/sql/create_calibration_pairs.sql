-- Calibration labels used for local similarity recalibration.
CREATE TABLE IF NOT EXISTS calibration_pairs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    face_id_a TEXT NOT NULL,
    face_id_b TEXT NOT NULL,
    pair_key TEXT,
    similarity_score DOUBLE PRECISION NOT NULL,
    is_match BOOLEAN NOT NULL,
    source TEXT NOT NULL,
    weight DOUBLE PRECISION DEFAULT 1.0,
    label_type TEXT,
    active BOOLEAN DEFAULT TRUE,
    state_event_id TEXT,
    state_event_action TEXT,
    source_surface TEXT,
    actor_id TEXT,
    linked_event_id TEXT,
    reversed_by_event_id TEXT,
    labeled_at TIMESTAMPTZ DEFAULT now(),
    superseded_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(face_id_a, face_id_b)
);

CREATE INDEX IF NOT EXISTS idx_calibration_pairs_pair_key ON calibration_pairs(pair_key);
CREATE INDEX IF NOT EXISTS idx_calibration_pairs_active ON calibration_pairs(active);
CREATE INDEX IF NOT EXISTS idx_calibration_pairs_label_type ON calibration_pairs(label_type);
CREATE INDEX IF NOT EXISTS idx_calibration_pairs_state_event_id ON calibration_pairs(state_event_id);
