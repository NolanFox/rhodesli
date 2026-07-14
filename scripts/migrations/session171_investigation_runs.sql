-- Session 171: durable Research Desk case/run contract.
-- Each row is one immutable-input run with its evidence and sealed verdicts.

CREATE TABLE IF NOT EXISTS investigation_runs (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    case_ref text NOT NULL,
    community_id text,
    input_manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
    input_manifest_hash text NOT NULL,
    idempotency_key text NOT NULL,
    status text NOT NULL DEFAULT 'pending',
    status_history jsonb NOT NULL DEFAULT '[]'::jsonb,
    claims jsonb NOT NULL DEFAULT '[]'::jsonb,
    candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
    contradictions jsonb NOT NULL DEFAULT '[]'::jsonb,
    requested_decisions jsonb NOT NULL DEFAULT '[]'::jsonb,
    sealed_verdicts jsonb NOT NULL DEFAULT '[]'::jsonb,
    models_used jsonb NOT NULL DEFAULT '[]'::jsonb,
    total_tokens int NOT NULL DEFAULT 0,
    total_cost_usd numeric NOT NULL DEFAULT 0,
    rights_state text NOT NULL DEFAULT 'private',
    worth_opening boolean,
    adjudication jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    sealed_at timestamptz,
    reviewed_at timestamptz,

    CONSTRAINT uq_investigation_runs_idem UNIQUE (idempotency_key),
    CONSTRAINT valid_run_idempotency_key CHECK (
        idempotency_key = case_ref || ':' || input_manifest_hash
    ),
    CONSTRAINT valid_run_status CHECK (status IN (
        'pending', 'assembling', 'investigating', 'sealed', 'reviewed', 'failed'
    )),
    CONSTRAINT valid_rights_state CHECK (rights_state IN (
        'private', 'archive_only', 'publishable'
    )),
    CONSTRAINT max_three_decisions CHECK (jsonb_array_length(requested_decisions) <= 3)
);

CREATE INDEX IF NOT EXISTS idx_investigation_runs_case_ref
    ON investigation_runs(case_ref);
CREATE INDEX IF NOT EXISTS idx_investigation_runs_status
    ON investigation_runs(status);

ALTER TABLE investigation_runs ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    CREATE POLICY "investigation_runs_read" ON investigation_runs
        FOR SELECT USING (auth.role() = 'service_role');
EXCEPTION WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE POLICY "investigation_runs_write" ON investigation_runs
        FOR INSERT WITH CHECK (auth.role() = 'service_role');
EXCEPTION WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE POLICY "investigation_runs_update" ON investigation_runs
        FOR UPDATE USING (auth.role() = 'service_role');
EXCEPTION WHEN duplicate_object THEN NULL;
END
$$;

ALTER TABLE identification_investigations
    ADD COLUMN IF NOT EXISTS rights_state text DEFAULT 'private';
