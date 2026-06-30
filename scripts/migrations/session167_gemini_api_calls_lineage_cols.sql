-- Session 167 (GEMINI-API-CALLS-SCHEMA-166): add the prompt-lineage columns to
-- gemini_api_calls so the values the code ALREADY passes get their own typed
-- columns instead of being folded into gemini_config._lineage.
--
-- BACKGROUND
-- ----------
-- Session 166 found that log_gemini_call() passed lineage columns
-- (contract_valid, prompt_manifest_id, request_surface, ...) that the LIVE
-- gemini_api_calls table did not have. PostgREST rejects the ENTIRE insert on a
-- single unknown column (PGRST204), so every interactive/admin estimate log was
-- being silently dropped. The Session-166 fix added a live-column-discovery
-- filter in app/supabase_data.py:log_gemini_call() that strips unknown columns
-- and stashes them inside gemini_config._lineage (so the data is preserved, just
-- not queryable as first-class columns).
--
-- This migration adds the real columns. Once applied, the discovery filter in
-- log_gemini_call() will see these columns in the live table and route the
-- values to them directly (no code change required — the filter is data-driven).
--
-- experiment_id is NOT included here — it was already added in
-- scripts/migrations/alter_gemini_api_calls_add_experiment_id.sql (Session 154).
--
-- All columns are nullable + ADD COLUMN IF NOT EXISTS => additive-only, safe to
-- re-run, no breaking changes, backwards-compatible with existing rows.
--
-- DO NOT APPLY UNATTENDED. Apply via the Supabase pooler (session mode, port
-- 5432, us-west-2; see Lesson 175) or the Management API SQL endpoint, then bust
-- the cached column set (restart the app, or it self-refreshes on next cold
-- start — _GEMINI_API_CALLS_COLUMNS is a module global).

ALTER TABLE gemini_api_calls
    ADD COLUMN IF NOT EXISTS contract_valid          BOOLEAN,
    ADD COLUMN IF NOT EXISTS prompt_manifest_id       TEXT,
    ADD COLUMN IF NOT EXISTS prompt_hash              TEXT,
    ADD COLUMN IF NOT EXISTS full_response_hash       TEXT,
    ADD COLUMN IF NOT EXISTS request_surface          TEXT,
    ADD COLUMN IF NOT EXISTS request_mode             TEXT,
    ADD COLUMN IF NOT EXISTS shadow_run_id            TEXT,
    ADD COLUMN IF NOT EXISTS prompt_family            TEXT,
    ADD COLUMN IF NOT EXISTS prompt_version           TEXT,
    ADD COLUMN IF NOT EXISTS prompt_variant           TEXT,
    ADD COLUMN IF NOT EXISTS prompt_contract_version  TEXT,
    ADD COLUMN IF NOT EXISTS related_state_event_id   TEXT;

-- Optional: backfill the new typed columns from gemini_config._lineage for rows
-- written during the drift window (Session 166 onward), where the filter stashed
-- these values inside the JSONB. Safe to run after the ALTER; only touches rows
-- that actually have a _lineage blob and a still-NULL target column.
UPDATE gemini_api_calls
SET
    contract_valid         = COALESCE(contract_valid,         (gemini_config->'_lineage'->>'contract_valid')::boolean),
    prompt_manifest_id      = COALESCE(prompt_manifest_id,      gemini_config->'_lineage'->>'prompt_manifest_id'),
    prompt_hash             = COALESCE(prompt_hash,             gemini_config->'_lineage'->>'prompt_hash'),
    full_response_hash      = COALESCE(full_response_hash,      gemini_config->'_lineage'->>'full_response_hash'),
    request_surface         = COALESCE(request_surface,         gemini_config->'_lineage'->>'request_surface'),
    request_mode            = COALESCE(request_mode,            gemini_config->'_lineage'->>'request_mode'),
    shadow_run_id           = COALESCE(shadow_run_id,           gemini_config->'_lineage'->>'shadow_run_id'),
    prompt_family           = COALESCE(prompt_family,           gemini_config->'_lineage'->>'prompt_family'),
    prompt_version          = COALESCE(prompt_version,          gemini_config->'_lineage'->>'prompt_version'),
    prompt_variant          = COALESCE(prompt_variant,          gemini_config->'_lineage'->>'prompt_variant'),
    prompt_contract_version = COALESCE(prompt_contract_version, gemini_config->'_lineage'->>'prompt_contract_version'),
    related_state_event_id  = COALESCE(related_state_event_id,  gemini_config->'_lineage'->>'related_state_event_id')
WHERE gemini_config IS NOT NULL
  AND gemini_config ? '_lineage';

-- Index for filtering by prompt manifest (the most common lineage query axis).
CREATE INDEX IF NOT EXISTS idx_gemini_api_calls_prompt_manifest_id
    ON gemini_api_calls(prompt_manifest_id)
    WHERE prompt_manifest_id IS NOT NULL;
