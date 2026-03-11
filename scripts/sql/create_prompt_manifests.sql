-- Prompt manifest registry for Gemini-backed flows (Session 97, AD-218)

CREATE TABLE IF NOT EXISTS prompt_manifests (
    prompt_manifest_id TEXT PRIMARY KEY,
    prompt_family TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    prompt_variant TEXT NOT NULL,
    prompt_contract_version TEXT NOT NULL,
    channel TEXT NOT NULL,
    context_flags JSONB DEFAULT '{}'::jsonb,
    template_source TEXT,
    prompt_hash TEXT,
    git_commit TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_prompt_manifests_family ON prompt_manifests(prompt_family);
CREATE INDEX IF NOT EXISTS idx_prompt_manifests_status ON prompt_manifests(status);
