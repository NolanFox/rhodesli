# Rhodesli Development Roadmap

Heritage photo identification system. FastHTML + InsightFace + Supabase + Railway + R2.
Current: v0.99.8 · ~4380 tests · 943 photos · 3433 identities · 95 confirmed

## Progress Tracking Convention
- `[ ]` = Todo | `[-]` = In Progress (add date) | `[x]` = Completed (add date)
- When completing a task, move to "Recently Completed" with date

## Current State & Key Risks
- User data migrated to Supabase Postgres (Session 59C). Face alignment also in Supabase (Session 64).
- **ML architecture: AD-110 Serving Path Contract** — web requests NEVER run heavy ML.
- Community sharing live on Jews of Rhodes Facebook group (~2,000 members)
- Gemini 3.1 Pro wired to Estimate (AD-139) — progressive refinement designed (AD-102)
- **Similarity calibration live**: isotonic regression, AUC=0.9577, calibrated scores in UI (AD-149/152)
- **API call logging**: Every Gemini call tracked in gemini_api_calls table (AD-152). gemini_config + response_summary now populated (AD-159 fix).
- **GEDCOM linking**: Admin can link identities to GEDCOM records via in-app search (AD-160)
- **Auto-clustering pipeline**: Two-tier system — Tier 1 auto-adds (<0.85), Tier 2 surfaces as Discovery suggestions (0.85-1.10). AD-179.
- **Railway volume space** — auto_backups pruned to 5 (was 10), ENOSPC fixed in Session 61B

## Phase Summary

| Phase | Status | Details |
|-------|--------|---------|
| **A: Stabilization** | COMPLETE | All P0 bugs fixed, 103 tests added |
| **B: Share-Ready Polish** | ~98% complete | Email notifications wired (Resend). Remaining: custom domain sender |
| **C: Annotation Engine** | COMPLETE | Full submit/review/approve workflow |
| **D: ML Feedback** | ~95% complete | Multi-pass foundation built. Remaining: batch execution, FE-040-043 |
| **E: Collaboration** | ~80% complete | Help Identify verified, email notifications. Remaining: analytics dashboard, moderation |
| **F: Scale & Generalize** | ~65% complete | Sentry, PostHog, CI/CD, structlog shipped. Remaining: pgvector (DEFERRED), ML service extraction |

For full feature checklists, see [docs/roadmap/FEATURE_STATUS.md](docs/roadmap/FEATURE_STATUS.md).
For ML-specific roadmap, see [docs/roadmap/ML_ROADMAP.md](docs/roadmap/ML_ROADMAP.md).

## Open Work (Prioritized)

### Immediate — Post-Session 92
- [x] 2026-03-08: Deploy v0.95.0 to Railway + browser verify all features (Session 92)
- [x] 2026-03-08: Set SENTRY_DSN + POSTHOG_API_KEY + RESEND_API_KEY on Railway (Session 92)
- [x] 2026-03-08: Leon's Restaurant fix — business name → GEDCOM owner lookup (AD-210, Session 92)
- [x] 2026-03-08: Full API call logging — prompt_text, full_response, gedcom_context columns (Session 92)
- [x] 2026-03-08: 10 P1/P2 UX bugs fixed (Session 92)
- [x] 2026-03-08: Email notifications via Resend (Session 92)
- [x] 2026-03-08: CI/CD foundation — .github/workflows/test.yml (Session 92)
- [x] 2026-03-08: Multi-pass Gemini foundation (rhodesli_ml/multi_pass.py, Session 92)
- [x] 2026-03-08: Active learning foundation (rhodesli_ml/active_learning.py, Session 92)
- [x] 2026-03-08: DATA-007 — Postgres migration complete (Session 93)
- [x] 2026-03-08: Batch GEDCOM re-analyze — 67/72 photos, AD-211, report (Session 93)
- [x] 2026-03-08: Observability verified — Sentry, PostHog, Resend all confirmed (Session 93)
- [ ] PERF-001: Test speed <30s (currently ~47s, floor limited by app import time)
- [x] 2026-03-10: DATA-008: Comprehensive data integrity audit + fixes (Session 96e-cont10)

### Near-Term — Standalone Tool Suite (PRD-034)
Community-agnostic versions of Rhodesli's ML tools. See `docs/prds/034_standalone_tool_suite.md`.

- [x] 2026-03-09: TOOLS-001: Date + Location Estimator Standalone — shipped as `/tools/estimate` (Session 95)
- [ ] TOOLS-002: ML Service Extraction — remove laptop dependency, automate pipeline, unblock face compare. 3-4 sessions. See `docs/architecture/ML_SERVICE.md`
- [ ] TOOLS-003: Face Compare Real-Time — depends on TOOLS-002 (ML service), 1-2 sessions after
- [ ] TOOLS-004: NL Query + Chatbot — parser prototype exists, needs Supabase wiring, 3-5 sessions
- [ ] TOOLS-005: Estimate v2 — GEDCOM upload + text context + geography retry (Nolan feedback). See `docs/BACKLOG.md`
- [ ] TOOLS-006: Self-service archive creation — "Create Your Archive" flow for community upload onboarding (Nolan feedback). See `docs/BACKLOG.md`
- [x] 2026-03-09: ROUTE-001: /facecompare → 301 redirect to /tools/compare (shipped post-Session 95)
- [x] 2026-03-10: COMMUNITY-001: Community data scoping — photos section, sidebar counts, admin bar scoped (Session 96 hotfix + 96d). Remaining: about page, tools photo picker.
- [-] 2026-03-09: COMMUNITY-002: Workspace switcher UX — admin dropdown to switch between communities (Session 95b)
- [x] 2026-03-10: COMMUNITY-003: Cross-community identity tagging — photo-derived identity sets + auto-tag identity_communities (AD-213, AD-216, Session 96c + 96d)
- [ ] COMMUNITY-004: "Shared person" indicator on identity cards — show when a person appears in multiple archives
- [ ] COMMUNITY-017: Default community routing — root URL defaults to Rhodes, risks accidental uploads from external users. Needs neutral landing + community selector. Blocks wider sharing. See `docs/BACKLOG.md`
- [x] 2026-03-10: COMMUNITY-005: Community-scoped sidebar counts — remove ML feature zeroing, enable Admin section for all communities (Session 96c + 96d proposals count)
- [x] 2026-03-10: COMMUNITY-006: Community-aware discoveries — filter by photo-derived identity set (Session 96c + 96d cross-community badges)

### Near-Term — Post-Upload Intelligence (PRD-037)
- [x] 2026-03-09: UPLOAD-001: Charlie Fox collection ingest — 636 photos via local pipeline (Session 96b)
- [x] 2026-03-09: PRD037-001: Auto-cluster after upload — wire clustering into `_background_ingest()` (Session 96b)
- [x] 2026-03-09: PRD037-002: GEDCOM triage page — surface top identities by face count for linking (Session 96b)
- [x] 2026-03-13: PRD037-004: Wire cluster review into community sidebar — speed-run mode with keyboard shortcuts (Session 100c)
- [x] 2026-03-14: PRD040-001: Batch cluster validation page — Google Photos-style select/confirm grid (Session 100f)
- [x] 2026-03-14: PRD039-002: Enriched speed-run — all faces, name input, merge search, recent actions, audit trail (Session 100f)
- [ ] PRD037-003: Batch Gemini with GEDCOM context — cost estimate UI, enriched prompts (future session)

### Near-Term — Longitudinal Face Modeling (PRD-038)
- [x] 2026-03-11: Session 97 foundation shipped — SDD, research pack, implementation bundle, prompt/state lineage spec, and merged-branch verification are wired into the harness
- [x] 2026-03-11: Phase 0: Eval repair + scorer-path unification
- [x] 2026-03-11: Phase 1: Local recalibration hygiene + label taxonomy
- [x] 2026-03-11: Phase 2: Prototype-bank longitudinal reranker in shadow mode
- [x] 2026-03-11: Phase 3: Active learning inside review UX
- [x] 2026-03-11: Phase 4: Adapter experiment track shipped with rollout gate still closed
- [ ] Phase 5: collect more Fox-family labels, rerun slice gates, and decide whether any matcher change graduates from shadow
- [ ] Scale path: keep PRD-038 local-first, but move offline scoring / retraining to queued cloud workers once local runtime, volume, or admin-concurrency thresholds are breached

### Near-Term — Infrastructure
- [ ] ENV-001: Dev/staging/prod environment separation — `SENTRY_ENVIRONMENT=development` in local `.env` (immediate), disable Sentry in local dev (medium-term), full env split (long-term). See OD-008, BACKLOG.md.
- [ ] OBS-001: Observability data retention — Sentry 90-day, PostHog 1-year. Export to Supabase if longer needed. See OD-009.
- [ ] AUDIT-001: Canonical actor attribution + person/photo history timelines — registry history still records `user_source` rather than actor identity, and entity-level timeline UI is still missing. Build canonical actor fields on mutations, Supabase-backed read paths, and admin timelines on `/person` + `/photo`. See `docs/BACKLOG.md`.

### Near-Term — Platform
- [ ] PRODUCT-002: Face Compare Tier 2 — consolidated into TOOLS-003 (depends on TOOLS-002 ML service)
- [ ] PRODUCT-003: NL Archive Query — consolidated into TOOLS-004 (PRD-032)
- [ ] Schema additions: previous_date_estimate, gedcom_token_count on gemini_api_calls (AD-211)
- [ ] Multi-GEDCOM support — merge/dedup architecture for community GEDCOM uploads

### Near-Term — Workspace & Onboarding (PRD-036)
Self-service workspace for users. See `docs/prds/036_workspace_onboarding.md`.

- [ ] WORKSPACE-001: Personal archive auto-creation on signup — 1 session
- [ ] WORKSPACE-002: Sharing mode UX (Help Identify for members) — 1-2 sessions, depends on WORKSPACE-001
- [ ] WORKSPACE-003: Add photos to community flow — 1-2 sessions, depends on WORKSPACE-001
- [ ] WORKSPACE-004: Anonymous contributions with session tracking — 1 session
- [ ] WORKSPACE-005: Community discovery page (`/communities`) — 1 session
- [ ] WORKSPACE-006: Per-community permissions enforcement — 2 sessions

### Future Evaluation: Frontend Framework Migration
- **Trigger:** If 3+ JS embeds require shared state, or mobile UX audit scores below acceptable after Session 74
- **Options:** React SPA with FastAPI backend, or Next.js with Supabase direct
- **Queued by:** HD-022 (Session 74)
- **Status:** NOT YET TRIGGERED

### Future
- [ ] PRODUCT-004: Historical Photo Date Estimator Standalone — consolidated into TOOLS-001 (PRD-034)
- [ ] PRODUCT-005: Face Compare Tier 3 — product grade, consolidated into TOOLS-002 (PRD-034)
- [ ] PRODUCT-006: Interactive Photo Chatbot — consolidated into TOOLS-003 (PRD-034)
- [ ] ML service extraction — consolidated into TOOLS-002 (`docs/architecture/ML_SERVICE.md`)
- [ ] pgvector migration (evaluation doc written, DEFERRED until 5K+ embeddings)
- [ ] GEN-001+: Multi-tenant architecture

See [docs/BACKLOG.md](docs/BACKLOG.md) for full details on each item.
See [docs/prds/034_standalone_tool_suite.md](docs/prds/034_standalone_tool_suite.md) for standalone tools master plan.

## Planned Sessions

### Session 91: Ship PRD Backlog + Platform Foundation (6 parallel tracks) — COMPLETE
- All 6 tracks shipped and merged. See Recently Completed.
- Prompt: docs/prompts/session-91-prompt.md

### Session 92: Ship Everything — COMPLETE
- 6 parallel worktree tracks, all merged. See Recently Completed.
- Prompt: docs/prompts/session-92-prompt.md

### Session 93: Close All Deferrals — COMPLETE
- DATA-007 Postgres migration complete (tables, backfill, flip)
- Observability verified (Sentry, PostHog, Resend)
- Batch GEDCOM re-analyze (67/72 photos, AD-211)
- GEDCOM Reanalysis Report (docs/ml/GEDCOM_REANALYSIS_REPORT.md)
- Prompt: docs/prompts/session-93-prompt.md

### Session 104: Fix Contributor UX + Claude Benatar Photos — COMPLETE
- P0 upload pipeline fixes: 404 after approval, anonymous attribution, missing thumbnails
- Auto-approve for logged-in contributor Compare uploads
- Robert Mattatia photos ingested (2 photos, 20 faces, R2 uploaded, production verified)
- Gemini deep comparison: 2.5 Pro (9/10) + 3.1 Pro (8.5/10) confidence, both logged
- Lesson 140 (hooks exit 0 are advisory), hook threshold fix
- 10 new tests, 3 BACKLOG items (TOOLS-007, TOOLS-008, OBS-002)
- Claude Benatar response message drafted
- Prompt: docs/prompts/session-104-prompt.md

### Session 100d: Contributor Experience + Upload Fixes — COMPLETE
- 6 pending approval workflow fixes (HTMX swap, batch approve, auto-confirm)
- Compare upload data loss prevention (3 safety fixes)
- Staging thumbnails preserved for pending uploads
- Email notifications wired into annotation approval
- My Contributions page enhanced with uploads + stats
- Contributor sidebar simplified (Help Identify + My Contributions)
- Quickstart guide for Claude Benatar
- Data flow audit (docs/architecture/DATA_FLOW.md)
- 5 new BACKLOG items (UX-061, DATA-013-016), Lessons 135-138
- 4216 app tests pass, production verified

### Session 100b: Dogfood Fix Sprint — COMPLETE
- Fixed 26 user-reported dogfood issues from Session 100
- BUG 1: Jacob Cohen/Jacob Franco bbox overlap — FIXED
- BUG 2: Photo metadata save duplicate routes — FIXED
- Dismissed faces visual treatment — FIXED

### Session 96c: Community-Scoped Review + Cross-Community Identity Pipeline — COMPLETE
- Photo-derived community identity sets (AD-216)
- Admin sections ungated for all communities
- Community-aware discoveries pipeline
- Supabase backfill (2533 identities)
- 81 new tests, browser verified 10/10
- Prompt: docs/prompts/session-96c-prompt.md

### Session 95: Fox MVP + Standalone Tool Suite — COMPLETE
- Multi-community platform: `/c/{slug}/` routing, Fox Family Archive live
- Standalone tools: `/tools` hub, `/tools/estimate`, `/tools/compare`
- Community infrastructure: 3 new Supabase tables, migration, admin CRUD
- Upload improvements: 200 cap, TIFF conversion
- 82 new tests, 2491 total pass, browser verified
- Prompt: docs/prompts/session-95-prompt.md

## Recently Completed

- [x] 2026-03-15: **v0.99.8 — Session 104b**: P0 Face Tagging Fix. Root cause: Supabase anchor_ids stored as JSON text strings instead of JSONB arrays — load_from_postgres() iterated characters instead of face IDs. Fix: _ensure_list() read guard, _ensure_list_for_supabase() write guard, 20 Supabase rows repaired. Hook enforcement audit: 4 broken hooks fixed (all now exit 2). test-gate.sh fast mode uses targeted core tests. Lessons 142-143. 3 new tests, 4380 app tests pass. Both Robert Mattatia photos browser-verified on production. Deploy SUCCESS.

- [x] 2026-03-15: **v0.99.7 — Session 104**: Fix Contributor UX + Claude Benatar Photos. P0 upload pipeline fixes: 404 after approval (compare_mode detection), anonymous attribution (auth gate removed), missing thumbnails (R2 path fix). Auto-approve for logged-in contributor uploads. Robert Mattatia photos ingested (2 photos, 20 faces, Congo group + family group). Gemini deep comparison: 2.5 Pro 9/10, 3.1 Pro 8.5/10 confidence — ML false negative from periocular occlusion. Both API calls logged. Lesson 140 (hooks exit 0). Pre-work hook threshold 2→1. 10 new tests, 4377 app tests pass. 2/2 photos browser verified. Deploy SUCCESS.

- [x] 2026-03-15: **v0.99.6 — Session 103**: ML Pipeline Execution + Triage Fixes. PRD-046 ml_runs + ml_proposals Supabase tables. Baseline clustering: 470 proposals (86 VERY HIGH, 384 HIGH). Reranker shadow comparison: Neutral (0 changes, not activated). compare_ml_runs.py diff tool. Community-scoped suggestions (find-similar + speed-run). P0 fixes: FB-168 tag search assignment, FB-150 clickable suggestion thumbnails. P1 fixes: FB-153 identify community lookup, FB-159/160 similar panel CONFIRMED ranking, FB-162 tag search prioritization. Session 102 test gaps closed (TEST-003, TEST-004, OBS-003). 14 P2 BACKLOG entries. 61 new tests, 4357 app tests pass. 5/5 browser verified. Deploy SUCCESS.

- [x] 2026-03-14: **v0.99.5 — Session 102**: Performance + Speed Loop fix + Navigation wiring. BUG-001 P0 fix (face lookup cache cleared in Postgres save path). DATA-019 community reassignment (Rhodes photos removed from Fox Family). DATA-020 Postgres name protection guard. Connected triage navigation (Identify Mode → Speed Loop, face click → per-face, back-to-queue). GEDCOM search optimization (trigram index, 3-char min). Similar panel community scoping. PRD-045 Active Learning Feedback Loop + PRD-046 ML Run Provenance. Unwired route detection test (TEST-002). 10/12 browser checks PASS. Health: 1922 identities, 941 photos. Session froze during Phase 5, recovered by second instance. Phase 8 (triage sprint) deferred to next session.

- [x] 2026-03-14: **v0.99.4 — Session 101**: Fox Triage P1 Fixes + Performance. GEDCOM link auto-renames, cross-community badges, CONFIRMED badge fix, non-blocking Supabase sync. 22 feedback items from triage sprint (FB-120–FB-143). 7/7 browser verified. 3 deploys SUCCESS.

- [x] 2026-03-14: **Session 100g**: Session 100 closeout. 5 BACKLOG entries created (PERF-003/004, UX-073-075). Browser verified: speed-run enrichment panel, batch cluster validation grid, Yaacov Franco person page. 1 new issue found (UX-076 reject advance). Session 100 officially complete.

- [x] 2026-03-14: **v0.99.3 — Session 100f**: Cluster validation & enrichment overhaul. Batch cluster validation page shipped (PRD-040) with Select All, face count filters, community scoping. Enriched speed-run: all faces visible (no overflow cap), post-confirm name input + merge search + suggested matches, recent actions sidebar with undo. Audit trail: `log_user_action()` on all 5 speed-run actions with identity_id, face_count, mode=speed-run. UX polish: 112px crops, cumulative progress counter, undo banner with context, workflow guides, Y key 300ms debounce, next-card pre-fetch. 46 new tests, 4276 app tests pass. 13/21 FB items from Session 100e fixed, 8 deferred with BACKLOG entries.

- [x] 2026-03-13: **v0.99.2 — Session 100d**: Contributor experience overhaul + upload pipeline fixes. Email notifications wired into annotation approval. My Contributions page enhanced with stats + uploads. Contributor sidebar simplified (Help Identify + My Contributions replaces admin Review section). 6 pending approval workflow fixes, 3 compare upload safety fixes, staging thumbnail preservation. Data flow audit (docs/architecture/DATA_FLOW.md). 5 new BACKLOG items, 4 new lessons. Quickstart guide for Claude Benatar. 4216 app tests pass. Production verified.

- [x] 2026-03-13: **v0.99.1 — Session 100c**: Speed-run cluster review mode shipped (PRD-039). Keyboard shortcuts Y/N/S/D, auto-advance, progress bar, community-scoped filtering. confirm-all/reject-all Postgres-compatible. Yaacov Franco + Solomon Galante data fixes synced. 10 new tests, 4163 app tests pass. Browser verified 6/6 PASS. 2 deploys SUCCESS.

- [x] 2026-03-11: **v0.98.0 — Session 97**: PRD-038 longitudinal ML foundation shipped. Repaired mixed-schema evals, rebuilt the longitudinal baseline, unified scorer paths, added prompt-manifest lineage, hardened local recalibration with reversible labels, shipped a prototype-bank reranker in shadow mode, added active learning in review UX, and built a frozen-embedding adapter experiment harness. Final merged-branch verification: `pytest tests/ -x -q` (`4116 passed, 21 skipped`) and `pytest rhodesli_ml/tests/ -x -q` (`578 passed, 2 skipped`). Rollout gates remain closed for matcher changes pending stronger age-gap evidence.
- [x] 2026-03-11: **v0.97.12 — Session 96f-cont1**: Follow-up provenance visibility + browse-safe admin return cleanup. Workstation and public photo cards now surface uploader/archive-entry provenance directly, public `/photos` now carries the same tie-break metadata as workstation photo lists, photo detail provenance moved higher in the metadata stack, and admin return links from public identify/person pages now land in community-aware browse-mode queues. Verified with targeted slices (`43 passed`, `133 passed`), full gates (`4110 passed, 7 skipped`; `566 passed`), and live `/health` (`200`, `1932` active identities, `939` photos).
- [x] 2026-03-11: **v0.97.11 — Session 96f**: Live UX closeout after the data reconciliation. Fixed the wrong upload success destination (`/?section=to_review&view=browse`), restored a first-run AI Analysis entry point for unlabeled admin photo views, made archive provenance explicit with full timestamps and missing-uploader wording, stabilized upload-date tie ordering using archival `photo_index.json` order, clarified public/workstation navigation (`Public Page`, `Back to Workstation`), and hardened attribution by dual-writing `log_user_action()` to Supabase plus logging photo metadata edits and rename flows with actor data. Verified targeted audit slices (`8 passed`) in addition to the earlier `pytest tests/ -x -q` (`4102 passed`) + `pytest rhodesli_ml/tests/ -x -q` (`566 passed`). Live deploy `705b0eff` SUCCESS.

- [x] 2026-03-11: **v0.97.10 — Session 96e-cont12**: Production reconciliation + root-cause closeout. Closed the remaining local structural drift (`157` orphans, `122` merge chains, `1` duplicate face, `2` ghost refs), finished embedding repair (`10` missing -> `0`), reconciled production with the audited `3412`-identity / `938`-photo snapshot, and pruned `112` stale Supabase identity rows only after exporting them to a checked-in JSON backup artifact. Also restored the app gate by making `/timeline` person filters timeline-backed. Verified `pytest tests/ -x -q` (`4098 passed`) + `pytest rhodesli_ml/tests/ -x -q` (`566 passed`). Deploy SUCCESS.

- [x] 2026-03-11: **v0.97.9 — Session 96e-cont11**: Stability closeout + audit trail. Fixed the remaining post-cont10 regressions: structured-anchor merge safety, append-only history bypasses, embeddings-first photo cache hiding valid face records, and ML early-stopping flake. Verified `pytest tests/ -x -q` (`4091 passed`) and `pytest rhodesli_ml/tests/ -x -q` (`566 passed`). Confirmed InsightFace had been run earlier and reduced 124 missing embeddings to 2 archival face records. Live verified: Holocaust collage now shows `11 people detected · 10 identified` and preserves `Caden Franco Sadis`; wedding newspaper now preserves its archival unmatched face record. Reversible audit trail added via before/after/delta artifacts. Deploy SUCCESS.

- [x] 2026-03-10: **v0.97.8 — Session 96e-cont10**: Data Integrity Audit + Fixes. Comprehensive audit found and fixed: 1 duplicate face (critical), 3 CONFIRMED placeholders, 121+ merge chains, 157+ orphan faces, 637 missing upload_dates, 2 ghost faces. Prevention: CLI --upload-date/--uploaded-by args, auto-default upload_date, merge cross-list dedup, admin force-state API. Lessons 118-121. Data integrity audit script with --fix. Browser verified: Person 2973 SKIPPED, Fox Family 635 photos. Deploy SUCCESS.

- [x] 2026-03-10: **v0.97.7 — Session 96e-cont7**: PRD-038 Longitudinal Face Modeling. 960-line PRD across 5 files. Recalibration architecture analysis. Upload date sort fix (backfill in resync).

- [x] 2026-03-10: **v0.97.6 — Session 96e-cont4**: Upload UX + Deploy Verify. Two-step upload flow (select → preview → upload). Upload 500 crash fix (PostHog). Supabase 1149 orphans deleted. Community scoping: proposals sidebar, proposals API, discoveries Help Identify, duplicate face filter, name consistency. 6 new tests. Browser verified 5/6. Deploy SUCCESS. Known: proposals API doesn't include proposals.json entries.

- [x] 2026-03-10: **v0.97.4 — Session 96e**: Fox Family Stabilization Complete. Face grouping (813 merges, 2009→1196 INBOX). 2115 proposals regenerated (1122 Fox-filtered). Proposals.json path fix (STORAGE_DIR on Railway, Lesson 114). GEDCOM triage includes INBOX identities. Registry TTL cache (30s). Discoveries proposal-only (no timeout). Cross-community badge fix. 1622 new INBOX identities created. Browser verified: New Matches 1497, Discoveries 568, Proposals 1122, Cluster Review 67 identities. 3908 tests pass.

- [x] 2026-03-10: **v0.97.3 — Session 96d**: Fix Fox Family to Usable State. All 7 COMMUNITY bugs fixed (007-014). Nav links use community prefix. Proposals surfaced in sidebar (35 proposals). Cluster review community-scoped. Cross-community "From [Community Name]" badges. Proposal match info ("Matches [Name] (XX%)"). Face crop responsive sizing. Photo filename display. Name truncation fix. 6 pre-existing test failures fixed. Browser verified. Known: COMMUNITY-015 internal links.

- [x] 2026-03-09: **v0.97.2 — Session 96c**: Community Identity Pipeline + Data Integrity. Photo-derived identity sets (AD-216). Admin sections ungated for all communities. ML feature counts restored. Community-aware discoveries. David Capeloto photo restored (Lesson 78). Fox Family admin view fixed. Dismissed section grid layout. Supabase backfill (2,533 identities). Data integrity validator + orphan detection tests. 81 new tests. Browser verified 10/10. Known issues: COMMUNITY-007/008 sidebar counts.

- [x] 2026-03-09: **v0.97.1 — Session 96**: Community Data Scoping Hotfix. Photos section, upload sidebar counts, and admin bar now community-scoped. Merge conflict resolved. Fox Family pages no longer show Rhodes data. Bulk upload workflow documented (636 Charlie Fox photos via local pipeline). BACKLOG: UPLOAD-001 bulk import, about page community content.

- [x] 2026-03-09: **v0.97.0 — Session 95**: Fox MVP + Standalone Tool Suite. Multi-community platform (CommunityMiddleware, `/c/{slug}/` routing, Fox Family Archive at `/c/fox-family`). Standalone tools hub at `/tools` with Date Estimator and Face Compare. 3 new Supabase tables (photo_communities, identity_communities, upload_batches). 295 photos + 894 identities migrated to Rhodes community. Upload cap 50→200, TIFF auto-conversion. Community admin CRUD. URL redirects for /estimate and /compare. Session 94 branches merged. 82 new tests. 2491 tests pass. Browser verified 8/8 routes.

- [x] 2026-03-08: **v0.96.0 — Session 93**: Close All Deferrals. DATA-007 complete (identities/photos/photo_faces tables, 894+295+981 rows backfilled, DATA_SOURCE=postgres on Railway). Supplementary migration (date_labels 271, photo_locations 268, birth_year_estimates 32). Observability verified (Sentry 5 issues, PostHog events, Resend email). Batch GEDCOM reanalysis (67/72 photos, Gemini 3.1 Pro, ~$2.66, 91% high confidence, avg 4.5yr ranges). GEDCOM Reanalysis Report (10-section analysis). AD-211. 4283 tests pass.
- [x] 2026-03-08: **v0.95.0 — Session 92**: Ship Everything — Close All Gaps. 6 parallel worktree tracks. Observability (Sentry + PostHog, 4 events). Bell icon sidebar fix. Email notifications (Resend). 10 P1/P2 UX fixes (source photo link, auto-scroll, 404 styling, birth year race, CTA standardization, tooltip, dropdown, double admin bar). Leon's GEDCOM fix (AD-210, business name → owner lookup). Full API logging (prompt_text, full_response, gedcom_context). Multi-pass + active learning foundations. NL query parser. Compare v2 stub. CI/CD (.github/workflows/test.yml). 3 PRDs + 3 architecture docs. Timeline life events. 4172 tests pass.
- [x] 2026-03-07: **v0.94.1 — Session 91b**: Complete Everything — Refactor + Discoveries + Notifications + Collection Fix. main.py 26,100 → 9,383 lines (64% reduction, 17 route files). 5 new route files: identity_routes, page_routes, engagement_routes, relationship_routes, discoveries_routes. Supabase tables created (communities, life_events, notifications, global_person_links). Life events seeded (5 events). Notification triggers wired into 7 confirm routes. Discoveries extraction + UX overhaul (recency sort, confidence tier labels, navigation). AD-209: collection name is weak provenance. 5 parallel worktree tracks. 3518 tests pass.
- [x] 2026-03-07: **v0.94.0 — Session 91**: PRD Backlog + Platform Foundation. 6 parallel worktree tracks. PRD-028 notifications (bell icon, /notifications, event triggers). PRD-027 Phase A R2 backup/restore. PRD-011 life events (CRUD, photo/person linking). PRD-029 photo backs completion (media group API, browse filter, badges). PRD-027 B/C Postgres read flip (DATA_SOURCE feature flag, load_from_postgres). GlobalPersonID schema (communities + global_person_links). Observability (Sentry, PostHog, structlog, all env-gated). PRD-030 + MULTI_TENANT.md. ~2265 lines new tests. 3502 tests pass.
- [x] 2026-03-06: **v0.93.1 — Session 90b (complete)**: Fix Sorting + Shadow Writes + Route Extraction + Back Photo. Upload date sorting fixed (296 photos patched). Leon's Restaurant → Tampa, FL. Supabase shadow writes fully wired (save_registry + save_photo_registry fire-and-forget). Route extraction: person_routes.py (1,632 lines), main.py 34K→26K. Back-photo upload (PRD-029). Test fixes for extracted routes. 22 commits. ~3915 tests.
- [x] 2026-03-04: **v0.92.0 — Session 89**: Wire GEDCOM into Location Estimation. AD-201: Unified Gemini prompt (interactive uses enriched prompt). AD-202: Admin re-analyze button. API call logging on every interactive Gemini call. Batch reprocessing script. Asheville photo pipeline ready. 24 new tests. ~4146 tests.
- [x] 2026-03-04: **v0.91.1 — Session 88**: Fix Scoring & Card Failures. Isotonic calibrator crash fixed, sigmoid CDF priority. Batch NN override removed. Compare link params fixed. Accordion headers with match preview. Admin badge → gear icon. Discovery cards: match_info_bar, distance, co-occurrence. HD-024 harness improvements (ruff format, dynamic hooks, test gate). Browser verified 5/5. ~4122 tests.
- [x] 2026-03-04: **v0.91.0 — Session 87**: Compare & Discoveries UX Overhaul. AD-200: Unified confidence scoring (12+ paths → 1). Compare best-matches summary. Shareable result "Could this be [Name]?" redesign. Discoveries sort/filter by confidence + photo. Identity card "Faces" button + visible detach. 63 new tests. ~4122 tests.
- [x] 2026-03-04: **v0.90.0 — Session 86b**: Route Extraction + Deferred UX Fixes. Extracted compare (4,642 lines) and estimate (739 lines) routes from main.py. UX-038: merged identity POST guards (~15 routes). UX-053/056/057: estimate photo preview, CTAs, form reset. Deploy fix for FastHTML serve() duplicate module. 13 new tests. ~4059 tests.
- [x] 2026-03-04: **v0.89.0 — Session 86**: P1 UX Fixes + MLS Experiment + Gemini Completion. Merge confirmation dialogs (UX-037). Person page inline admin controls (UX-039). Confirmed face labels visible for all users. Connected navigation (person→tree/map/timeline/compare). MLS vs Euclidean resolved: Euclidean wins AUC 0.9903 vs 0.9454 (AD-027). Gemini 271/271 complete. app/utils.py extraction. 38+ new tests. ~4023 tests.
- [x] 2026-03-03: **v0.88.0 — Session 85c**: Universal Comparison Workspace. Two-slot design (Source + Compare With), all entity combinations, multi-target (up to 5), unified search (people + photos), per-match context (target's best %, rank), CSS animations (bar glow, skeleton loading, face collapse), backward-compat URLs. PRD-026. 36 new tests (99 total compare). Browser verified 14/14 PASS. ~3985 tests.
- [x] 2026-03-03: **v0.87.1 — Session 85b**: Compare Navigation + PRD-025 Gap Closure. Archive-to-compare flow (from-photo endpoint), direct compare URLs, photo/person page navigation links, reference context on shareable result page, merge/not-same admin actions on result page. Isaac Cohen E2E verified with shareable link. Disk-full resilience. 11 new tests (33 total compare). ~3985 tests.
- [x] 2026-03-03: **v0.87.0 — Session 85**: Fix Compare — Unified Upload Pipeline. Compare uploads now use same staging → process_directory pipeline as Upload page. New vs-person comparison with search + per-face scores. Enhanced result page with confidence bars (dual encoding), person/photo links. Removed SSE interceptor for HTMX-based flow. 9 new tests (22 total compare). ~3985 tests.
- [x] 2026-03-02: **v0.86.1 — Session 84**: Unified Face Cards + Restore Find Similar. Browse grid uses unified identity_card (DD-006). Find Similar wired to full neighbors_sidebar with Select All/Merge/Not Same/Load More/Search/Rejected. Triage buttons on browse cards. Share on all named identities. Card expansion animation. Help Identify panel full-width fix. 25 tests (up from 10). ~3976 tests.
- [x] 2026-03-02: **v0.86.0 — Session 83a**: Critical UX Fixes (User Feedback Response). Display Name field (AD-196). Help Identify wired to annotations (AD-197). Compare result 404 fix (AD-198). Admin card search filter (AD-199). Origin: Claude Benatar feedback. 12 new tests. ~3961 tests.
- [x] 2026-03-02: **v0.85.1 — Session 82f**: Completion Audit. Exhaustive audit of Session 82 (82a-82e): 20 features shipped, 0 broken. Fixed Similar button hit area (38x16px → 46x24px). Formally deferred 5 features (UX-201-204, ML-100). 82b (Codex) never executed, 82c branch stranded. Browser verified 16/16 PASS. 3949 tests.
- [x] 2026-03-01: **v0.85.0 — Session 82e**: UX Feature Sprint. Mobile hamburger fix (768px breakpoint). Masonry photo grid (CSS columns, natural aspect ratios). Help Needed page (/help, top 50 unidentified faces). Share for Help OG cards (og:image face crop). Identify Mode focus state (toggle, pulse animation, "?" badges). Landing page help section. Browser verified 7/7 PASS. 22 new tests. ~2942 tests.
- [x] 2026-03-01: **v0.83.0 — Session 81**: Connected App — Tree, Map, Location, Face Labels. Photo→Tree smart nav (BFS subtree, nuclear family detect). Face identity labels (clickable links). Location estimate display (Leaflet maps, confidence badges). GEDCOM-enriched location prompts (AD-192, Asheville benchmark). Relationship viz (thicker lines, hover, generation bands). Matilda GEDCOM fix. Browser verification 12/12 PASS. AD-192/193. 8 parallel subagents across 2 rounds. ~3030 tests.
- [x] 2026-02-28: **v0.82.1 — Session 80 cont.**: Parallel track improvements. Tree: photo cycling, expand-any-node, multi-spouse, rounded-rect faces (DD-005). Cards: share button restored, multi-face gallery. GEDCOM: 21 new matches (56 total). Docs: DD-005, AD-190/191. 5 parallel worktree subagents. ~2933 tests.
- [x] 2026-02-28: **v0.82.0 — Session 80**: Fix Everything — Tree + Face Cards + UX. Tree: complete D3 rewrite with card-based layout, T-shape connections, expand arrows, search (AD-185). Graph unification: GEDCOM xrefs→UUIDs. Expand fix: source person in response. Face cards verified. Compare deferred AD-187. Lesson 89. ~3272 tests.
- [x] 2026-02-28: **v0.81.0 — Session 79**: Fix Three Visible Failures. Tree: CardSvg replaces broken CardHtml (AD-184), 13-node family renders with photos. Face cards: compact redesign, face 60%+ of card, icon-only actions. Tier 2 threshold 1.10→1.30 (AD-183, Nolan approved), 617 suggestions surfaced. No data loss found for Big Leon/Nace. Mobile verified. 3784 tests.
- [x] 2026-02-28: **v0.80.0 — Session 78**: Integration + Fix-Everything. Stop hook fixed (exit 2 blocking). 2 ML test failures resolved. Per-face dedup implemented. GEDCOM→Supabase sync (1,019 rels, pagination fix). PRD-024 auto-clustering. Threshold analysis: Tier 2 ceiling 1.10 provably too low. 31 new tests. Visual audit: 9 pages PASS. ~3792 tests.
- [x] 2026-02-28: **v0.79.1 — Session 77**: Compare Rebuild Follow-up. Pair compare enriched with cross-photo face summaries and archive best-hit matches (AD-181). Compare uploads auto-queued to admin pending review (AD-182). Golden test suite in tests/test_compare.py. Session provenance: audit log + assessment.
- [x] 2026-02-28: **v0.79.0 — Session 76a**: Auto-Clustering + Discoveries Redesign + Face Cards. Two-tier auto-clustering pipeline (AD-179): Tier 1 (<0.85) auto-adds, Tier 2 (0.85-1.10) surfaces as suggestions. Discoveries page redesigned as ML audit trail with confirm/undo/reject. Browse cards face-dominant (200px min). Backfill: 0 Tier 1, 7 Tier 2, 652 no match. 15 new tests + 4 regression fixes. ~3742 tests.
- [x] 2026-02-28: **v0.78.0 — Session 75**: Post-Gemini Cleanup + Tree Upgrade. Data integrity: restored 19 UUID relationships, reverted 9K lines of key-reorder noise. GEDCOM date parser: regex replaces broken [:4] slice (AD-175). Tree rewrite: CardHtml API, bidirectional rels, 718 people, siblings render. xdist fix: atomic route reordering + timeout (0 failures). 38 new tests. AD-175/176/177/178. ~3216 tests.
- [x] 2026-02-27: **v0.77.1 — Session 73**: Cleanup + Share-Readiness. File naming convention enforced, 3 legacy scripts removed, stop hook fixed for merge sessions. Enter key 400ms hack replaced with htmx:afterSettle. Share-readiness: 10/10 smoke test PASS. Status: READY.
- [x] 2026-02-27: **v0.77.0 — Session 72**: Harness Fix + ML Similarity Calibration. Test tiering (make test-fast <30s, 2166 tests via pytest-xdist). Branch enforcement hooks. Merge script. MLP calibrator on frozen embeddings (AUC 0.84, F1 0.75). Regression gate: NO-SHIP on ECE. Shadow scoring: 96.3% agreement, calibrator more conservative. AD-174. ~3180 tests.
- [x] 2026-02-27: **v0.76.1 — Session 71D Merge**: Discoveries fix + harness enforcement. Merged 2 worktree branches. Discoveries: confidence labels replace "54% match", clickable navigation, threshold 1.05 (Nace surfaces), photo context. Harness: worktree enforcement scripts. AD conflict resolved (AD-171/172/173). Browser verified. ~3163 tests.
- [x] 2026-02-26: **v0.76.0 — Session 71**: UX Dogfooding Fixes + GEDCOM Integration + Harness Enforcement. Track A: 6 UX fixes (quality labels, face card size, enter key, analysis sections, name truncation, loading indicator). Track B: GEDCOM search ranking with date/Rhodes bonuses, match strength labels, pagination, tree buttons on identity cards. Track C: Mechanical subagent commit enforcement (HD-021), AD-170, Lesson 88, parallel sessions doc. 3 parallel tracks. ~3146 tests.
- [x] 2026-02-25: **v0.75.0 — Session 70**: UX Fix Pass + Multi-Tool Harness + Auto-Eval Loop. 13 UX issues addressed (2 HIGH, 5 MEDIUM, 6 LOW). Multi-tool harness: AGENT_HARNESS.md + 5 adapter files + sync script (HD-019). Auto-eval loop: run_session.sh rewritten for 6-stage orchestration (HD-020). Parallelization skill validated. 3 parallel worktree subagents. 28 new tests. ~3671 tests.
- [x] 2026-02-25: **v0.74.0 — Session 69**: Bug Fixes + Design Audit + Discovery Notifications. BUG-1: Create Identity 500 fix (AD-168). BUG-2: Gatekeeper confirmed by design (AD-169). BUG-3: Collection dropdown UX. Editorial archival design (DD-001/002). Discovery notification system (DD-003). Parallelization skill. 3 parallel worktree subagents. ~3595 tests.
- [x] 2026-02-25: **v0.73.1 — Session 68**: Hook Hardening + LoRA Audit + UX-103 + Photo Retry. Python stop gate replaces bash grep (AD-167). PreCompact recovery strategy. UX-103: back nav + metadata overlay + mobile menu. LoRA audit: 221 positive pairs, MARGINAL. Photo retry: 142/144 done, 2 blocked by Gemini content safety. 3 parallel worktree subagents. ~3064 tests.
- [x] 2026-02-25: **v0.73.0 — Session 67**: Hook Enforcement System. Stop hook blocks session end until assessment exists + phases logged. PreCompact blocks /compact. UserPromptSubmit injects parallelization reminder. Session runner script for headless phase isolation. ux-reviewer: 8 new UX issues (1 P1). session-evaluator: independent eval found Phases 4/5/6 of session 66 were PARTIAL (self-assessment rated PASS). AD-166. ~3588 total.
- [x] 2026-02-25: **v0.72.1 — Session 66b**: CRITICAL Upload Fix. Root cause: cache staleness + R2 upload race (AD-165). Background thread now does R2 upload + cache invalidation. embeddings.npy safety gate added. Verified in production: 2 faces uploaded, sidebar counts updated immediately. 10 new tests. ~3588 total.
- [x] 2026-02-24: **v0.72.0 — Session 66**: Parallel Worktrees + Enrichment Validation + GEDCOM Admin + Portfolio. First parallel worktree execution (3 subagents). 7 harness subagents. Session log archival (INDEX.md). GEDCOM admin UI with version management (AD-164). Enrichment validation: identity priority bug fix, 400-3700 GEDCOM tokens confirmed. Portfolio writeup. 25 new tests. ~3578 total.
- [x] 2026-02-24: **v0.71.0 — Session 65d**: Disk Space Fix + GEDCOM Versioning + Harness. Disk: .dockerignore saves ~400MB, startup cleanup, backup pruning (AD-162). All 3 uploads verified in Chrome browser. GEDCOM temporal versioning: version tracking, field-level diffs, enrichment queue, current_* views (AD-163). Stop hook + enhanced eval script. ~3553 tests.
- [x] 2026-02-24: **v0.70.0 — Session 65c**: Upload Fix (MANDATORY) + Verification Sweep + Harness. Root cause: subprocess OOM from double model loading. Fix: thread shares hybrid models (AD-161). All 3 upload surfaces verified in production. GEDCOM linking verified end-to-end. Harness: assessment mandate, prompt template, eval script. ~3475 tests.
- [x] 2026-02-24: **v0.69.0 — Session 65b**: GEDCOM Linking UX + Enrichment Fix. Production verification (5/6 PASS). GEDCOM ↔ Identity linking with fuzzy search (AD-160). Enrichment pipeline fix: first_order variant for full family context (AD-159). API call logging: gemini_config + response_summary populated. 28 new tests. ~3521 total.
- [x] 2026-02-23: **Session 64c**: Concerns Resolution. Harness validation (4 hooks, 6 skills, 39 rules audited). Exception narrowing (12 handlers narrowed). API cost tracking verified. Calibrated scores verified end-to-end. AD-158. +4 new tests. ~3472 total.
- [x] 2026-02-23: **v0.68.0 — Session 65a**: Upload Fix + Compare Overhaul + UX Polish. Upload subprocess death detection + timeout. Two-photo face comparison (/compare/pair). Face overlay toggle (admin ON, non-admin OFF). Prompt fidelity audit (AD-159). 24 new tests. ~3493 total.
- [x] 2026-02-23: **v0.67.1 — Session 64b**: Execute What 64 Deferred. Supabase tables created. 127 alignments migrated. GEDCOM context builder. Dry-run 3 photos. AD-153-157. 8 new tests. ~3468 total.
- [x] 2026-02-23: **v0.67.0 — Session 64**: Verify, Migrate, Harden. Harness hardening (5 skills, 3 rules, 3 hooks). Face alignment → Supabase. gemini_api_calls tracking. Centralized model config. Combined pipeline. Calibrated scores in UI. Recalibration hooks wired. AD-152. ~50 new tests. ~3450 total.
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
