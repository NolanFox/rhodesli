# PRD-046: ML Pipeline Run Provenance

**Status:** Draft | **Author:** Session 102 | **Date:** 2026-03-15
**Prerequisite for:** PRD-045 (Active Learning Feedback Loop)

## Problem

The ML pipeline has no run-level tracking:
- `proposals.json` is overwritten on every `cluster_new_faces.py` run — no history
- `core/run_context.py` writes run IDs to local text file, not Supabase
- `core/event_recorder.py` writes JSONL events but isn't wired into clustering
- No way to compare two runs, A/B test, or audit what changed
- Re-running clustering with new parameters could silently regress quality

## Solution

### 1. `ml_runs` Supabase table

| Column | Type | Description |
|--------|------|-------------|
| run_id | UUID PK | Unique run identifier |
| created_at | timestamptz | Run start time |
| pipeline_type | text | `cluster_new_faces`, `reranker_shadow`, `active_learning` |
| config_json | jsonb | Full config snapshot: thresholds, model versions, parameters |
| status | text | `running`, `completed`, `failed` |
| result_summary | jsonb | Counts: proposals generated, tier splits, new matches |
| duration_ms | int | Wall clock time |
| triggered_by | text | `manual`, `post_upload`, `scheduled` |
| parent_run_id | UUID nullable | For incremental runs that build on a prior run |

### 2. `ml_proposals` Supabase table

| Column | Type | Description |
|--------|------|-------------|
| proposal_id | UUID PK | Unique proposal identifier |
| run_id | UUID FK → ml_runs | Which run generated this |
| source_identity_id | UUID | The query identity |
| target_identity_id | UUID | The proposed match |
| score | float | Distance/similarity score |
| calibrated_score | float nullable | After calibration |
| tier | text | `tier_1`, `tier_2`, `no_match` |
| status | text | `pending`, `accepted`, `rejected`, `expired` |
| decided_by | text nullable | User who acted on it |
| decided_at | timestamptz nullable | When acted on |

### 3. Run-aware clustering

`cluster_new_faces.py` changes:
1. Create `ml_runs` row at start with config snapshot
2. Write each proposal to `ml_proposals` with run_id
3. Update `ml_runs.status` and `result_summary` at end
4. proposals.json becomes a cache/export, not source of truth

### 4. Diff/compare tooling

`scripts/compare_ml_runs.py`:
- Input: two run_ids
- Output: new proposals in run B not in A, removed proposals, score changes
- Visual: markdown table suitable for session logs

### 5. Migration path

1. Create tables (Supabase SQL editor)
2. Backfill current proposals.json into ml_proposals with a synthetic run_id
3. Update cluster_new_faces.py to write to both
4. Once stable, proposals.json becomes read-only cache

## Out of Scope

- Real-time ML inference (AD-110: web requests never run heavy ML)
- Automated rollback (manual review of diffs is sufficient for now)
- Multi-tenant ML runs (single pipeline, community filtering at query time)

## Acceptance Criteria

- [ ] `ml_runs` and `ml_proposals` tables exist in Supabase
- [ ] `cluster_new_faces.py` creates a run record and writes proposals to Supabase
- [ ] `compare_ml_runs.py` produces a readable diff between two runs
- [ ] Existing proposals.json workflow still works (backward compat)
- [ ] At least one real clustering run tracked end-to-end in Supabase
