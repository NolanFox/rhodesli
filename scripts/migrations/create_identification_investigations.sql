-- Session 149: Identification Investigations Table
-- Stores structured identification research sessions with per-candidate evidence
-- Schema source: docs/session_context/session-148c-api-schema-proposal.md

CREATE TABLE IF NOT EXISTS identification_investigations (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,

    -- Investigation scope
    investigation_name text NOT NULL,
    session_id text NOT NULL,
    community_id text,
    collection_id text,

    -- Target person
    target_name text NOT NULL,
    target_birth_year int,
    target_death_year int,
    target_relationship text,
    target_gedcom_id text,
    target_spouse text,
    target_geography text,

    -- Known references (anchors for the search)
    known_references jsonb NOT NULL DEFAULT '[]'::jsonb,

    -- Methodology
    methodology_steps jsonb NOT NULL DEFAULT '[]'::jsonb,

    -- Candidates evaluated
    candidates jsonb NOT NULL DEFAULT '[]'::jsonb,

    -- Clusters found during investigation
    clusters jsonb NOT NULL DEFAULT '[]'::jsonb,

    -- Outcome
    outcome text NOT NULL DEFAULT 'IN_PROGRESS',
    confirmed_identity_id text,
    confirmed_face_ids jsonb DEFAULT '[]'::jsonb,
    confidence_overall text,

    -- Signals used (quantitative record of what worked)
    signals_used jsonb DEFAULT '{}'::jsonb,

    -- Also identified (bonus finds during this investigation)
    also_identified jsonb DEFAULT '[]'::jsonb,

    -- Feature ideas generated during investigation
    feature_ideas jsonb DEFAULT '[]'::jsonb,

    -- Metadata
    investigator text DEFAULT 'claude',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),

    CONSTRAINT valid_outcome CHECK (outcome IN (
        'IN_PROGRESS', 'CONFIRMED', 'INCONCLUSIVE', 'DEFERRED'
    )),
    CONSTRAINT valid_confidence CHECK (confidence_overall IS NULL OR confidence_overall IN (
        'VERY_HIGH', 'HIGH', 'MODERATE', 'LOW'
    ))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_investigations_target_name
    ON identification_investigations(target_name);
CREATE INDEX IF NOT EXISTS idx_investigations_session
    ON identification_investigations(session_id);
CREATE INDEX IF NOT EXISTS idx_investigations_outcome
    ON identification_investigations(outcome);
CREATE INDEX IF NOT EXISTS idx_investigations_community
    ON identification_investigations(community_id);
CREATE INDEX IF NOT EXISTS idx_investigations_confirmed_identity
    ON identification_investigations(confirmed_identity_id);

-- GIN index for searching within JSONB candidates
CREATE INDEX IF NOT EXISTS idx_investigations_candidates_gin
    ON identification_investigations USING gin (candidates);

-- RLS
ALTER TABLE identification_investigations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "investigations_read" ON identification_investigations
    FOR SELECT USING (auth.role() = 'service_role');

CREATE POLICY "investigations_write" ON identification_investigations
    FOR INSERT WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "investigations_update" ON identification_investigations
    FOR UPDATE USING (auth.role() = 'service_role');

COMMENT ON TABLE identification_investigations IS
    'Structured identification research sessions with per-candidate evidence and methodology (Session 148c)';
COMMENT ON COLUMN identification_investigations.candidates IS
    'Per-face assessments: face_id, photo_id, embedding_distance, confidence, decision, evidence text';
COMMENT ON COLUMN identification_investigations.signals_used IS
    'Quantitative record of which identification signals were used and their strength';
