# Session 146: Deploy + Fader Collection + PRD-059 Phase 4 Foundation

## Context
Session 145 was an interactive family research session. Rachel Fox Newman identified and confirmed by descendant Howard Newman. Full Fox sibling mapping from 1894 Minsk revision list. Family Cluster Score approach validated (AD-235). PRD-059 Phase 4 specified with SDD. FB-001 UX fix committed. Fader collection (147 photos) ingested locally but not deployed.
See `docs/session_context/session-145-context.md` for full context.
See `docs/assessments/session-145-assessment.md` for assessment.

## Approach
This session runs autonomously. Follow all harness rules in `.claude/rules/`. Codex audit after every phase. /clear between phases. Assessment + ROADMAP + BACKLOG + CHANGELOG at end.

## Phase 0: Deploy + Verify (SEQUENTIAL)

### 0a: Deploy v0.99.58
- `git push origin main` or `railway deploy`
- Wait for deploy completion, verify health endpoint
- Check deploy status: `mcp__railway-mcp-server__list-deployments`

### 0b: Browser Verify Session 145 Changes
- **FB-001 fix**: Navigate to `/c/fox-family/identify/{any_identity_id}` as admin. Click "View Person Page" — should go to person page, NOT queue.
- **Rachel Fox Newman**: `/c/fox-family/person/f41dff7b-ec67-4e0b-9dde-96474988c769` — should show 3+ photos (2 Howard photos + merged 82863536 photo)
- **Standard smoke**: landing, people grid, person page, compare, estimate, 404

### 0c: Verify Session 145 Assessment Items
- Rachel person page renders correctly with merged photos
- All test suites pass (baseline from session 145: 3980+ app tests)

## Phase 1: Fader Collection Deploy (SEQUENTIAL — after Phase 0)

The Fader collection was ingested locally (147 photos, 328 faces, 0 failures) but needs to reach production.

### 1a: Re-run Ingest (if needed)
The local ingest wrote to data files that were restored to git state. Check if ingest output is recoverable, or re-run:
```bash
python -m core.ingest_inbox \
  --directory ~/Downloads/fox_sibling_pictures/sarah_fox_fader_clean/ \
  --job-id fader-002 \
  --source "Sherry Ann Fader Collection (via Erik Josowitz)" \
  --collection "Sarah Fox Fader Family" \
  --community fader-collection \
  --uploaded-by "Erik Josowitz"
```
Community already exists in Supabase: slug=fader-collection, id=1a2c23d6-fc5e-4d0e-b020-1721579485bf

### 1b: Upload to R2
Upload 147 photos + ~400 crops to R2 fader_photos/ prefix.

### 1c: Push to Production
Push updated data files. Verify Fader community appears in navigation.

### 1d: Cross-Community Matching
Run cross-batch matching against Fox family embeddings. Session 145 analysis showed no strong matches (closest: Charles Fox at 1.13), but verify on production.

### 1e: Browser Verify Fader Collection
- `/c/fader-collection/` loads with photos
- `/c/fader-collection/people` shows detected faces
- Cross-community badges appear if any matches found

## Phase 2: PRD-059 Phase 4 Foundation (PARALLEL tracks if independent files)

### 2a: Identity Suggestions Table
Create Supabase migration for `identity_suggestions` table per SDD (`docs/prds/059_phase4_sdd.md`):
- target_identity_id, suggested_name, suggested_identity_id
- evidence_json (JSONB with all 6 signal scores)
- confidence (float), status (pending/accepted/rejected)
- created_at, reviewed_at, reviewed_by

### 2b: Family Cluster Score Batch Script
Create `scripts/compute_family_scores.py` per AD-235:
- For each unidentified person, compute mean L2 distance to all confirmed Fox family members
- Write results to identity_suggestions table
- Include: family_cluster_score, closest_member, closest_distance, n_members_within_threshold

### 2c: Evidence Panel UI (STRETCH)
Add "Identity Suggestions" section to person page per SDD wireframe:
- Show evidence breakdown per signal
- Accept/Reject buttons for admin
- Only render when identity_suggestions has entries for this person

## Constraints
- Production data files (data/*.json, data/*.npy) are production-origin — NEVER commit (Lesson 141)
- Fader photos at ~/Downloads/fox_sibling_pictures/sarah_fox_fader_clean/ (147 unique, deduped)
- Fox family sibling list is DEFINITIVE from 1894 Minsk revision: Bessie, Sarah, Harry, Sadie, Rachel, Albert, Irving, Jacob. Rose Scheckzner is Harry's WIFE, not a sibling.
- Family Cluster Score threshold: 1.34-1.35 (NOT 1.30). Per-family calibrated, not global.

## Key Files
- `docs/session_context/session-145-context.md` — all research findings
- `docs/prds/059_temporal_co_occurrence.md` — PRD with Phase 4 spec
- `docs/prds/059_phase4_sdd.md` — SDD for implementation
- `docs/ml/ALGORITHMIC_DECISIONS.md` — AD-235 Family Cluster Score
- `app/page_routes.py:5189` — FB-001 fix location
- `data/fader_embeddings.npy` — re-extracted Fader embeddings (if present)

## Parallelization Plan
| Track | Files | Depends On |
|-------|-------|------------|
| Phase 0 (deploy) | none (git push) | — |
| Phase 1a-1c (Fader ingest) | data/*.json, data/*.npy | Phase 0 |
| Phase 1d-1e (cross-match) | core/cross_batch_matching.py | Phase 1c |
| Phase 2a (migration) | Supabase SQL | — (parallel with 1) |
| Phase 2b (batch script) | scripts/compute_family_scores.py | Phase 2a |
| Phase 2c (UI) | app/page_routes.py | Phase 2a |

## Mandatory Close
- Assessment: `docs/assessments/session-146-assessment.md`
- CHANGELOG: increment to v0.99.59
- ROADMAP + BACKLOG: update status
- Browser verify: all changes on production
- `git log origin/main..HEAD` must be empty
