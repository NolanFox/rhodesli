# Rhodesli: Project Backlog

**Version**: 41.0 — March 4, 2026
**Status**: ~4059 tests passing, v0.90.0, 274 photos, 665 identities, 60 confirmed
**Live**: https://rhodesli.nolanandrewfox.com

---

## Current State Summary

Rhodesli is an ML-powered family photo archive for the Rhodes/Capeluto Jewish heritage community. It uses InsightFace/AdaFace PFE with MLS distance metrics, FastHTML for the web layer, Supabase for auth, Railway for hosting, and Cloudflare R2 for photo storage. Admin: NolanFox@gmail.com (sole admin). 50 sessions have delivered deployment, auth, core UX, ML pipeline, stabilization, share-ready polish, ML validation, sync infrastructure, family tree, social graph, map, timeline, compare tool, sharing design system, feature audit polish, match page polish, year estimation tool, community bug fixes, estimate page overhaul, and 2401 tests. Community sharing live on Jews of Rhodes Facebook group with 3 active identifiers.

---

## Active Bugs

### P0 — Blocks Core Workflow
- ~~**UX-036**: Merge button 404~~ FIXED (Session 49D)
- ~~**UX-070-072**: Name These Faces broken on /photo/ pages~~ FIXED (Session 49D)
- ~~**UX-044/052**: Compare/Estimate upload messaging~~ FIXED (Session 49D/49E)

### P1 — Significant Friction
- ~~**UX-103**: Full-bleed photo view has no CTAs, overlays, or metadata~~ FIXED (Session 68)
- ~~**UX-037**: Merge direction unintuitive~~ FIXED (Session 86) — hx_confirm on all merge buttons with both identity names
- ~~**UX-038**: Operations on merged-away IDs return 200 silently~~ FIXED (Session 86b) — POST guards with HX-Redirect to canonical
- ~~**UX-039**: No admin controls on /person/ page~~ FIXED (Session 86) — inline rename, confirm/skip/reject, merge search
- **UX-042**: /identify/{id} shareable page has no link to source photo (critical for community onboarding)
- **UX-045-046**: No loading indicator + no auto-scroll on compare upload results
- ~~**UX-053**: Estimate upload: no photo preview~~ FIXED (Session 86b)
- **UX-054-055**: Estimate upload: no loading indicator, no auto-scroll
- ~~**UX-056**: Estimate upload: no CTAs (dead end)~~ FIXED (Session 86b)
- ~~**UX-057**: Estimate upload: file input doesn't reset~~ FIXED (Session 86b)
- **UX-080**: 404 page unstyled — Tailwind not loading
- **UX-081**: About page missing navbar
- **UX-092**: Birth year Save Edit race condition (click interference)

### P1 — From Session 69 UX Review
- ~~**UX-108**: "Heritage Archive" subtitle fails WCAG AA contrast~~ FIXED (Session 70)
- ~~**UX-109**: "To Review" color inconsistent — amber vs blue~~ FIXED (Session 70)

### P2 — From Session 69 UX Review
- ~~**UX-110**: Discovery card identity names truncated at 120px~~ FIXED (Session 70, 200px + tooltips)
- ~~**UX-111**: Discovery confidence badge no tooltip~~ FIXED (Session 70)
- ~~**UX-112**: "Confirm as {name}" button overflow~~ FIXED (Session 70, truncation + tooltip)
- ~~**UX-113**: Discovery empty state blank div~~ FIXED (Session 70, "All discoveries reviewed!")

### P2 — From Session 70
- **UX-114**: Collection dropdown `onfocus="this.select()"` is fragile — keyboard nav doesn't trigger onfocus. Replace with placeholder text or proper select component. Source: Session 69 BUG-3 fix fragility.

### P2 — From Session 67 UX Review
- ~~**UX-104**: Compare "Compare Selected Faces" button disabled state~~ VERIFIED (Session 70, already implemented)
- ~~**UX-105**: Missing "Help Identify" CTA for all-unidentified photos~~ FIXED (Session 70, amber styling)
- **UX-106**: Inconsistent contribution CTA phrasing ("Do you know?" vs "Can you help?")
- **UX-107**: "Identified" badge on person page has no tooltip or explanation

### COMPARE-002: Real-Time Compare Upload (Concrete Plan, AD-187)
- **Status**: DEFERRED — blocked by AD-007 (no ML deps in production)
- **What works now**: Archive-face comparison (pre-computed embeddings). Upload queues to R2 for batch.
- **What's needed**: GPU on Railway OR ONNX export of InsightFace compatible with PFE embeddings
- **Estimated effort**: 2-3 sessions once blocker clears
- **Steps**: (1) Export InsightFace to ONNX, (2) Add onnxruntime-cpu to production, (3) Single-face inference on upload, (4) Cosine distance vs cached embeddings
- **Trigger**: Railway GPU support announcement OR compatible lightweight model

### Deferred from Earlier Audits (Medium/Low)
- **M2**: Compare file input lacks preview feedback
- **L1**: Login inputs missing `autocomplete` attribute
- **L2**: Tailwind CDN development warning
- **L3**: Landing stats counter shows 0 before scroll
- **Pre-existing**: `test_nav_consistency` `/map` state pollution (passes in isolation)

Full tracker: [docs/ux_audit/UX_ISSUE_TRACKER.md](../docs/ux_audit/UX_ISSUE_TRACKER.md) — 100 issues total

---

## Recent Sessions (v0.79.1 — 2026-02-28)

- **Session 77** (v0.79.1): Compare Rebuild Follow-up. Pair compare enriched with cross-photo face summaries and archive best-hit matches (AD-181). Compare uploads auto-queued to admin pending review (AD-182). Golden test suite in tests/test_compare.py. ~3752 total.

- **Session 76a** (v0.79.0): Auto-Clustering + Discoveries Redesign + Face Cards. Two-tier auto-clustering pipeline (AD-179). Discovery log as ML audit trail. Discoveries page two-tier layout. Browse cards face-dominant (200px min). Backfill: 0 Tier 1, 7 Tier 2, 652 no match. 15 new tests + 4 regression fixes. ~3742 total.

- **Session 65d** (v0.71.0): Disk Space Fix + GEDCOM Versioning + Harness. Disk: .dockerignore saves ~400MB, startup cleanup, backup pruning (AD-162). All 3 uploads verified in Chrome browser. GEDCOM temporal versioning: version tracking, field-level diffs, enrichment queue, current_* views (AD-163). Stop hook + enhanced eval script. 30 new tests. ~3553 total.
- **Session 65c** (v0.70.0): Upload Fix (MANDATORY) + Verification Sweep + Harness. Root cause: subprocess OOM from double model loading (AD-161). Fix: thread shares hybrid models. All 3 upload surfaces verified in production. GEDCOM linking verified end-to-end (6/6 PASS). Harness: assessment mandate, prompt template, eval script. ~3475 tests.
- **Session 65b** (v0.69.0): GEDCOM Linking UX + Enrichment Fix. Production verification (5/6 PASS). GEDCOM ↔ Identity linking with fuzzy Sephardic search (AD-160). Enrichment pipeline: first_order variant for full family context (AD-159 fix). API call logging: gemini_config + response_summary now populated. 28 new tests. 3521 total.
- **Session 65a** (v0.68.0): Upload Fix + Compare Overhaul + UX Polish. Upload subprocess death detection + timeout. Two-photo face comparison (/compare/pair). Face overlay toggle. Prompt fidelity audit (AD-159). 24 new tests. ~3493 total.
- **Session 64** (v0.67.0): Verify, Migrate, Harden. Harness hardening (5 skills, 3 rules, 3 hooks). Face alignment → Supabase. gemini_api_calls tracking. Centralized model config. Combined pipeline. Calibrated scores in UI. Recalibration hooks wired. AD-152. ~50 new tests. ~3450 total.
- **Session 63** (v0.66.0): Close the Gaps, Calibrate, Re-Run. Real photo face alignment (3/3 pass). GEDCOM Supabase import (21,809 individuals, 145,574 relationships). Similarity calibration (AUC=0.9577, 348 pairs). Recalibration hooks. AD-149/150/151. 29 new ML tests. ~3402 total.
- **Sessions 57-62** (v0.59.0-v0.65.0): CORAL production, MLflow, Face Compare Tier 1, Supabase migration, Gemini refinement, SSE upload, face alignment. See [docs/roadmap/SESSION_HISTORY.md](../docs/roadmap/SESSION_HISTORY.md).
- **Sessions 49B-56** (v0.55-v0.58): Similarity calibration, ONNX serving, landing page refresh, UX fixes, GEDCOM import. See [docs/roadmap/SESSION_HISTORY.md](../docs/roadmap/SESSION_HISTORY.md).

---

## Session 78 Outstanding Items (2026-02-28)

### GEDCOM Sync Follow-up
- [ ] **GEDCOM-007: Verify production tree count after deploy** — Local data/relationships.json has ~1,019 relationships (19 UUID + 1,000 GEDCOM). Supabase may only have the 19 UUID ones. After Session 78 deploy, verify /tree shows ~718 people, not just 24 confirmed identities. Source: docs/session_context/session-78-context.md.

### Compare Full Rebuild
- [ ] **COMPARE-001: Complete compare UX rebuild** — Session 77 (Codex) implemented ~25% of the original 8-phase compare prompt: archive context + auto-queue + golden tests. Remaining: full UX redesign of compare flow, upload pipeline reliability, mobile optimization, standalone compare product vision. Source: docs/session_context/session-78-context.md.

### Route Error Investigation
- [ ] **BUG-004: Verify /connect and /map stability** — Both routes had 500 errors in earlier sessions (Sessions 40-41). /map depends on PhotoRegistry.get_photo() and geocoded data. /connect depends on D3.js social graph. Verify both return 200 in production after deploy, check for ISEs under edge cases (missing data, bad IDs). Source: Session 78 Track 7 prompt.

### Per-Identity Adaptive Thresholds
- [ ] **ML-098: Per-identity adaptive thresholds for auto-clustering** — Current auto-clustering uses global thresholds (Tier 1 < 0.85, Tier 2 < 1.10). Per-identity thresholds based on within-cluster distance variance could improve precision. Big Leon's within-cluster max may exceed 1.10, meaning Tier 2 misses valid matches for high-variance identities. Requires per-identity distance stats from threshold analysis. Source: AD-179, docs/prds/024_auto_clustering.md "Out of Scope".

---

## Session 60B Findings (2026-02-22)

### ML — Progressive Refinement Completion (P1)
- [x] **ML-090: Fix enriched prompt gap** — DONE (Session 61). `call_gemini()` now accepts `prompt` parameter, `run_refinement()` passes enriched prompt. AD-139.
- [ ] **ML-091: Real 3-photo validation** — Run refinement on top photo (inbox_b5e8a89e_9, 19 facts, existing label 1950s, birth year math says 1940s). ~$0.10.
- [ ] **ML-092: Results-to-web bridge** — Script/endpoint to merge refinement_results.json into date_labels.json for admin review. Currently no connection to web app.
- [ ] **ML-093: Full 41-photo batch run** — After prompt gap fixed and validated. ~$1.31.
- [x] **ML-094: Write AD-136/137/138** — DONE (Session 61). AD-139-142 also added. See ALGORITHMIC_DECISIONS.md.
- [ ] **ML-095: CORAL retroactive run** — Run local model on all 271 photos, compare to Gemini labels. Free independent validation.

### UX Improvements (from Production Review)
- [ ] **UX-120: Help Identify mode for non-admin users (P1)** — Primary community use case requires admin intervention. Let logged-in users suggest names for unidentified faces → admin approval queue. See `docs/session_logs/session_60b_ux_review.md`.
- [ ] **UX-121: Contribution instructions page (P2)** — /contribute page explaining: how to identify faces, submit photos, report errors. Community members arrive from Facebook links.
- [ ] **UX-122: Person page family context (P2)** — 19 relationships exist in data but aren't visible. Show family connections, timeline of appearances.
- [ ] **UX-123: Mobile photo overlay readability (P2)** — Photos with 12+ faces have overlapping labels. CSS media query for reduced label size or tap-to-show.
- [ ] **UX-124: People page search/filter (P2)** — No search input on /people page.

### Face Alignment (Session 62)
- [-] **FA-001: Batch face alignment for all 271 photos** — 127/271 aligned (Session 63/64). 144 rate-limited, retry ready: `python scripts/run_combined_pipeline.py --retry-failed results/batch_alignment_20260223_023456.json`
- [x] **FA-002: Face alignment + GEDCOM context integration** — DONE (Session 64). Combined pipeline includes GEDCOM curated context. `scripts/run_combined_pipeline.py` with `--no-gedcom` flag to disable.
- [ ] **FA-003: Mobile UI refinement for face description cards** — Cards may overlap on small screens with many faces. Needs CSS media queries. Source: Session 62 prompt 6B.
- [ ] **FA-004: Auto-trigger face alignment on new photo upload** — After upload + face detection, auto-run alignment if GEMINI_API_KEY available. Source: Session 62 prompt 6B.
- [x] **FA-005: Production test face alignment** — DONE (Session 63). 3 photos tested, 100% success, $0.03. Source: Session 62 Phase 5 deferred.

### GEDCOM Integration (Session 61C, AD-147/148)
- [x] **GEDCOM-001: Supabase GEDCOM tables** — DONE (Session 63). 4 tables created via psycopg2: gedcom_individuals (21,809), gedcom_events (40,140), gedcom_relationships (145,574), gedcom_face_links (61). Source: Session 61C, AD-147/148.
- [x] **GEDCOM-002: Admin GEDCOM link review UI** — DONE (Session 65b). Fuzzy search with Sephardic surname variants. Auto-enriches birth/death on link. Unlink with soft delete. AD-160.
- [x] **GEDCOM-006: GEDCOM temporal versioning** — DONE (Session 65d). Version tracking, field-level diffs, enrichment queue, current_* views. AD-163. Migration: scripts/supabase_migration_002_gedcom_versioning.sql. Import: scripts/import_gedcom_version.py.
- [ ] **GEDCOM-003: GEDCOM enrichment in upload flow** — When a face is identified and has a GEDCOM link, show enriched analysis popup with genealogical context (birth year, relationships, life events). Status: OPEN. Source: Session 61C, AD-147/148.
- [ ] **GEDCOM-004: "Analysis improved because..." UX feature** — Show users what GEDCOM context added vs visual-only analysis. Side-by-side or inline comparison of results with and without genealogical enrichment. Status: OPEN. Source: Session 61C, AD-147/148.
- [ ] **GEDCOM-005: Batch re-analysis with GEDCOM enrichment** — Re-run all 271 photos with first_order GEDCOM variant (fixed from curated in Session 65b). Leverage linked GEDCOM data to improve date estimation and identity confidence. Status: OPEN, pipeline fix shipped. Source: Session 61C, AD-147/148, AD-159.

### Similarity Calibration (Session 63, AD-149/150)
- [ ] **CAL-001: Community "reject" UX** — Enable explicit non-match pair collection from admin/user rejections. Feeds recalibration hooks (AD-150). Critical for calibration model improvement. Source: Session 63 Phase 9.
- [ ] **CAL-002: Active learning — surface uncertain pairs** — Find face pairs near the decision boundary (P(match) 0.4-0.6) and surface them for admin labeling. Maximizes information gain per label. Source: Session 63 Phase 9.
- [ ] **CAL-003: Calibration drift monitoring dashboard** — Admin page showing calibration model version, AUC trend, threshold history, pair count growth. Alert on drift >0.1. Source: Session 63 Phase 9.
- [ ] **CAL-004: Wire calibrated probabilities to compare UI** — Replace raw cosine similarity display with calibrated P(match) + confidence label (High/Medium/Low/Unlikely). Source: Session 63 AD-149.

### Data Layer (Session 64, AD-152)
- [ ] **DATA-002: Create Supabase tables** — Run `scripts/sql/create_face_gemini_alignments.sql` and `scripts/sql/create_gemini_api_calls.sql` in Supabase. Required for Supabase-first data layer to function. Source: Session 64.
- [ ] **DATA-003: Run alignment migration** — Execute `python scripts/migrate_alignments_to_supabase.py --execute` after tables created. Migrates 127 alignment records from JSON to Supabase. Source: Session 64.
- [ ] **DATA-004: Retry 144 rate-limited photos** — Run `python scripts/run_combined_pipeline.py --retry-failed results/batch_alignment_20260223_023456.json`. Requires GEMINI_API_KEY. Estimated cost: ~$4 at $0.028/photo. Source: Session 64.

### Face Card Consolidation (Session 82b gap, deferred 82f)
- [ ] **UX-204: Unify face card rendering** — 14+ inline face card rendering locations in app/main.py use bespoke code. Consolidate into reusable `face_card()` component. Major refactor. Source: 82b Phase 2, 82d assessment.

### 82c Gemini Branch Merge (Session 82c, stranded)
- [ ] **ML-100: Merge session-82c/gemini-rerun to main** — Branch has 14 commits of Gemini enrichment pipeline work (Asheville litmus test, batch pipeline, Gatekeeper integration). Blocked by: AD numbering conflict (branch AD-194 vs main AD-194), 82a artifacts on branch need removal. Requires deliberate merge session with conflict resolution. Source: Session 82c.

### UX Features (Session 82a ideation, deferred 82f)
- [ ] **UX-201: Missing Info Table View** — Admin view listing identities with missing metadata (no birth year, no GEDCOM link, no photos). ~30-45 min. Needs PRD. Source: 82a #21.
- [ ] **UX-202: One-Click Bulk Tag Confirmation** — Confirm all faces in a high-confidence cluster at once. ~30-60 min. Risk: data writes. Source: 82a #30.
- [ ] **UX-203: Relational Context Labels** — Show GEDCOM relationships ("mother of X") on face cards. Requires Supabase GEDCOM query per identity. ~45-60 min. Source: 82a #19.

### Architecture
- [ ] **ARCH-001: Rhodesli-specific hardcoding** — 171 references to "Rhodes/Jewish/Ladino/Sephardic" in app/main.py. Heavy refactoring needed for multi-community. See `docs/session_logs/session_60b_ux_review.md` Broader Scope section.

---

## From Community Sharing Feedback (Session 49C)

### Quick-Identify from Photo View — DONE (Session 51, v0.51.0)
P0 tag dropdown was already implemented. Session 51 added P1 sequential
"Name These Faces" mode: admin clicks button → auto-advances through
unidentified faces left-to-right with progress tracking. See PRD-021.

### Batch Identity Entry from External Source — PARTIALLY DONE (Session 51)
"Name These Faces" sequential mode covers the left-to-right naming
use case. Remaining: bulk text paste ("Albert Cohen, Morris Franco,
Ray Franco") auto-assigned to faces. Deferred to future session.
See: docs/session_context/session_49C_community_feedback.md

### Facebook Integration Research (LOW priority)
The sharing -> comment -> identification loop works manually but is
friction-heavy. Research: can we create a bot or integration that
monitors tagged posts and pulls identifications back into the system?
Alternatively: shareable photo pages with inline commenting that
feeds back to the admin review queue.
See: docs/session_context/session_49C_community_feedback.md

---

### Estimate Page Remaining (PRD-020 P1/P2)
- [ ] Search/filter by collection, date range
- [ ] Date correction flow — "Know the date?" → Gatekeeper pattern
- [ ] Deep CTAs: "View in archive", "Help identify", "Explore era"
- [ ] Auto-run Gemini on uploaded photos when API key configured

---

## Immediate Priority (Next 1-2 Sessions)

- [x] **Quick-Identify**: Inline face naming on photo page — DONE (Session 51)
- [x] **Batch Identity Entry**: "Name These Faces" sequential mode — DONE (Session 51)
- [ ] **OPS-001**: Custom SMTP for branded "Rhodesli" email sender
- [ ] **FE-040-043**: Skipped faces workflow for non-admin users
- [x] **PRODUCT-001: Face Compare Standalone — Tier 1**: Museum-quality /facecompare page. Session 59, v0.61.0. AD-131/132/133.

## Near-Term (3-5 Sessions)

- [x] **Gemini 3.1 Pro integration**: Wired to Estimate upload (Session 52). Updated to 3.1 Pro (Session 61, AD-139).
- [ ] **ML-075: Batch Gemini Run on 271 Photos**: Run date estimation on all existing photos. Deferred from Session 52.
- [ ] **ML-096: Run compare_models.py with --photos 20**: Flash vs Pro A/B comparison on 20 photos (~$0.62). Needs Nolan approval. (Session 61)
- [ ] **ML-097: Run full 271-photo re-analysis with 3.1 Pro**: After ML-096 validates quality. Needs cost approval. (Session 61)
- [-] **PRD-015 v2**: Face alignment via coordinate bridging — design complete (AD-144), integrated with unified extraction (AD-143). Implementation TODO. Session 53 design → Session 61B update.
- [x] **Gemini unified extraction architecture**: AD-143, rhodesli_ml/gemini_extraction.py, 16 tests. Session 61B.
- [x] **PRD-023 Stage 1**: Similarity calibration — isotonic regression (better than Platt). AUC=0.9577, 348 pairs. Session 63, AD-149. Stage 2 (LoRA) deferred.
- [x] **Progressive refinement**: Pipeline fully wired — enriched prompt now sent to Gemini. Session 60 (AD-138) + Session 61 (ML-090 fixed).
- [ ] **UX-130**: Homepage visitor experience — non-admin landing page with CTAs (P2). Source: Session 61B UX evaluation.
- [ ] **UX-131**: Photo page admin tools below evidence — collapse behind toggle (P2). Source: Session 61B UX evaluation.
- [ ] **UX-132**: Homepage "Compare a Face" CTA for non-admin visitors (P2). Source: Session 61B UX evaluation.
- [x] **FE-041**: "Help Identify" mode for non-admin users — DONE 2026-03-01 (Session 82e). /help page, Identify Mode toggle, OG cards for sharing.
- [ ] **DOC-001**: Portfolio documentation — Technical writeup of ML pipeline (InsightFace → CORAL → isotonic calibration → Gemini alignment → GEDCOM enrichment). Session 66. AD-158.
- [ ] **ML-070**: LoRA fine-tuning — Fine-tune InsightFace final layers on confirmed identity pairs. Needs 50-100+ confirmed pairs. Stage 2 of PRD-023. Session 67+. AD-158.
- [ ] **BE-031-033**: Upload moderation queue with rate limiting
- [ ] **ROLE-006**: Email notifications for contributors
- [ ] **ML-053**: Multi-pass Gemini for low-confidence re-labeling
- [ ] **BE-015-016**: Geographic data model + temporal date handling
- [ ] **FE-061-063**: Quick Compare, batch confirmation, browser performance audit
- [ ] **Overnight ML pipeline** — `scripts/ml_pipeline.py` with modes: overnight (full pipeline), interactive (quick), validate (re-check compare results). See session 54B context.
- [ ] **Playwright MCP integration** — Browser-based production testing. `.mcp.json` configured, needs first test run.
- [ ] **UX-134**: Mobile landing page horizontal overflow — `test_mobile_landing_page[chromium]` fails with 405px overflow (scrollWidth=780, clientWidth=375). Pre-existing, confirmed across multiple sessions. Source: Session 82e.
- [ ] **COMMUNITY-001: Nancy Gormezano Beta Test**: Engage Nancy as first non-family beta tester. Source: Session 49C community thread.
- [ ] **Production smoke test in CI** — Auto-run `scripts/production_smoke_test.py` on deploy
- [x] **ML-070: MLflow Integration — CORAL Training**: MLflow Model Registry + Promotion Pipeline. Session 58, v0.60.0. AD-130.
- [ ] **PRODUCT-002: Face Compare Tier 2 — Shared Backend**: Shared comparison engine between standalone and Rhodesli. Rhodesli path adds: archive identity matching, upload persistence, date context, contribute-to-archive flow. Public path: compare and discard. See AD-117, docs/session_context/session_54c_planning_context.md Part 2C.

## Medium-Term

- [ ] **OPS-002**: CI/CD pipeline (automated tests, staging, deploy previews)
- [ ] **OPS-004**: Error tracking (Sentry)
- [ ] **QA-005-007**: Mobile viewport tests, UX walkthroughs, performance benchmarking
- [ ] **AN-022**: Cross-reference genealogy databases (Ancestry, FamilySearch, JewishGen)
- [ ] **DOC-010-013**: In-app help, about page, admin guide, contributor onboarding
- [ ] **FE-080-083**: Client-side analytics and admin dashboard
- [ ] **ROLE-004**: Family member self-identification ("That's me!" button)
- [x] **Admin/Public UX Unification**: Admin bar + quick-identify inline flow — Session 60, v0.63.0
- [ ] **Confidence scores per identification**: Show which results are ground truth vs provisional. Genealogy-specific differentiation. (Source: Expert review, Session 54)
- [ ] **Identity voting / community verification**: Let users confirm/reject ML matches. Improves embeddings over time. (Source: Expert review, Session 54)
- [ ] **Processing Timeline UI**: Per-photo status display for trust restoration. (Source: Expert review, Session 54. See AD-111)
- [ ] **Observability over unit tests**: Prioritize integration tests, per-photo processing timelines, job status visibility. (Source: Expert review, Session 54. See AD-110)

## Medium-Term — New Products & ML (Session 54c)

- [ ] **ML-071: MLflow — Gemini Prompt Tracking**: Track how different Gemini API prompts yield better/worse photo context extraction over time. Log prompt text, model version, output quality metrics per run. See AD-116, docs/session_context/session_54c_planning_context.md Part 1B.
- [ ] **ML-072: MLflow — Local vs Web ML Benchmarking**: Compare InsightFace local inference vs API-based face comparison. Track latency, accuracy, cost per comparison. See AD-116, docs/session_context/session_54c_planning_context.md Part 1B.
- [ ] **PRODUCT-003: NL Archive Query MVP (LangChain)**: Natural language interface: "Show me photos from the 1930s with people who look like [uploaded face]." Chain: face detection → embedding search → date filtering → NL response. Prerequisites: similarity calibration + CORAL + stable identity matching. Estimated 2-3 sessions once prerequisites met. See AD-118, docs/session_context/session_54c_planning_context.md Part 1B.
- [ ] **PRODUCT-004: Historical Photo Date Estimator Standalone**: Upload historical photo → estimate when taken using CORAL model. Genuinely novel — no existing tool offers this. Prerequisite: CORAL model trained and validated. Could combine with face comparison in shared "faces" tool site. See docs/session_context/session_54c_planning_context.md Part 2D.

### Upload UX Remaining (from Session 60 SSE Epic)
- [ ] Face-by-face progressive rendering + overlay animations
- [ ] asyncio.Queue for concurrent upload serialization

## Long-Term

- [ ] **BE-040-042**: PostgreSQL migration (JSON won't scale past ~500 photos)
- [ ] **ML-030-032**: Model evaluation (ArcFace, ensemble, fine-tuning)
- [ ] **GEN-001+**: Multi-tenant architecture (if traction)
- [ ] **AI-001/003-005**: Auto-caption, photo restoration, handwriting OCR, story generation
- [ ] **GEO-003**: Community-specific context events (diaspora cities)
- [ ] **GEO-004: Geographic Migration Analysis**: Combine Gemini-extracted locations with GEDCOM data to trace family migration patterns (Rhodes → diaspora cities). Source: Session 54c planning.
- [ ] **KIN-001**: Kinship recalibration post-GEDCOM (19 relationships now available)
- [ ] **Session 43**: Life Events & Context Graph (event tagging, richer timeline)
- [ ] **PRODUCT-005: Face Compare Tier 3 — Product Grade**: User accounts, saved comparisons, API access, batch comparison. Post-employment priority. See AD-117.
- [ ] **PRODUCT-006: Interactive Photo Chatbot**: Conversational interface for photo analysis — user provides context, chatbot cross-references GEDCOM data, progressive refinement. Demonstrated by Asheville case study (Session 81). Each user input documented as metadata, feeds back to improve estimates. Source: Session 81 Nolan feedback, `docs/session_context/session_81_context.md` §5.
- [ ] **GRAPH-001: "Six Degrees" Connection Finder**: Graph traversal showing shortest path between any two people in the archive via photos, family, events. Novel feature. Source: Session 54c planning.
- [ ] **ML-080: DNA Matching Integration**: Explore DNA-based family matching as complement to face comparison. Community interest from Leo Di Leyo (Facebook). Source: Session 49C community feedback.
- [ ] **PARTNER-001: Institutional Partnership**: Museum/archive collaboration for expanded photo access and academic credibility. Source: Session 49C community feedback.
- [ ] **UX-110: Three-Mode Cognitive Framing**: Explore/Investigate/Curate modes with progressive complexity. Adopted conceptually, not yet built. Source: Session 50 planning.

---

## Execution Phases

### Phase A: Stabilization — COMPLETE (2026-02-08)
All 9 bugs fixed. 103+ new tests. Event delegation pattern established.

### Phase B: Share-Ready Polish — MOSTLY COMPLETE (2026-02-06 to 2026-02-19)
Landing page, search, mobile, sync, photo viewer, timeline, compare, sharing, year estimation, estimate overhaul.
Remaining: OPS-001 (branded email).

### Phase C: Annotation Engine — COMPLETE (2026-02-10 to 2026-02-13)
Photo/identity annotations, merge safety, GEDCOM, suggestion lifecycle.

### Phase D: ML Feedback & Intelligence — MOSTLY COMPLETE (2026-02-09 to 2026-02-19)
Threshold calibration, golden set, date estimation pipeline, Gemini 3.1 Pro wired to Estimate upload, ML on Railway.
Remaining: ML-053 (multi-pass Gemini), FE-040-043, progressive refinement, batch Gemini run on 271 photos.

### Phase E: Collaboration & Growth — IN PROGRESS
Contributor roles done. Community sharing live. Quick-Identify + "Name These Faces" done (Session 51). Remaining: Help Identify mode, upload moderation, notifications.

### Phase F: Scale & Generalize — FUTURE
PostgreSQL migration, CI/CD, model evaluation, multi-tenant.

### Harness Engineering — BACKLOG
- [ ] HARNESS-001: Evaluate Ralph Wiggum for overnight runs after 3+ sessions with verification gate (see HD-001)
- [ ] HARNESS-002: Consider native Tasks system for sessions with independent phases (see HD-001)
- [ ] HARNESS-003: Build session log analyzer script for docs/session_logs/*.md patterns (see HD-005)
- [ ] HARNESS-004: `run_session.sh` — manual test only, not a numbered session phase. Script splits prompts at `## PHASE` markers and runs each as separate `claude -p` invocations. Cannot be tested from within a Claude session (nested `claude -p` not supported). Session 67 Phase 5 created it, Session 68 Phase 5 confirmed it cannot run inside Claude. Needs manual validation outside a session. See `scripts/run_session.sh`, HD-018.

---

## Sub-Files

| File | Content |
|------|---------|
| [docs/backlog/COMPLETED_SESSIONS.md](backlog/COMPLETED_SESSIONS.md) | All completed session history (Sessions 1-46) |
| [docs/backlog/FEATURE_MATRIX_FRONTEND.md](backlog/FEATURE_MATRIX_FRONTEND.md) | Bugs + Front-End/UX items (Sections 1-2) |
| [docs/backlog/FEATURE_MATRIX_BACKEND.md](backlog/FEATURE_MATRIX_BACKEND.md) | Backend + ML + Annotations + Infra (Sections 3-6) |
| [docs/backlog/FEATURE_MATRIX_OPS.md](backlog/FEATURE_MATRIX_OPS.md) | Testing + Docs + Roles + Vision (Sections 7-10) |
