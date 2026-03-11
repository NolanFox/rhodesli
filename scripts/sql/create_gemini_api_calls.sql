-- Gemini API Calls tracking table (AD-152)
-- Logs every Gemini API call for model, cost, and performance analysis.

CREATE TABLE IF NOT EXISTS gemini_api_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id TEXT NOT NULL,
    model_used TEXT NOT NULL,
    call_type TEXT NOT NULL,  -- 'alignment', 'enrichment', 'combined', 'date_estimation'
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd NUMERIC(10, 6),
    latency_ms INTEGER,
    status TEXT NOT NULL,  -- 'success', 'rate_limited', 'error', 'timeout'
    error_message TEXT,
    rate_limit_type TEXT,  -- 'rpm', 'rpd', 'tpm', null if not rate limited
    response_summary JSONB,  -- key fields from response (not full response)
    gemini_config JSONB,  -- thinking_level, max_output_tokens, temperature
    prompt_manifest_id TEXT,
    prompt_family TEXT,
    prompt_version TEXT,
    prompt_variant TEXT,
    prompt_contract_version TEXT,
    prompt_hash TEXT,
    full_response_hash TEXT,
    experiment_id TEXT,
    shadow_run_id TEXT,
    request_surface TEXT,
    request_mode TEXT,
    related_state_event_id TEXT,
    contract_valid BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT now(),
    batch_id TEXT,  -- groups calls from same batch run
    prompt_text TEXT,
    full_response JSONB,
    gedcom_context TEXT
);

CREATE INDEX IF NOT EXISTS idx_gemini_calls_photo ON gemini_api_calls(photo_id);
CREATE INDEX IF NOT EXISTS idx_gemini_calls_model ON gemini_api_calls(model_used);
CREATE INDEX IF NOT EXISTS idx_gemini_calls_status ON gemini_api_calls(status);
CREATE INDEX IF NOT EXISTS idx_gemini_calls_batch ON gemini_api_calls(batch_id);
CREATE INDEX IF NOT EXISTS idx_gemini_calls_prompt_manifest ON gemini_api_calls(prompt_manifest_id);
CREATE INDEX IF NOT EXISTS idx_gemini_calls_prompt_family ON gemini_api_calls(prompt_family);
