# Rhodesli Development Roadmap

Heritage photo identification system. FastHTML + InsightFace + Supabase + Railway + R2.
Current: v0.76.1 · ~3163 tests · 274 photos · 775 identities · 55 confirmed

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
- **Railway volume space** — auto_backups pruned to 5 (was 10), ENOSPC fixed in Session 61B

## Phase Summary

| Phase | Status | Details |
|-------|--------|---------|
| **A: Stabilization** | COMPLETE | All P0 bugs fixed, 103 tests added |
| **B: Share-Ready Polish** | ~95% complete | Remaining: OPS-001 (custom SMTP) |
| **C: Annotation Engine** | COMPLETE | Full submit/review/approve workflow |
| **D: ML Feedback** | ~90% complete | Remaining: ML-053 (multi-pass Gemini), FE-040-043 |
| **E: Collaboration** | ~70% complete | Remaining: Help Identify mode, analytics, moderation |
| **F: Scale & Generalize** | ~20% complete | Face alignment + GEDCOM in Supabase, API logging. Remaining: full Postgres ML data, CI/CD, Sentry |

For full feature checklists, see [docs/roadmap/FEATURE_STATUS.md](docs/roadmap/FEATURE_STATUS.md).
For ML-specific roadmap, see [docs/roadmap/ML_ROADMAP.md](docs/roadmap/ML_ROADMAP.md).

## Open Work (Prioritized)

### Immediate
- [ ] OPS-001: Custom SMTP for branded email sender (code ready, needs RESEND_API_KEY in Railway)
- [x] 2026-02-25: Retry 144 failed photos — 142/144 already retried ($2.04). 2 blocked by Gemini content safety.
- [x] 2026-02-25: UX-103 — Back nav, metadata overlay, mobile hamburger menu

### Near-Term
- [ ] PRODUCT-002: Face Compare Tier 2 — shared backend architecture (AD-117)
- [ ] ML-053: Multi-pass Gemini — low-confidence re-labeling
- [ ] FE-041: "Help Identify" mode for non-admin users
- [ ] Active learning pipeline

### Future
- [ ] PRODUCT-003: NL Archive Query MVP — LangChain (AD-118)
- [ ] PRODUCT-004: Historical Photo Date Estimator Standalone
- [ ] OPS-002: CI/CD pipeline
- [ ] PRODUCT-005: Face Compare Tier 3 — product grade
- [ ] GEN-001+: Multi-tenant architecture

See [docs/BACKLOG.md](docs/BACKLOG.md) for full details on each item.

## Planned Sessions

### Session 72: LoRA Fine-Tuning or Active Learning
- Depends on LoRA audit: 221 positive pairs is MARGINAL. Need admin to confirm candidates for Vida/BigLeon/Victor to reach 500+.
- Alternative: active learning pipeline, similarity calibration improvements

### Session 43: Life Events & Context Graph (deferred)
- Event tagging, connecting photos/people/places/dates
- PRD: docs/prds/011_life_events_context_graph.md

## Recently Completed

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
