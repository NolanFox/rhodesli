# Session 147 Context: PRD-059 Phase 4 Completion — Identity Inference UI + Signals

**Predecessor**: Session 146 (docs/session_context/session-146-context.md)
**Date**: 2026-03-31
**State**: v0.99.59, ~4654 tests (3996 app + 658 ML), PRD-059 Phase 4 partially started

---

## What Session 146 Delivered

### Fader Collection (DEPLOYED)
- 147 photos, 328 faces ingested and live on production
- R2 uploads complete, Supabase sync done
- Community: fader-collection (slug), id: 1a2c23d6-fc5e-4d0e-b020-1721579485bf
- No strong Fox family cross-matches (closest: Charles Fox at 1.13)

### PRD-059 Phase 4 Foundation (PARTIAL)
- **identity_suggestions Supabase table**: 13 columns, 4 indexes, UNIQUE(target_identity_id, family_id), RLS enabled
- **Batch script**: `scripts/compute_identity_suggestions.py` (574 lines)
  - 6 signals defined: family_cluster (COMPLETE), co_occurrence (COMPLETE), age_trajectory (EXISTS BUT NOT WIRED), gedcom_match (PLACEHOLDER), testimony (PLACEHOLDER), provenance (PLACEHOLDER)
  - Dry-run: 19 candidates scored, top confidence=0.288 (low because only 2/6 signals contribute)
  - `--execute` mode NOT YET RUN (no data in Supabase identity_suggestions)
- **Tests**: 16 tests in `tests/test_identity_suggestions.py` covering scoring functions + table existence
- **Documentation**: SDD at `docs/prds/059_phase4_sdd.md` (230 lines), AD-235 in ALGORITHMIC_DECISIONS.md

### Security (Session 146)
- RLS tightened on identity_suggestions (Codex P1+P2 findings fixed)
- UNIQUE constraint added on (target_identity_id, family_id)

---

## What Remains for Phase 4 Completion

### A. Wire Remaining Signals (batch script)
4 of 6 signals are placeholders in the pipeline (lines 474-484 of compute_identity_suggestions.py):

1. **age_trajectory**: Function `compute_age_feasibility()` EXISTS at line 137 but is never called. The pipeline has `date_labels` and `identity_photos` loaded — just needs wiring. Requires candidate birth year from GEDCOM for each candidate.
2. **gedcom_match**: New function. Query `current_gedcom_individuals` view for Fox family GEDCOM records. Score generational/era consistency.
3. **testimony**: Hardcode known evidence from Session 145:
   - Person 3481 (273ac560): Howard Newman "almost certainly NOT my grandmother" → NEGATIVE
   - Person 82863536: Howard Newman confirmed as Rachel → POSITIVE
4. **provenance**: Hardcode known evidence:
   - Person 82863536: Fox cousin labeled "Ervin Fox's sister Sadie" → high provenance

### B. Execute Mode + Verify
Run `--execute` to populate identity_suggestions in Supabase. Verify data appears.

### C. Evidence Panel UI (person page)
Admin-only card on person page showing:
- Suggested identity name + confidence score
- 6 signal progress bars with scores
- Accept / Reject / Need More action buttons
- Only renders when identity_suggestions has PENDING rows for this person

**Pattern to follow**: ML birth year suggestion card at `app/person_routes.py:960-1063` — identical interaction pattern (admin-only card, accept/reject buttons, HTMX swap, auto-dismiss).

### D. Accept/Reject/NeedMore API Endpoints
Following ML review pattern at `app/admin_routes.py:391-535`:
- Accept: rename identity → confirm → link GEDCOM → update Supabase status
- Reject: set REJECTED + store reason → prevent re-suggestion
- NeedMore: set NEEDS_MORE → flag for follow-up

---

## Key Technical Details

### Supabase Table: identity_suggestions
```
id (uuid PK), target_identity_id (uuid), suggested_name (text),
suggested_identity_id (uuid nullable), suggested_gedcom_id (text nullable),
family_id (text), confidence (float), evidence_json (jsonb),
status (text: PENDING/ACCEPTED/REJECTED/NEEDS_MORE),
rejection_reason (text nullable), created_at (timestamptz),
reviewed_at (timestamptz nullable), reviewed_by (text nullable)
```
SQL: `scripts/sql/session_146_identity_suggestions.sql`

### GEDCOM Access
- `current_gedcom_individuals` Supabase view with fallback to `gedcom_individuals` table
- Cached in `app/relationship_routes.py:_load_gedcom_individuals()` with TTL
- birth_date field is TEXT (e.g., "1889", "ABT 1890") — needs parsing

### Evidence JSON Schema (from SDD)
```json
{
  "family_cluster": {"score": 0.82, "raw_distance": 1.18, "threshold": 1.35, ...},
  "co_occurrence": {"score": 0.65, "shared_photos_with_family": 12, ...},
  "age_trajectory": {"score": 0.90, "candidate_birth_year": 1889, "observations": [...], ...},
  "gedcom_match": {"score": 0.80, "relationship": "sibling", ...},
  "testimony": {"score": 0.0, "entries": []},
  "provenance": {"score": 0.60, "labels": [...]}
}
```

### Key Identity IDs (Ground Truth)
| Person | ID | Status | Expected |
|--------|----|----|----------|
| Albert Fox | 85546ebf-75b9-4971-a9d4-b2ce2271bc19 | CONFIRMED | 199 faces |
| Esther Burd Fox | 65207728-9ee6-48c1-be68-a2da23354caf | CONFIRMED | 143 faces |
| Rachel Fox Newman | f41dff7b-ec67-4e0b-9dde-96474988c769 | CONFIRMED | verified |
| Person 82863536 | (query from Supabase) | UNIDENTIFIED | Family cluster 0.95 → Rachel |
| Person 3481 | 273ac560-bf13-43f5-8f87-e0f7ec967b2c | UNIDENTIFIED | NOT Fox (Howard Newman negative) |
| Person 3299 | 7cbbecb4-96bc-4275-901b-df35cf0b7d27 | UNIDENTIFIED | Likely Elizabeth Tischler |
| Person 4044 | dd201526-2722-47a1-8d9c-af5240b9f9bf | UNIDENTIFIED | Fox signal (1.10) |

---

## Pre-Implementation Audit Findings

### P1 — Cache Invalidation on Accept
When a suggestion is accepted and the identity is renamed/confirmed, the registry caches (`_identities_cache`, `_suggestions_cache`, `perf_cache`) must be invalidated. The ML review accept endpoint at admin_routes.py:440 demonstrates the pattern: call `save_registry()` with `changed_ids`, which triggers cache invalidation. Follow the same path.

### P1 — CSRF on New POST Endpoints
All three new POST endpoints (accept/reject/needs-more) MUST include `_check_origin()` for CSRF protection, following the pattern at admin_routes.py:395.

### P1 — Accept Must Not Double-Confirm
If an identity is already CONFIRMED (race condition: admin confirmed via another surface), the accept endpoint must handle gracefully — check state before rename/confirm.

### P2 — GEDCOM birth_date Parsing
The `gedcom_individuals.birth_date` field stores varied formats ("1889", "ABT 1890", "BEF 1895", "1 JAN 1890"). The `compute_gedcom_match_score()` function needs robust year extraction via regex.

### P2 — Suggestion Staleness
If identities are merged or confirmed between batch run and admin review, the suggestion may be stale. Accept endpoint should verify target identity still exists and is unconfirmed.

### P3 — Hardcoded Testimony
Hardcoding testimony in the script is pragmatic for Phase 4 but should be tagged with a TODO for migration to `testimony_evidence` table.

---

## Parallelization Plan

| Track | Phase | Files | Depends On |
|-------|-------|-------|------------|
| Track A (worktree) | Signal implementation | scripts/compute_identity_suggestions.py, tests/test_identity_suggestions.py | None |
| Track B (main) | Evidence panel UI | app/person_routes.py, tests/test_identity_suggestion_ui.py (new) | None |
| Track C (worktree) | API endpoints | app/admin_routes.py, tests/test_identity_suggestion_actions.py (new) | HTMX target ID contract from Track B |
| Sequential | Integration | All files | Tracks A+B+C merged |

No file conflicts between tracks. Cross-track contract: HTMX target ID `#identity-suggestion-{suggestion_id}`.

---

## Deferred Work → BACKLOG
- testimony_evidence Supabase table (SDD marks as optional)
- Leave-one-out validation (SDD testing strategy)
- Inline timeline on person page (TIMELINE-002)
- Second family validation (Capeluto) for threshold generalization
