# Rhodesli Active Todo

Last updated: 2026-03-07 (Session 91b)

## Immediate — This Session (91b)
- [x] Supabase migrations executed (communities, life_events, notifications, global_person_links)
- [x] Life events seeded (5 events)
- [x] AD-206, AD-207, AD-208, AD-209 written
- [x] Collection name prompt fixed (AD-209)
- [x] main.py refactored: 26,100 → 9,346 lines, 16 route files
- [x] Notification triggers wired into save_registry()
- [ ] Discoveries extraction + UX overhaul (Track C — in progress)
- [ ] Test speed optimization merged (Track E — done, verify <30s)
- [ ] Browser verification with screenshots
- [ ] Session assessment + docs updates

## Post-Session 91b
- [ ] Deploy to Railway + browser verify all features
- [ ] Set SENTRY_DSN + POSTHOG_API_KEY on Railway
- [ ] Test DATA_SOURCE=postgres on Railway
- [ ] OPS-001: Custom SMTP for branded email (code ready, needs RESEND_API_KEY)
- [ ] Re-analyze Leon's Restaurant photo → verify Asheville (not Tampa)

## Near-Term
- [ ] PRODUCT-002: Face Compare Tier 2 — shared backend architecture (AD-117)
- [ ] ML-053: Multi-pass Gemini — low-confidence re-labeling
- [ ] Active learning pipeline
- [ ] Email notifications (PRD-028 P1+ — needs RESEND_API_KEY)
- [ ] Timeline integration for life events

## Future
- [ ] PRODUCT-003: NL Archive Query MVP — LangChain (AD-118)
- [ ] PRODUCT-004: Historical Photo Date Estimator Standalone
- [ ] OPS-002: CI/CD pipeline
- [ ] pgvector migration (embeddings stay as .npy for now)
- [ ] ML service extraction (separate FastAPI service)
- [ ] Frontend framework migration (NOT YET TRIGGERED — HD-022)
- [ ] Second collection onboarding (Fox family photos)

## Reference
- Full backlog: `docs/BACKLOG.md`
- Feature status: `docs/roadmap/FEATURE_STATUS.md`
- ML roadmap: `docs/roadmap/ML_ROADMAP.md`
- Lessons: `tasks/lessons.md`
