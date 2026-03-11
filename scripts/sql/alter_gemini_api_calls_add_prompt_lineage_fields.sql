-- Add prompt-manifest lineage fields to gemini_api_calls (Session 97, AD-218)

ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS prompt_manifest_id TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS prompt_family TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS prompt_version TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS prompt_variant TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS prompt_contract_version TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS prompt_hash TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS full_response_hash TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS experiment_id TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS shadow_run_id TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS request_surface TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS request_mode TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS related_state_event_id TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS contract_valid BOOLEAN;

CREATE INDEX IF NOT EXISTS idx_gemini_calls_prompt_manifest ON gemini_api_calls(prompt_manifest_id);
CREATE INDEX IF NOT EXISTS idx_gemini_calls_prompt_family ON gemini_api_calls(prompt_family);
