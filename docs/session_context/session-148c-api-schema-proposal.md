# Session 148c — Identification Investigations Schema Proposal

**Date:** 2026-04-14
**Source:** Codex audit (self-performed — Codex at capacity) + harness compliance review
**Auditor:** Claude Opus 4.6 (1M context)
**Agent type:** Resume (sees full session context)

---

## Part 1: Harness Compliance Audit (P0/P1/P2/P3)

### Present (PASS)

| Artifact | Path | Status |
|----------|------|--------|
| Assessment | `docs/assessments/session-148c-assessment.md` | EXISTS — 4 phases shipped, 4 deferred, 4 red flags |
| CHANGELOG | `CHANGELOG.md` line 5 | EXISTS — v0.99.63 entry |
| Feedback file | `docs/feedback/session-148c-feedback.md` | EXISTS — 8 FB items, all with disposition |
| Investigation JSON | `docs/session_context/session-148c-investigation.json` | EXISTS — structured data |
| Learnings | `docs/session_context/session-148c-learnings.md` | EXISTS — signal rankings + 6 feature proposals |
| Context file | `docs/session_context/session-148c-context.md` | EXISTS |

### Gaps Found

| Severity | Gap | Details |
|----------|-----|---------|
| **P1** | ROADMAP.md missing 148c entry | ROADMAP "Recently Completed" has 148b but NOT 148c. Session 148c shipped v0.99.63 with Abraham Fader identification + 6 bug fixes + methodology docs, but no ROADMAP entry. |
| **P1** | BACKLOG.md not updated | Session 148c assessment lists 4 deferred items and 6 feature proposals, none of which appear in BACKLOG.md. FB-002 (kinship identification), FB-003 (Ancestry integration), FB-004 (Gemini visual context), FB-006 (name collision detection) all marked "BACKLOG candidate" in feedback file but never written to BACKLOG. |
| **P2** | SESSION_HISTORY.md missing 148c | No entry for Session 148c in `docs/roadmap/SESSION_HISTORY.md`. |
| **P2** | SESSION_LOG.md stale | Still shows Session 114 content. Not reset or updated for 148c. |
| **P3** | Codex audit coverage reduced | 2/3 Codex attempts hit capacity. Self-audit performed as fallback (documented in assessment). Acceptable given transient infrastructure issue. |

### Summary
Assessment file is thorough. CHANGELOG updated. Feedback items all have dispositions. However, ROADMAP and BACKLOG were not updated — the two files that make session work discoverable for future sessions. SESSION_HISTORY also missing.

---

## Part 2: Identification Investigations Table Schema

### Motivation

Session 148c performed manual identification investigation work (Nellie Kubrin, Abraham Fader) that produced structured data currently stored as ad-hoc JSON (`session-148c-investigation.json`). This data should be stored in Supabase so that:

1. Future investigations for the same family can retrieve past findings
2. Per-candidate assessments (face IDs, distances, confidence) are queryable
3. The methodology steps are auditable
4. The data feeds back into ML pipelines (training data for identification models)

### Relationship to `gemini_api_calls`

The `gemini_api_calls` table stores individual API call records: one row per Gemini invocation with prompt, response, cost, and tokens. An identification investigation is a **higher-level concept** that may include 0+ Gemini calls but also includes:

- Manual visual analysis (no API call)
- Embedding distance computations
- Genealogical research (GEDCOM, Ancestry)
- Cross-photo person tracking
- Event context reasoning

The two tables relate as: `identification_investigations` 1:N `gemini_api_calls` (an investigation may trigger multiple Gemini calls, linked by `investigation_id`).

### Schema

```sql
-- Session 148c: Identification Investigations Table
-- Stores structured identification research sessions with per-candidate evidence

CREATE TABLE IF NOT EXISTS identification_investigations (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,

    -- Investigation scope
    investigation_name text NOT NULL,              -- e.g., "Nellie Kubrin Identification"
    session_id text NOT NULL,                      -- e.g., "148c"
    community_id text,                             -- community scope (nullable for cross-community)
    collection_id text,                            -- which photo collection was searched

    -- Target person
    target_name text NOT NULL,                     -- who we're looking for
    target_birth_year int,
    target_death_year int,
    target_relationship text,                      -- e.g., "Mother of Sherry Ann Fader (CONFIRMED)"
    target_gedcom_id text,                         -- GEDCOM individual ID if known
    target_spouse text,                            -- spouse name for context
    target_geography text,                         -- e.g., "NYC tristate area"

    -- Known references (anchors for the search)
    known_references jsonb NOT NULL DEFAULT '[]'::jsonb,
    -- Array of: { identity_id, name, anchor_count, role }
    -- e.g., [{"identity_id": "37611153-...", "name": "Sherry Ann Fader",
    --         "anchor_count": 35, "role": "daughter"}]

    -- Methodology
    methodology_steps jsonb NOT NULL DEFAULT '[]'::jsonb,
    -- Array of: { step_number, description, outcome }
    -- e.g., [{"step_number": 1, "description": "Built Sherry centroid from
    --         solo bridal portrait + 9 closest faces", "outcome": "10-face centroid"}]

    -- Candidates evaluated
    candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
    -- Array of: { face_id, photo_id, photo_filename, cluster_name,
    --             embedding_distance, confidence, decision, evidence,
    --             linked_identity_id }
    -- decision: "ACCEPT" | "REJECT" | "POSSIBLE" | "ELIMINATED"
    -- e.g., [{"face_id": "inbox_484e92285abb", "photo_id": "D72A1E71",
    --         "embedding_distance": 0.8773, "confidence": "VERY_HIGH",
    --         "decision": "ACCEPT",
    --         "evidence": "Cake topper handoff, brocade dress matches ceremony"}]

    -- Clusters found during investigation
    clusters jsonb NOT NULL DEFAULT '[]'::jsonb,
    -- Array of: { cluster_name, face_count, photo_count, avg_reference_distance,
    --             status, assessment }
    -- status: "CANDIDATE" | "ELIMINATED" | "CONFIRMED"

    -- Outcome
    outcome text NOT NULL DEFAULT 'IN_PROGRESS',   -- IN_PROGRESS | CONFIRMED | INCONCLUSIVE | DEFERRED
    confirmed_identity_id uuid,                     -- if outcome=CONFIRMED, the resulting identity
    confirmed_face_ids jsonb DEFAULT '[]'::jsonb,   -- face IDs assigned to the confirmed identity
    confidence_overall text,                        -- VERY_HIGH | HIGH | MODERATE | LOW

    -- Signals used (quantitative record of what worked)
    signals_used jsonb DEFAULT '{}'::jsonb,
    -- { "event_context": {"strength": "VERY_STRONG", "note": "corsage + aisle walk"},
    --   "cross_photo_tracking": {"strength": "STRONG", "intra_dist": "0.58-0.76"},
    --   "age_genealogy_filter": {"strength": "STRONG", "candidates_eliminated_pct": 85},
    --   "kinship_embedding": {"strength": "WEAK", "gap": 0.09},
    --   "cross_collection": {"strength": "NONE"} }

    -- Also identified (bonus finds during this investigation)
    also_identified jsonb DEFAULT '[]'::jsonb,
    -- Array of: { name, face_id, photo_id, status, description }

    -- Feature ideas generated during investigation
    feature_ideas jsonb DEFAULT '[]'::jsonb,
    -- Array of: { title, description }

    -- Metadata
    investigator text DEFAULT 'claude',             -- "claude" | "human" | admin email
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

-- Link gemini_api_calls to investigations (optional FK column on gemini_api_calls)
-- ALTER TABLE gemini_api_calls ADD COLUMN investigation_id uuid
--     REFERENCES identification_investigations(id);

-- RLS
ALTER TABLE identification_investigations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "investigations_read" ON identification_investigations
    FOR SELECT USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

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
```

### How Session 148c Data Maps to This Schema

| Investigation JSON field | Table column |
|--------------------------|-------------|
| `investigation` | `investigation_name` |
| `session` | `session_id` |
| `target.*` | `target_name`, `target_birth_year`, `target_death_year`, `target_relationship`, `target_spouse`, `target_geography` |
| `known_references.*` | `known_references` (JSONB) |
| `methodology.*` | `methodology_steps` (JSONB array) |
| `clusters_of_interest.*` | `clusters` (JSONB array) |
| `consolidated_nellie_candidate.face_ids_likely_same_person` | `candidates` (JSONB array) |
| `consolidated_nellie_candidate.overall_confidence` | `confidence_overall` |
| `also_identified.*` | `also_identified` (JSONB) |
| `feature_ideas_from_methodology` | `feature_ideas` (JSONB) |
| Learnings file signal rankings | `signals_used` (JSONB) |

### Example Query: Retrieve Past Investigations for the Same Family

```sql
-- Find all investigations involving the Fader family
SELECT investigation_name, target_name, outcome, confidence_overall, created_at
FROM identification_investigations
WHERE known_references::text ILIKE '%fader%'
   OR target_name ILIKE '%fader%'
ORDER BY created_at DESC;

-- Find all confirmed identifications with high confidence
SELECT investigation_name, target_name, confirmed_identity_id
FROM identification_investigations
WHERE outcome = 'CONFIRMED'
  AND confidence_overall IN ('VERY_HIGH', 'HIGH');

-- Find investigations that used a specific identity as a reference
SELECT *
FROM identification_investigations
WHERE known_references @> '[{"identity_id": "37611153-36d1-4f20-9535-d994e1893e13"}]'::jsonb;
```

### Design Decisions

1. **JSONB for candidates/clusters/methodology** rather than normalized child tables. Rationale: investigations are write-once-read-many, and the nested structure mirrors how the data is produced. Avoids 4+ join tables for a feature that will have O(100) rows, not O(100K).

2. **`investigation_id` on `gemini_api_calls`** is proposed as an optional ALTER (commented out). This links API calls to the investigation that triggered them without breaking the existing table. Add it when Gemini is wired into the investigation workflow.

3. **`signals_used` as JSONB** rather than a fixed set of columns. Rationale: the signal set is still evolving (Session 148c identified 6 signals, future sessions may add more). JSONB is extensible without schema migrations.

4. **Follows existing patterns**: RLS policies match `identity_suggestions` table. `service_role` for writes, `authenticated` for reads. UUID primary keys. Timestamptz for dates.

### Migration Path

1. Run the CREATE TABLE SQL in Supabase SQL editor
2. Backfill Session 148c data from `session-148c-investigation.json`
3. Add `log_identification_investigation()` helper to `app/supabase_data.py` (mirrors `log_gemini_api_call()`)
4. Wire into future investigation sessions (manual or automated)
5. Optionally add `investigation_id` FK to `gemini_api_calls` when Gemini-assisted identification ships
