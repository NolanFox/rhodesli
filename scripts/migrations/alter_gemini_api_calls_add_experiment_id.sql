-- Session 154 Phase A0: Schema fix for shadow-eval logging.
-- Adds experiment_id column to gemini_api_calls so the shadow-eval script
-- (and future A/B harnesses) can group calls under a stable run identifier
-- without the existing gemini_config.experiment_id workaround.
--
-- Why: Session 153b shadow eval observed every Supabase log write fail with
-- PGRST204 because the script's `experiment_id=...` kwarg has no matching
-- column. Logging fell through to gemini_config.experiment_id but the
-- top-level column was missing. Backfill from gemini_config when known.
--
-- Additive-only — no breaking changes.

ALTER TABLE gemini_api_calls
    ADD COLUMN IF NOT EXISTS experiment_id TEXT;

-- Backfill from gemini_config.experiment_id where it has been logged in the
-- nested JSON (Session 153b shadow eval rows wrote it there as a fallback).
UPDATE gemini_api_calls
SET experiment_id = gemini_config->>'experiment_id'
WHERE experiment_id IS NULL
  AND gemini_config IS NOT NULL
  AND gemini_config ? 'experiment_id';

-- Index for filtering shadow-eval runs by experiment.
CREATE INDEX IF NOT EXISTS idx_gemini_api_calls_experiment_id
    ON gemini_api_calls(experiment_id)
    WHERE experiment_id IS NOT NULL;
