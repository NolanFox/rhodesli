# Rhodesli Development Roadmap

Heritage photo identification system. FastHTML + InsightFace + Supabase + Railway + R2.
Current: v0.64.0 · ~3250 tests · 271 photos · 775 identities · 55 confirmed

## Progress Tracking Convention
- `[ ]` = Todo | `[-]` = In Progress (add date) | `[x]` = Completed (add date)
- When completing a task, move to "Recently Completed" with date

## Current State & Key Risks
- User data migrated to Supabase Postgres (Session 59C). ML data still JSON/NumPy.
- **ML architecture: AD-110 Serving Path Contract** — web requests NEVER run heavy ML.
- Community sharing live on Jews of Rhodes Facebook group (~2,000 members)
- Gemini 3.1 Pro wired to Estimate (AD-139) — progressive refinement designed (AD-102)
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

### Near-Term
- [ ] PRODUCT-002: Face Compare Tier 2 — shared backend architecture (AD-117)
- [ ] ML-053: Multi-pass Gemini — low-confidence re-labeling
- [ ] FE-041: "Help Identify" mode for non-admin users
- [ ] ML-096: Flash vs Pro comparison (20 photos, ~$0.62, needs approval)
- [ ] Active learning pipeline

### Future
- [ ] PRODUCT-003: NL Archive Query MVP — LangChain (AD-118)
- [ ] PRODUCT-004: Historical Photo Date Estimator Standalone
- [ ] OPS-002: CI/CD pipeline
- [ ] PRODUCT-005: Face Compare Tier 3 — product grade
- [ ] GEN-001+: Multi-tenant architecture

See [docs/BACKLOG.md](docs/BACKLOG.md) for full details on each item.

## Planned Sessions

### Session 61B: Verify, Optimize, Assess — COMPLETE (2026-02-22)
- [x] Production verification of Session 61 features (ENOSPC fix, smoke test, screenshots)
- [x] Gemini unified extraction architecture (AD-143, 16 tests)
- [x] Flash vs Pro comparison — deferred pending cost approval (docs/PENDING_APPROVALS.md)
- [x] PRD-015 v2 face alignment + PRD-023 LoRA/calibration + AD-143/144/145
- [x] Self-assessment protocol (HD-016, .claude/rules/self-assessment.md)

### Session 43: Life Events & Context Graph (deferred)
- Event tagging, connecting photos/people/places/dates
- PRD: docs/prds/011_life_events_context_graph.md

## Recently Completed

- [x] 2026-02-22: **v0.64.0 — Session 61**: Gemini Photo Detective + Multi-Photo Compare. Fixed enriched prompt gap (ML-090). Gemini 3.1 Pro (AD-139). MLflow tracking (AD-140). Multi-photo compare (AD-141, PRD-021). Evidence cards UX (AD-142, PRD-022). ~3250 tests.
- [x] 2026-02-22: **v0.63.0/v0.63.1 — Sessions 60/60B**: Gemini Progressive Refinement + SSE Upload + Production Verification. P0 CSS crash fix. 3192 tests.
- [x] 2026-02-22: **v0.62.0 — Session 59C**: Supabase Migration for User Data Safety. DATA-001 structurally resolved. 3102 tests.
- [x] 2026-02-21: **v0.61.0/v0.61.1 — Sessions 59/59B**: Face Compare Standalone + Recovery + Deploy Safety. AD-131-134. 3123 tests.
- [x] 2026-02-21: **v0.60.0 — Session 58**: MLflow Model Registry + Promotion Pipeline. AD-130. 3068 tests.

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
