# Rhodesli Development Roadmap

Heritage photo identification system. FastHTML + InsightFace + Supabase + Railway + R2.
Current: v0.91.0 · ~4122 tests · 274 photos · 665 identities · 69 confirmed

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
- [ ] DATA-005: Nightly R2 backup for critical JSON/NPY files ([PRD-027](docs/prds/027_data_migration.md))
- [x] 2026-02-25: Retry 144 failed photos — 142/144 already retried ($2.04). 2 blocked by Gemini content safety.
- [x] 2026-02-25: UX-103 — Back nav, metadata overlay, mobile hamburger menu

### Near-Term
- [ ] DATA-006: Shadow writes — all identities + photo_index to Supabase ([PRD-027](docs/prds/027_data_migration.md))
- [ ] PRODUCT-002: Face Compare Tier 2 — shared backend architecture (AD-117)
- [ ] ML-053: Multi-pass Gemini — low-confidence re-labeling
- [x] 2026-03-01: FE-041: "Help Identify" mode — /help page, Identify Mode toggle, OG cards
- [ ] Active learning pipeline

### Future Evaluation: Frontend Framework Migration
- **Trigger:** If 3+ JS embeds require shared state, or mobile UX audit scores below acceptable after Session 74
- **Options:** React SPA with FastAPI backend, or Next.js with Supabase direct
- **Queued by:** HD-022 (Session 74)
- **Status:** NOT YET TRIGGERED

### Future
- [ ] PRODUCT-003: NL Archive Query MVP — LangChain (AD-118)
- [ ] PRODUCT-004: Historical Photo Date Estimator Standalone
- [ ] OPS-002: CI/CD pipeline
- [ ] PRODUCT-005: Face Compare Tier 3 — product grade
- [ ] GEN-001+: Multi-tenant architecture

See [docs/BACKLOG.md](docs/BACKLOG.md) for full details on each item.

## Planned Sessions

### Session 43: Life Events & Context Graph (deferred)
- Event tagging, connecting photos/people/places/dates
- PRD: docs/prds/011_life_events_context_graph.md

## Recently Completed

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
