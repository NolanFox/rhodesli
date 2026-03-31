# SDD: PRD-059 Phase 4 — Identity Inference Engine

**Parent PRD:** [059_temporal_co_occurrence.md](059_temporal_co_occurrence.md)
**Date:** 2026-03-30
**References:** AD-235 (Family Cluster Score), Session 145 context

---

## Architecture

```
  scripts/compute_identity_suggestions.py   (batch — runs offline)
       |
       v
  Supabase: identity_suggestions table     (persistent storage)
       |
       v
  app/identity_routes.py                   (reads table, renders UI)
       |
       v
  Person page: "Identity Suggestion" panel (admin-only)
```

The inference engine is a **batch computation** — never runs in a web request (AD-110).
The script reads from existing Supabase tables (identities, photo_faces, date_labels,
co_occurrence_pairs, gedcom_individuals) and writes scored suggestions.

Admin actions (accept/reject) write back to identity_suggestions and, on accept,
promote the identity via the existing confirm workflow.

---

## Data Model

### Table: `identity_suggestions`

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key (auto) |
| target_identity_id | uuid | The unidentified person |
| suggested_name | text | Candidate identity name |
| suggested_gedcom_id | text | GEDCOM individual ID (nullable) |
| family_id | text | Which family cluster (e.g., "fox") |
| confidence | float | Overall weighted score 0.0-1.0 |
| evidence_json | jsonb | Per-signal breakdown (see below) |
| status | text | PENDING / ACCEPTED / REJECTED / NEEDS_MORE |
| rejection_reason | text | Admin note on rejection (nullable) |
| created_at | timestamptz | Batch computation time |
| reviewed_at | timestamptz | Admin action time (nullable) |
| reviewed_by | text | Admin email (nullable) |

**Indexes:** target_identity_id, status, confidence DESC

### evidence_json Schema

```json
{
  "family_cluster": {
    "score": 0.82,
    "raw_distance": 1.18,
    "threshold": 1.35,
    "n_family_members": 8,
    "closest_member": "Albert Fox",
    "closest_distance": 0.95
  },
  "co_occurrence": {
    "score": 0.65,
    "shared_photos_with_family": 12,
    "total_photos": 18,
    "top_co_occurring": [
      {"name": "Esther Burd Fox", "count": 8},
      {"name": "Albert Fox", "count": 6}
    ]
  },
  "age_trajectory": {
    "score": 0.90,
    "candidate_birth_year": 1889,
    "observations": [
      {"photo_date": 1920, "estimated_age": 30, "expected_age": 31, "deviation": 1},
      {"photo_date": 1930, "estimated_age": 42, "expected_age": 41, "deviation": 1}
    ],
    "mean_absolute_deviation": 1.0
  },
  "gedcom_match": {
    "score": 0.80,
    "relationship": "sibling",
    "generation_match": true,
    "era_overlap": true,
    "birth_year_source": "1894 Minsk revision list"
  },
  "testimony": {
    "score": 0.0,
    "entries": []
  },
  "provenance": {
    "score": 0.60,
    "labels": [
      {"source": "Fox cousin", "label": "Ervin Fox's sister", "relationship": "extended_family"}
    ]
  }
}
```

### Table: `testimony_evidence` (new, optional)

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| target_identity_id | uuid | Who is being identified |
| source_name | text | "Howard Newman" |
| source_relationship | text | "grandson of Rachel Fox" |
| statement | text | Free text of what they said |
| polarity | text | POSITIVE / NEGATIVE / UNCERTAIN |
| confidence_impact | float | -1.0 to +1.0 |
| session_id | text | Which session captured this |
| created_at | timestamptz | When recorded |

---

## Key Functions

### `compute_family_cluster_score(target_id, family_member_ids, embeddings, threshold=1.35)`

AD-235 implementation. Computes mean L2 distance from target centroid to all confirmed family member centroids. Normalizes to 0.0-1.0 (1.0 at distance 0.8, 0.0 at threshold+0.2). Returns dict with `score`, `raw_distance`, `closest_member`, `closest_distance`, `n_family_members`.

### `compute_age_feasibility(target_id, candidate_birth_year, date_labels, max_deviation=10.0)`

For each photo containing target face, computes expected age (photo_year - birth_year) vs Gemini-estimated age. Returns 0.0 if any expected age is impossible (<0 or >110). Otherwise returns `1.0 - (MAD / max_deviation)` clamped to [0, 1]. Returns 0.5 (neutral) when no age data available.

### `aggregate_evidence(signals, weights=None)`

Weighted sum of normalized signal scores. Default weights: testimony 0.30, family_cluster 0.25, age_trajectory 0.20, co_occurrence 0.10, gedcom_match 0.10, provenance 0.05. When signals are absent (e.g., no testimony), their weight is redistributed proportionally to present signals.

---

## UI: Evidence Panel on Person Page

Rendered in `app/identity_routes.py` for admin users when `identity_suggestions` has
rows for the current person with status=PENDING.

```
+--------------------------------------------------+
| Identity Suggestion: Rachel Fox Newman       0.78 |
| Family Cluster  [========------]  0.82           |
| Age Trajectory  [=========-----]  0.90           |
| Co-occurrence   [======--------]  0.65           |
| GEDCOM Match    [========------]  0.80           |
| Testimony       (none available)                  |
| Provenance      [=====----------]  0.60           |
|                                                    |
| [Accept as Rachel Fox Newman] [Reject] [Need More]|
+--------------------------------------------------+
```

- Sortable by confidence when multiple suggestions exist
- Accept triggers: rename identity, set state=CONFIRMED, update GEDCOM link
- Reject triggers: status=REJECTED, rejection_reason stored, prevents re-suggestion
- "Need More" triggers: status=NEEDS_MORE, flagged for follow-up

---

## Batch Script: `scripts/compute_identity_suggestions.py`

Usage: `python scripts/compute_identity_suggestions.py --family fox [--dry-run|--execute]`

Pipeline: load confirmed family from Supabase, load embeddings + co-occurrence + date_labels + GEDCOM + testimony, score all GEDCOM candidates for each unidentified person with family_cluster_score < threshold, upsert top-3 candidates per person to `identity_suggestions`. Dry-run prints scores without Supabase writes (Lesson 162).

---

## Testing Strategy

### Unit Tests (in `tests/`)
- `test_family_cluster_score()` — verified against Session 145 distance matrix
- `test_age_feasibility_impossible()` — Bessie b.1877 at age 98 scores 0.0
- `test_age_feasibility_plausible()` — Rachel b.1889 in 1920 photo scores high
- `test_aggregate_evidence_redistribution()` — absent testimony redistributes weight
- `test_aggregate_evidence_all_signals()` — full signal set produces expected score

### Integration Tests
- `test_batch_script_dry_run()` — script runs without Supabase writes
- `test_suggestion_panel_renders()` — person page shows panel for PENDING suggestions
- `test_accept_suggestion()` — accept promotes identity to CONFIRMED
- `test_reject_suggestion()` — reject prevents re-suggestion

### Validation: Leave-One-Out
- For each confirmed Fox identity, temporarily remove from confirmed set
- Run inference engine — does it correctly suggest the removed identity?
- Target: 6/8 correct top-1 (75% accuracy) given N=8 family members
- Known hard case: Albert/Harry (CLUSTER-QUALITY-001) — acceptable to rank both in top-2

### Ground Truth from Session 145
| Person | Expected Identity | Key Evidence |
|--------|-------------------|--------------|
| 82863536 | Rachel Fox Newman | 0.95 to Rachel, Fox cousin labeled "Ervin's sister" |
| 3299 | Bessie's descendant | 0.51 to Bessie, but b.1877 → impossible age in 1975 |
| 3481 | NOT Rachel | Howard Newman negative testimony, 1.43 family cluster score |
| 4044 | Fox sister (unclear) | 1920-1954 spread, 1.10 to Rachel in 1954 face |

---

## Migration SQL

```sql
CREATE TABLE IF NOT EXISTS identity_suggestions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    target_identity_id UUID NOT NULL,
    suggested_name TEXT NOT NULL,
    suggested_gedcom_id TEXT,
    family_id TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    evidence_json JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'PENDING',
    rejection_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT
);

CREATE INDEX idx_identity_suggestions_target ON identity_suggestions(target_identity_id);
CREATE INDEX idx_identity_suggestions_status ON identity_suggestions(status);
CREATE INDEX idx_identity_suggestions_confidence ON identity_suggestions(confidence DESC);
```

---

## Open Questions
1. Should the scoring weights be configurable per-family in Supabase, or hardcoded?
2. When testimony contradicts embedding evidence (Howard says "not Rachel" but embeddings say strong match), should testimony always win?
3. Should we surface suggestions to non-admin users in a read-only "Community Hypothesis" mode?
