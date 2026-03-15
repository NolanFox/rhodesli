-- PRD-046: ML Run Provenance Tables
-- Session 103, 2026-03-15

CREATE TABLE IF NOT EXISTS ml_runs (
  run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ DEFAULT now(),
  pipeline_type TEXT NOT NULL,
  config_json JSONB,
  status TEXT DEFAULT 'running',
  result_summary JSONB,
  duration_ms INT,
  triggered_by TEXT DEFAULT 'manual',
  parent_run_id UUID REFERENCES ml_runs(run_id)
);

CREATE TABLE IF NOT EXISTS ml_proposals (
  proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID REFERENCES ml_runs(run_id),
  source_identity_id UUID,
  target_identity_id UUID,
  score FLOAT,
  calibrated_score FLOAT,
  tier TEXT,
  status TEXT DEFAULT 'pending',
  decided_by TEXT,
  decided_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ml_proposals_run ON ml_proposals(run_id);
CREATE INDEX IF NOT EXISTS idx_ml_proposals_status ON ml_proposals(status);
