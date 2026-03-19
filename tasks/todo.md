# Rhodesli Active Todo

Last updated: 2026-03-18 (Post-Session 117)

## Done (Sessions 92-93)
- [x] Deploy v0.95.0 → v0.96.0 to Railway + browser verify
- [x] Set SENTRY_DSN + POSTHOG_API_KEY + RESEND_API_KEY on Railway
- [x] DATA-007 — Postgres migration complete (identities, photos, photo_faces)
- [x] Batch GEDCOM re-analyze — 67/72 photos, AD-211
- [x] Observability verified — Sentry, PostHog, Resend all confirmed
- [x] Email notifications via Resend
- [x] CI/CD foundation — .github/workflows/test.yml
- [x] Multi-pass Gemini + active learning foundations
- [x] 10 P1/P2 UX bugs fixed
- [x] Leon's Restaurant fix (AD-210)
- [x] Full API call logging (prompt_text, full_response, gedcom_context)
- [x] main.py refactored: 26,100 → 9,346 lines (Session 91b)

## Immediate (Housekeeping)
- [x] PERF-001: Test speed <30s — achieved 28s (Session 114)
- [ ] OPS-001: Custom SMTP for branded email (code ready, needs RESEND_API_KEY config)
- [ ] BACKLOG-FLAKY-001: 8 order-dependent tests marked xfail (route loading order)
- [ ] ML-100: Merge or close stranded session-82c/gemini-rerun branch (14 commits)

## Near-Term — Standalone Tool Suite (PRD-034)
See `docs/prds/034_standalone_tool_suite.md` for master plan.

- [ ] TOOLS-001: Date + Location Estimator Standalone — engine ready, zero blockers, 2-3 sessions
- [x] TOOLS-002: ML Service Extraction — Phase 1 (skeleton, Session 115), Phase 2 (deploy, Session 116), Phase 3 (wire pipeline, Session 117) DONE.
      Remaining: Phase 4 (clustering automation), Phase 5 (remove local ML deps from web Dockerfile).
      See `docs/architecture/ML_SERVICE.md` + `ml_service/` directory
- [ ] TOOLS-003: Face Compare Real-Time — depends on TOOLS-002, 1-2 sessions after
- [ ] TOOLS-004: NL Query + Chatbot — parser prototype exists, 3-5 sessions

## Near-Term — Platform
- [ ] Schema additions: previous_date_estimate, gedcom_token_count on gemini_api_calls (AD-211)
- [ ] Multi-GEDCOM support — merge/dedup architecture
- [ ] UX-042: Shareable identity page — no link to source photo (P1)
- [ ] UX-134: Mobile landing page horizontal overflow (P2)
- [ ] Second collection onboarding (Fox family photos — needs TOOLS-002 first)

## Future
- [ ] pgvector migration (DEFERRED until 5K+ embeddings)
- [ ] Frontend framework migration (NOT YET TRIGGERED — HD-022)
- [ ] GEN-001+: Multi-tenant architecture

## Reference
- Full backlog: `docs/BACKLOG.md`
- Standalone tools PRD: `docs/prds/034_standalone_tool_suite.md`
- ML service architecture: `docs/architecture/ML_SERVICE.md`
- Feature status: `docs/roadmap/FEATURE_STATUS.md`
- ML roadmap: `docs/roadmap/ML_ROADMAP.md`
- Lessons: `tasks/lessons.md`
