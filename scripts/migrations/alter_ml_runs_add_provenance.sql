-- Session 115: ML Run Provenance Columns (AD-227)
-- Additive-only — no breaking changes to existing rows
-- All columns nullable with sensible defaults

-- What environment executed this run
-- Values: 'local_laptop', 'railway_web', 'railway_ml_service', 'ci', 'test'
ALTER TABLE ml_runs ADD COLUMN IF NOT EXISTS
  execution_environment TEXT DEFAULT 'local_laptop';

-- What ML models and versions were used
-- Example: {"insightface": "0.7.3", "buffalo": "buffalo_l", "calibration": "isotonic_v3"}
ALTER TABLE ml_runs ADD COLUMN IF NOT EXISTS
  model_versions JSONB DEFAULT '{}';

-- Scope: which community was this run for (NULL = all communities / global)
-- Enables community-scoped ML runs as we scale to dozens of communities
ALTER TABLE ml_runs ADD COLUMN IF NOT EXISTS
  community_id UUID;

-- Fine-grained scope filter for subset runs
-- Examples:
--   {"photo_ids": ["abc123", "def456"]}         — run on specific photos
--   {"identity_ids": ["uuid1", "uuid2"]}         — run on specific identities
--   {"batch_id": "upload-2026-03-18"}            — run on specific upload batch
--   {"exclude_confirmed": true}                   — skip already-confirmed
-- NULL means "entire population for the given community_id"
ALTER TABLE ml_runs ADD COLUMN IF NOT EXISTS
  scope_filter JSONB DEFAULT NULL;
