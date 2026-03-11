ALTER TABLE calibration_pairs ADD COLUMN IF NOT EXISTS pair_key TEXT;
ALTER TABLE calibration_pairs ADD COLUMN IF NOT EXISTS label_type TEXT;
ALTER TABLE calibration_pairs ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;
ALTER TABLE calibration_pairs ADD COLUMN IF NOT EXISTS state_event_id TEXT;
ALTER TABLE calibration_pairs ADD COLUMN IF NOT EXISTS state_event_action TEXT;
ALTER TABLE calibration_pairs ADD COLUMN IF NOT EXISTS source_surface TEXT;
ALTER TABLE calibration_pairs ADD COLUMN IF NOT EXISTS actor_id TEXT;
ALTER TABLE calibration_pairs ADD COLUMN IF NOT EXISTS linked_event_id TEXT;
ALTER TABLE calibration_pairs ADD COLUMN IF NOT EXISTS reversed_by_event_id TEXT;
ALTER TABLE calibration_pairs ADD COLUMN IF NOT EXISTS labeled_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE calibration_pairs ADD COLUMN IF NOT EXISTS superseded_at TIMESTAMPTZ;
ALTER TABLE calibration_pairs ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

UPDATE calibration_pairs
SET pair_key = face_id_a || '::' || face_id_b
WHERE pair_key IS NULL;

UPDATE calibration_pairs
SET label_type = CASE
    WHEN source ILIKE 'merge%' THEN 'explicit_positive'
    WHEN source ILIKE 'reject%' THEN 'explicit_negative'
    WHEN source ILIKE 'implicit_confirm%' THEN 'implicit_negative'
    WHEN source ILIKE '%discovery%' AND is_match = TRUE THEN 'discovery_confirmed'
    WHEN is_match = TRUE THEN 'explicit_positive'
    ELSE 'explicit_negative'
END
WHERE label_type IS NULL;

UPDATE calibration_pairs
SET labeled_at = COALESCE(labeled_at, created_at, now())
WHERE labeled_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_calibration_pairs_pair_key ON calibration_pairs(pair_key);
CREATE INDEX IF NOT EXISTS idx_calibration_pairs_active ON calibration_pairs(active);
CREATE INDEX IF NOT EXISTS idx_calibration_pairs_label_type ON calibration_pairs(label_type);
CREATE INDEX IF NOT EXISTS idx_calibration_pairs_state_event_id ON calibration_pairs(state_event_id);
