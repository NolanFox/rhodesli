# Session 96e-cont7 Log — PRD-038 + Post-Deploy Verification
## Mission: Comprehensive PRD for longitudinal face modeling + browser verify cont6 deploy
## Started: 2026-03-10
## Version: v0.97.7
## Assessment: docs/assessments/session-96e-cont7-assessment.md

### Phase 1: Post-Deploy Verification
- [x] Supabase resync triggered: 938 photos, 3023 identities synced
- [x] Raymond Halfon photo: face detected, 3572x2553px, source clean
- [x] Claude Benatar photo: face overlay visible, 1241x1891px, source clean
- [x] Discoveries: 0 auto-applied (BUG-7 fix confirmed), 561 Help Identify

### Phase 2: PRD-038 Comprehensive Rewrite
- [x] Hub PRD rewritten following template (235 lines)
- [x] RECALIBRATION_ARCHITECTURE.md — 4 architecture options, Option A recommended
- [x] IMPLEMENTATION_SPECS.md — Per-workstream code changes, LoRA data growth strategy
- [x] EVALUATION_AND_SAFETY.md — Golden test set, retroactive improvement safety, community resilience
- [x] RESEARCH_REFERENCES.md — Academic papers, Google Photos analysis, heritage challenges
- [x] BACKLOG ML-110-116 breadcrumbs added to PRD-038

### Key Finding
Recalibration hooks (`rhodesli_ml/recalibration_hooks.py`) wired into `app/engagement_routes.py:727-740` but silently fail on production because sklearn not installed on Railway (AD-007) and embeddings path wrong (Lesson 114). Data collection (calibration_pairs) may be working but recalibration itself cannot run.

---

# Session 93 Log — Close All Deferrals
## Mission: Close ALL deferred items from Session 92
## Started: 2026-03-08
## Version: v0.95.0 → v0.96.0
## Context: docs/session_context/session-93-context.md
## Predecessor: Session 92 (v0.95.0)
## Detailed log: docs/session_logs/session-93-log.md

### Phase 1-4: DATA-007 — Postgres Migration
- [x] Core tables created: identities, photos, photo_faces + 4 indexes
- [x] Data backfilled: 894 identities, 295 photos, 981 faces
- [x] Null name fix: identity 224495e8 defaulted to "Unknown (224495e8)"
- [x] DATA_SOURCE=postgres flipped on Railway
- [x] Deploy confirmed: "IdentityRegistry loaded from Postgres (894 identities)"

### Phase 5-7: Observability Verification
- [x] Sentry: 5 real issues (NameError photo_url, APIError invalid UUID)
- [x] PostHog: Page view events + 4 server-side events
- [x] Resend: 1 email delivered, RESEND_API_KEY confirmed

### Phase 8: Batch GEDCOM Re-analyze
- [x] 67/72 photos reanalyzed with Gemini 3.1 Pro
- [x] Runtime: ~79 minutes, estimated cost ~$2.66
- [x] 91% high confidence, avg 4.5-year date ranges

### Phase 9: Supplementary Migration
- [x] date_labels (271), photo_locations (268), birth_year_estimates (32)
- [x] Column name mismatch fixed (full_data → data)

### Phase 10: GEDCOM Reanalysis Report
- [x] 10-section in-depth analysis: docs/ml/GEDCOM_REANALYSIS_REPORT.md
- [x] AD-211 entry added
- [x] User feedback captured: docs/session_context/session-93-user-feedback.md

### Tests
- App: 3717 passed, 4 skipped
- ML: 566 passed
- 1 pre-existing e2e failure (chromium discovery layer sort)
