# Session 96e-cont7 Log — PRD-038 + Post-Deploy Verification + Sort Fix

## Mission: Comprehensive PRD for longitudinal face modeling + browser verify cont6 deploy + fix upload sort
## Started: 2026-03-10
## Version: v0.97.7
## Assessment: docs/assessments/session-96e-cont7-assessment.md
## Predecessor: Session 96e-cont6

## Phase Checklist
- [x] Phase 1: Post-deploy browser verification (resync, Halfon, Benatar, Discoveries)
- [x] Phase 2: PRD-038 comprehensive rewrite (hub + 4 sub-files, 960 lines total)
- [x] Phase 3: Upload sort fix (backfill upload_date in resync endpoint)
- [x] Phase 4: Harness outputs (assessment, CHANGELOG, SESSION_LOG, BACKLOG breadcrumbs)

## Commits
- f32563f: docs: PRD-038 comprehensive rewrite — evaluation, recalibration arch, safety
- 1e82d5e: fix(sync): backfill upload_date on photos missing it during resync
- 2a42d87: docs: update assessment, changelog, session log for cont7 completion

### Phase 5: Post-Deploy Sort Verification (cont8)
- [x] Railway CLI deploy confirmed SUCCESS with DOCKERFILE builder (deploy 8e86b551)
- [x] Resync triggered: 938 photos, 3023 identities, 643 upload_dates backfilled
- [x] "Upload Date (Newest)" sort verified — recent community photos at top of grid
- [x] Screenshot evidence: ss_3712ugncj

## Key Findings
1. Recalibration hooks silently fail on production (sklearn not on Railway, embeddings path wrong)
2. Upload sort broken because BUG-1 wiped upload_date from volume JSON for pre-cont6 uploads
3. Deploy via CLI uses DOCKERFILE builder correctly; git push auto-deploy uses RAILPACK
4. resync-supabase endpoint fails with JSONDecodeError if Content-Type: application/json sent with empty body

## Files Created/Modified
- docs/prds/038_longitudinal_face_modeling.md (rewritten)
- docs/prds/038_longitudinal/RECALIBRATION_ARCHITECTURE.md (new)
- docs/prds/038_longitudinal/IMPLEMENTATION_SPECS.md (new)
- docs/prds/038_longitudinal/EVALUATION_AND_SAFETY.md (new)
- docs/prds/038_longitudinal/RESEARCH_REFERENCES.md (new)
- docs/BACKLOG.md (ML-110-116 breadcrumbs)
- app/sync_routes.py (upload_date backfill)
- docs/assessments/session-96e-cont7-assessment.md (new)
- CHANGELOG.md, docs/SESSION_LOG.md
