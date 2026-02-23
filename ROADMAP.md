# Rhodesli Development Roadmap

Heritage photo identification system. FastHTML + InsightFace + Supabase + Railway + R2.
Current: v0.66.0 · ~3402 tests · 271 photos · 775 identities · 55 confirmed

## Progress Tracking Convention
- `[ ]` = Todo | `[-]` = In Progress (add date) | `[x]` = Completed (add date)
- When completing a task, move to "Recently Completed" with date

## Current State & Key Risks
- User data migrated to Supabase Postgres (Session 59C). ML data still JSON/NumPy.
- **ML architecture: AD-110 Serving Path Contract** — web requests NEVER run heavy ML.
- Community sharing live on Jews of Rhodes Facebook group (~2,000 members)
- Gemini 3.1 Pro wired to Estimate (AD-139) — progressive refinement designed (AD-102)
- **Similarity calibration live**: isotonic regression, AUC=0.9577, 348 pairs (AD-149/150)
- **Railway volume space** — auto_backups pruned to 5 (was 10), ENOSPC fixed in Session 61B

## Phase Summary

| Phase | Status | Details |
|-------|--------|---------|
| **A: Stabilization** | COMPLETE | All P0 bugs fixed, 103 tests added |
| **B: Share-Ready Polish** | ~95% complete | Remaining: OPS-001 (custom SMTP) |
| **C: Annotation Engine** | COMPLETE | Full submit/review/approve workflow |
| **D: ML Feedback** | ~90% complete | Remaining: ML-053 (multi-pass Gemini), FE-040-043 |
| **E: Collaboration** | ~70% complete | Remaining: Help Identify mode, analytics, moderation |
| **F: Scale & Generalize** | ~10% complete | Remaining: Postgres ML data, CI/CD, Sentry |

For full feature checklists, see [docs/roadmap/FEATURE_STATUS.md](docs/roadmap/FEATURE_STATUS.md).
For ML-specific roadmap, see [docs/roadmap/ML_ROADMAP.md](docs/roadmap/ML_ROADMAP.md).

## Open Work (Prioritized)

### Immediate
- [ ] OPS-001: Custom SMTP for branded email sender (code ready, needs RESEND_API_KEY in Railway)
- [x] Gemini unified extraction architecture — AD-143, rhodesli_ml/gemini_extraction.py (Session 61B)
- [x] PRD-015 v2: Face alignment via coordinate bridging — AD-144 (Session 61B)
- [x] PRD-015 implementation: Face alignment end-to-end — AD-146 (Session 62)
- [x] Production test: Face alignment on real photos — 3/3 pass, $0.03 (Session 63)
- [-] Batch face alignment for all 271 photos — running (Session 63, ~$4 estimated)

### Near-Term
- [ ] PRODUCT-002: Face Compare Tier 2 — shared backend architecture (AD-117)
- [ ] ML-053: Multi-pass Gemini — low-confidence re-labeling
- [ ] FE-041: "Help Identify" mode for non-admin users
- [x] ML-096: Flash vs Pro + GEDCOM comparison (11 runs, $2.46, Session 61C)
- [x] Similarity calibration: isotonic regression, 348 pairs, AUC=0.9577 (Session 63, AD-149)
- [ ] Active learning pipeline

### Future
- [ ] PRODUCT-003: NL Archive Query MVP — LangChain (AD-118)
- [ ] PRODUCT-004: Historical Photo Date Estimator Standalone
- [ ] OPS-002: CI/CD pipeline
- [ ] PRODUCT-005: Face Compare Tier 3 — product grade
- [ ] GEN-001+: Multi-tenant architecture

See [docs/BACKLOG.md](docs/BACKLOG.md) for full details on each item.

## Planned Sessions

### Session 63: Close the Gaps, Calibrate, Re-Run — COMPLETE (2026-02-23)
- [x] Deployed face alignment, verified on 3 real photos (100% success, $0.03)
- [x] GEDCOM Supabase tables (21,809 individuals, 145,574 relationships) + face linking (61 links)
- [x] Ground truth calibration pairs (348 pairs from confirmed identities)
- [x] Isotonic regression calibration (AUC=0.9577, threshold@90%=0.268)
- [x] Recalibration hooks (merge/reject/confirm event-driven, AD-149/150/151)
- [-] Batch face alignment (271 photos, running)

### Session 61C: GEDCOM-Enriched Analysis + Flash vs Pro — COMPLETE (2026-02-23)
- [x] GEDCOM parser extended with life events (RESI, OCCU, IMMI, EMIG, BURI)
- [x] 5-variant GEDCOM context builder (rhodesli_ml/gedcom_context.py, 19 tests)
- [x] Supabase import script (tables not yet created)
- [x] 11 comparison runs: 3 models × 5 GEDCOM variants, $2.46 spent
- [x] Verdict: Pro + curated GEDCOM is optimal (AD-147, AD-148)

### Session 62: PRD-015 Face Alignment Implementation — COMPLETE (2026-02-22)
- [x] EXIF orientation handler (app/exif_handler.py, 10 tests)
- [x] Coordinate bridging module (app/face_alignment.py, 30 tests)
- [x] API endpoints: POST/GET /api/face-alignment/{photo_id} (8 tests)
- [x] Photo page UI: face description cards, mismatch warnings, admin trigger (6 tests)
- [x] AD-146 documented. 54 new tests. ~3373 total.

### Session 43: Life Events & Context Graph (deferred)
- Event tagging, connecting photos/people/places/dates
- PRD: docs/prds/011_life_events_context_graph.md

## Recently Completed

- [x] 2026-02-23: **v0.66.0 — Session 63**: Close the Gaps, Calibrate, Re-Run. Real photo face alignment (3/3 pass). GEDCOM Supabase import (21,809 individuals). Similarity calibration (AUC=0.9577, 348 pairs). Recalibration hooks. AD-149/150/151. 29 new ML tests. ~3402 total.
- [x] 2026-02-23: **Session 61C**: GEDCOM-Enriched Analysis + Flash vs Pro. 3 models × 5 GEDCOM variants ($2.46). Verdict: Pro + curated optimal. AD-147/148. GEDCOM context builder (19 tests). Supabase import script.
- [x] 2026-02-22: **v0.65.0 — Session 62**: PRD-015 Face Alignment via Coordinate Bridging. EXIF handler, coordinate bridging module, API endpoints, photo page UI with per-face description cards. AD-146. 54 new tests. ~3373 total.
- [x] 2026-02-22: **v0.64.0 — Session 61**: Gemini Photo Detective + Multi-Photo Compare. Fixed enriched prompt gap (ML-090). Gemini 3.1 Pro (AD-139). MLflow tracking (AD-140). Multi-photo compare (AD-141, PRD-021). Evidence cards UX (AD-142, PRD-022). ~3250 tests.
- [x] 2026-02-22: **v0.63.0/v0.63.1 — Sessions 60/60B**: Gemini Progressive Refinement + SSE Upload + Production Verification. P0 CSS crash fix. 3192 tests.
- [x] 2026-02-22: **v0.62.0 — Session 59C**: Supabase Migration for User Data Safety. DATA-001 structurally resolved. 3102 tests.
For all sessions: see [docs/roadmap/SESSION_HISTORY.md](docs/roadmap/SESSION_HISTORY.md).

## Reference Documents
- Detailed backlog: `docs/BACKLOG.md`
- Feature status: `docs/roadmap/FEATURE_STATUS.md`
- ML roadmap: `docs/roadmap/ML_ROADMAP.md`
- Session history: `docs/roadmap/SESSION_HISTORY.md`
- ML decisions: `docs/ml/ALGORITHMIC_DECISIONS.md`
- Ops decisions: `docs/ops/OPS_DECISIONS.md`
- UX audit: `docs/ux_audit/UX_ISSUE_TRACKER.md`
- Lessons learned: `tasks/lessons.md`
