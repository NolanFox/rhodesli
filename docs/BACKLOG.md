# Rhodesli: Project Backlog

**Version**: 46.0 — March 11, 2026
**Status**: ~4664 tests passing, v0.97.10, 938 photos, 3412 identities, 84 confirmed
**Live**: https://rhodesli.nolanandrewfox.com

---

## Current State Summary

Rhodesli is an ML-powered family photo archive for the Rhodes/Capeluto Jewish heritage community. It uses InsightFace/AdaFace PFE with Euclidean distance metrics, FastHTML for the web layer, Supabase/Postgres for auth and structured data, Railway for hosting, and Cloudflare R2 for photo storage. Admin: NolanFox@gmail.com (sole admin). 95 sessions have delivered deployment, auth, core UX, ML pipeline, stabilization, share-ready polish, ML validation, sync infrastructure, family tree, social graph, map, timeline, compare tool, sharing design system, feature audit polish, match page polish, year estimation tool, community bug fixes, estimate page overhaul, Postgres migration, observability (Sentry/PostHog/Resend), GEDCOM integration, auto-clustering, and ~4283 tests across 299 photos, 894 identities (69 confirmed). Community sharing live on Jews of Rhodes Facebook group (~2,000 members).

---

## Active Bugs

### P0 — Fox Family Unusable (Session 96c-cont4 + 96d) — ALL FIXED in Session 96d
- ~~**COMMUNITY-007**: Fox Family sidebar counts not community-scoped~~ FIXED (Session 96d) — proposals.json read + community filter
- ~~**COMMUNITY-008**: Fox Family bottom nav bar uses bare URLs~~ FIXED (Session 96d) — community_url_prefix on all nav links
- ~~**COMMUNITY-009**: Upload Review + GEDCOM triage pages not discoverable~~ FIXED (Session 96d) — already in sidebar, verified
- ~~**COMMUNITY-010**: Proposals not surfaced in Fox Family sidebar~~ FIXED (Session 96d) — sidebar reads proposals.json
- ~~**COMMUNITY-011**: Cluster review page not community-scoped~~ FIXED (Session 96d) — proposals filtered by community identity set
- ~~**COMMUNITY-012**: To Review section shows flat faces without proposal info~~ FIXED (Session 96d) — badge shows "Matches [Name] (XX%)"
- ~~**COMMUNITY-013**: Admin page headers show "Rhodesli" instead of community name~~ FIXED (Session 96d) — admin headers use community name
- ~~**COMMUNITY-014**: Cross-community photos/faces have no community indicator~~ FIXED (Session 96d) — "From [Community Name]" badges on neighbor_card + discovery cards

### P1 — Community Link Scoping
- **COMMUNITY-015**: Internal photo/person links don't include community prefix — clicking a photo from Fox Family browse navigates to `/photo/{id}` (Rhodes context) instead of `/c/fox-family/photo/{id}`. Requires updating hundreds of `href=f"/photo/{id}"` references across all route files. Source: Session 96d browser verification.

### P1 — Default Community Routing Risk (COMMUNITY-017)
- **COMMUNITY-017**: Root URL `/` defaults to Rhodes community. External users (not Rhodes/Fox family members) who visit the site and upload photos would accidentally add them to the Rhodes archive. As we scale to more communities and share tools more widely (e.g., `/tools/estimate`), this becomes a real risk. **Needs**: (1) Community selector on first visit or signup, (2) Neutral landing page at `/` that doesn't default to any community, (3) Upload requires explicit community selection if user belongs to multiple or none. **Scope**: Architectural — ties into WORKSPACE-001 (personal archive auto-creation) and WORKSPACE-005 (community discovery page). Must be solved before wider sharing. Source: Session 96e-cont5 user feedback.

### P2 — Missing Embeddings (EMBED-001)
- ~~**EMBED-001**: Reduced from `124` missing embeddings to `2` archival face records after local InsightFace rerun regenerated 130 embeddings.~~ FIXED (Session 96e-cont12) — the final `2` archival records were crop-matched back to current detections and embedded. Final local audit reports `0` missing embeddings. Root cause was registry/artifact drift plus staged-upload publication gaps.

### P2 — Batch-Wide Orphan Detection (INGEST-001)
- **INGEST-001**: `process_directory()` does per-file orphan checks but not a batch-wide sweep. Cross-file grouping by `create_inbox_identities()` can leave faces unlinked that per-file checks don't catch. Fix: Add post-batch orphan sweep in `process_directory()` after all files processed. Source: Session 96e-cont10 root cause analysis, Lesson 121.

### P1 — Shadow Reconcile Automation (DATA-009)
- **DATA-009**: Supabase backfills/shadow syncs are additive-only, so audited corrective snapshots can still leave stale rows behind. Session 96e-cont12 had to export and prune `112` stale identity rows manually. Fix: add a dry-run-first `--prune-stale` reconcile mode that emits a checked-in diff artifact before deleting anything. Source: Session 96e-cont12 production reconciliation.

### P1 — Cross-Store Drift Monitoring (DATA-010)
- **DATA-010**: We still lack automatic detection when volume JSON, Postgres shadow tables, and derived artifacts drift apart. Fix: nightly snapshot compare of counts + hashes across identities, photos, face counts, and embedding coverage, with an artifact written for review and alerting on divergence. Source: Session 96e-cont12 root-cause analysis.

### P2 — Test Ordering Flakiness (TEST-001)
- ~~**TEST-001**: 31 tests fail in full suite but pass individually.~~ FIXED (Session 96e-cont12 closeout) — cache/env leakage fixtures were tightened, calibration early stopping was stabilized, and the final `/timeline` empty-filter failure was closed. Full suite now passes: `4098` app + `566` ML.

### P1 — Upload Pipeline Bugs (UPLOAD-002)
- **UPLOAD-002**: Two bugs found in upload pipeline (Session 96e-cont5): (1) Rhodes community excluded from `photo_communities` tagging — uploaded photos invisible in community-scoped Photos view despite "success" message. FIXED. (2) Supabase sync after ingest loads from Postgres (old data) instead of JSON (new data) when DATA_SOURCE=postgres — new photos never reach Supabase. FIXED. Both bugs mean uploads appeared successful but photos were invisible. Root cause: pipeline written for DATA_SOURCE=json, not updated for Postgres migration.

### P1 — Proposals API Incomplete
- **COMMUNITY-016**: `/api/proposed-matches` only reads `registry.list_proposed_matches()`, not `proposals.json`. Sidebar counts include both sources (via `_compute_sidebar_counts`), so Fox Family shows "17 Proposals" in sidebar but "No pending proposals" in content. Fix: API endpoint must also read proposals.json, same as sidebar does. Source: Session 96e-cont4 browser verification.

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

### Session 95 Post-Ship (Nolan Feedback, 2026-03-09)

- **ROUTE-001: Deprecate /facecompare → redirect to /tools/compare** — ~~`/facecompare` redirects needed.~~ **DONE** (post-Session 95). 301 redirects from `/facecompare` → `/tools/compare` and `/facecompare/result/{id}` → `/compare/result/{id}`. Step 2 remaining: remove `match_facecompare_routes.py` once confirmed no external links depend on API endpoints. Source: Nolan feedback post-Session 95.

- **TOOLS-005: Estimate v2 — GEDCOM upload + text context + geography retry** — Allow users to upload a GEDCOM file or provide additional text context to enrich the Gemini date estimation prompt. Add a "Refine with more info" button on results page that accepts geography hints for retry. Builds on existing enrichment pipeline (`rhodesli_ml/enrichment/`). **Priority: P2** — v2 iteration on `/tools/estimate`. Source: Nolan feedback post-Session 95. See also: PRD-034 (`docs/prds/034_standalone_tool_suite.md`).

- **TOOLS-006: Self-service archive creation (community upload onboarding)** — Enable non-admin users to create their own community archive and upload photos. Current state: Fox Family archive exists at `/c/fox-family` but is empty and upload is admin-only. Needed: (1) "Create Your Archive" public flow (community creation + first upload in one journey), (2) per-community upload permissions (community admin vs site admin), (3) onboarding UX for first photos. This is essentially PRD-035 Phase 2 multi-tenant upload. **Priority: P2** — key to Fox Family kickoff and future growth. Source: Nolan feedback post-Session 95. See also: PRD-035 (`docs/prds/035_multi_community_platform.md`).

- **UPLOAD-001: Bulk photo import (Google Drive / local folder)** — User has 636 photos from Uncle Charlie (Fox family, digitized by cousin David) in Google Drive + Google Photos. Current web upload caps at 200 files per batch. Common use case: scanning services digitize entire collections as small JPGs (~5MB each). **Options**: (A) Local pipeline — download to folder, run `core.ingest_inbox` in batches, upload to R2, push to production. (B) Web upload in 3-4 batches of 200. (C) Google Drive API integration — paste shared folder link, app fetches + processes. Option A is fastest for immediate need. Option C is the long-term product feature for community self-service. **Priority: P1** — blocks Fox Family archive population. **Immediate action**: Run local pipeline for Charlie Fox photos. **Future**: Build Google Drive import as part of TOOLS-006. Source: Nolan feedback Session 96.

- **COMMUNITY-001: Community data scoping (PRD-035 Phase 1 gap)** — ~~Session 95 shipped community middleware but did NOT scope the actual data.~~ **PARTIALLY FIXED (Session 96)**: Photos section, sidebar counts (upload page), and admin bar now community-scoped. **Remaining gaps**: About page shows Rhodes-specific content when accessed from Fox Family sidebar (`/about` hardcodes Rhodes history). `/tools/estimate` photo picker shows Rhodes photos (by design — tools are cross-community). **Status: ~70% DONE**. Source: Nolan feedback post-Session 95, fixed Session 96.

- **COMMUNITY-002: Workspace switcher UX** — Admin users who manage multiple communities need a way to switch between them from within the app. Like Slack's workspace sidebar or Notion's workspace dropdown. Should show in the sidebar/nav: current workspace name + dropdown to switch. Notifications should be cross-workspace (user-level, not community-level). **Priority: P1** — blocks practical multi-community admin workflow. Source: Nolan feedback post-Session 95. See: PRD-035 (`docs/prds/035_multi_community_platform.md`).

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

### ML — Longitudinal Face Modeling (P2) — PRD-038 | Session 96e-cont6 research
- [ ] **ML-110: Quality-weighted best-linkage** — Weight min-distance by detection_score + embedding_norm. Modify `compute_min_distance()`. Expected: +2-5% recall. Effort: LOW (1 session). See AD-001, AD-118. **PRD**: `docs/prds/038_longitudinal_face_modeling.md` WS-1.
- [ ] **ML-111: Metadata feature expansion to calibrator** — Add date_proximity_score, name_similarity to `_featurize_pair()`. Expected: AUC 0.957→0.965+. Effort: LOW (1 session). See AD-126/149. **PRD**: `docs/prds/038_longitudinal_face_modeling.md` WS-5.
- [ ] **ML-112: Wire active learning to UI** — Surface `find_uncertain_pairs()` as "Help Review These" in sidebar. Accumulates hard negatives for calibration. Effort: LOW (1 session). See AD-092. **PRD**: `docs/prds/038_longitudinal_face_modeling.md` WS-3.
- [ ] **ML-113: Age-aware distance modulation** — Penalize impossible age gaps using birth_year + photo date. `penalty = exp(-gap/50)`. Effort: MEDIUM (1-2 sessions). See ADR-002, AD-159. **PRD**: `docs/prds/038_longitudinal_face_modeling.md` WS-2.
- [ ] **ML-114: LoRA re-evaluation with Fox Family data** — Session 68 audit found 221 pairs (MARGINAL). Fox Family likely adds 100+ pairs, pushing past threshold. Effort: MEDIUM (2 sessions). See AD-115, AD-145. **PRD**: `docs/prds/038_longitudinal_face_modeling.md` WS-4.
- [ ] **ML-115: Recalibrate thresholds with growing confirmed pairs** — Re-run isotonic regression on current confirmed set (was 69 confirmed, growing). Effort: LOW (<1 session). See AD-149/152. **PRD**: `docs/prds/038_longitudinal_face_modeling.md` WS-1.
- [ ] **ML-116: Longitudinal anchor stratification** — Use best-quality faces from EACH DECADE for matching, not just best overall. Effort: MEDIUM (1-2 sessions). **PRD**: `docs/prds/038_longitudinal_face_modeling.md` WS-2.
- **Context**: Nolan noted that Roland Fox has many photos across life stages (Fox Family collection). Current multi-anchor best-linkage helps (more anchors = better min-distance) but we're leaving improvement on the table. Google Photos does temporal clustering, active learning, metadata fusion. See research in session-96e-cont6 assessment.

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
- [ ] **DATA-005: Nightly R2 backup for critical JSON/NPY files** — Upload identities.json, photo_index.json, embeddings.npy, date_labels.json, photo_locations.json to R2 nightly. Closes "total data loss" risk. ~0.5 session. Source: PRD-027.
- [x] **DATA-006: Shadow writes for all identities + photo_index** — DONE (Session 90b). Tables created, backfill script exists, save_registry() and save_photo_registry() fire-and-forget to Supabase. Backfill on production pending.
- [x] **DATA-007: Full Postgres migration (triggered)** — Core tables created (identities, photos, photo_faces), data backfilled, DATA_SOURCE=postgres flipped on Railway. Session 93. Supplementary tables also migrated (date_labels, photo_locations, birth_year_estimates). Source: PRD-027.

### PRD Backlog — Session 91
- [-] **NOTIFY-001: PRD-028 Contributor Notifications P0** — In-app notification center, bell icon, identity confirmation trigger, auto-clustering match trigger. Origin: Claude Benatar feedback ("how does someone know if there's a match?"). PRD: `docs/prds/028_contributor_notifications.md`.
- [-] **DATA-008: PRD-027 Phase A R2 Nightly Backup** — scripts/backup_to_r2.py + scripts/restore_from_r2.py. Closes "total data loss" risk. PRD: `docs/prds/027_data_migration.md`.
- [-] **EVENT-001: PRD-011 Life Events & Context Graph** — Event model (Supabase tables), CRUD routes, photo/person/timeline integration. Flesh out stub PRD first. PRD: `docs/prds/011_life_events_context_graph.md`.
- [-] **MEDIA-001: PRD-029 Photo Backs Completion** — Media group API, Front/Back label, browse "Has back" filter, card badges. Completes work started in Session 90b. PRD: `docs/prds/029_photo_back_and_media_groups.md`.
- [ ] **BACKLOG-FLAKY-001: 8 order-dependent tests marked xfail** — Root cause: FastHTML route module loading order varies by test execution order. Proper fix needs test isolation (fresh TestClient per test or route order reset). Source: Session 90c.

### Face Card Consolidation (Session 82b gap, deferred 82f)
- [ ] **UX-204: Unify face card rendering** — 14+ inline face card rendering locations in app/main.py use bespoke code. Consolidate into reusable `face_card()` component. Major refactor. Source: 82b Phase 2, 82d assessment.

### 82c Gemini Branch Merge (Session 82c, stranded)
- [ ] **ML-100: Merge session-82c/gemini-rerun to main** — Branch has 14 commits of Gemini enrichment pipeline work (Asheville litmus test, batch pipeline, Gatekeeper integration). Blocked by: AD numbering conflict (branch AD-194 vs main AD-194), 82a artifacts on branch need removal. Requires deliberate merge session with conflict resolution. Source: Session 82c.

### UX Features (Session 82a ideation, deferred 82f)
- [ ] **UX-201: Missing Info Table View** — Admin view listing identities with missing metadata (no birth year, no GEDCOM link, no photos). ~30-45 min. Needs PRD. Source: 82a #21.
- [ ] **UX-202: One-Click Bulk Tag Confirmation** — Confirm all faces in a high-confidence cluster at once. ~30-60 min. Risk: data writes. Source: 82a #30.
- [ ] **UX-203: Relational Context Labels** — Show GEDCOM relationships ("mother of X") on face cards. Requires Supabase GEDCOM query per identity. ~45-60 min. Source: 82a #19.

### Standalone Tool Suite (PRD-034) — Session 94
Community-agnostic versions of Rhodesli's ML tools, serving as top-of-funnel and portfolio pieces. Master PRD: `docs/prds/034_standalone_tool_suite.md`.

- [ ] **TOOLS-001: Date + Location Estimator Standalone** — Extract Gemini pipeline (`rhodesli_ml/gemini_config.py`, `rhodesli_ml/gemini_extraction.py`, `app/estimate_routes.py`) into standalone product. Engine ready, zero blockers. Includes evidence cards (AD-142) + Leaflet maps. Revenue model: free (3/month), Pro ($9.99/month), API ($0.10/photo). GEDCOM upload as premium upsell. 2-3 sessions. Source: PRD-033, PRD-034.
- [ ] **TOOLS-002: ML Service Extraction + Automated Pipeline** — Extract InsightFace into separate FastAPI service. Eliminates laptop as single point of failure (pipeline has run only 6 times in 4 months). Adds: upload webhook → detect → embed → cluster → notify. Scheduled batch: nightly recalibration + re-clustering. Unblocks TOOLS-003 (face compare). 3-4 sessions. Source: `docs/architecture/ML_SERVICE.md` (reframed Session 94), PRD-034. **Key finding:** 7 pipeline scripts exist but 9/10 steps are manual CLI commands that never run. Only face detection (step 4) is automated on Railway.
- [ ] **TOOLS-003: Face Compare Real-Time** — With ML service (TOOLS-002) running, wire real-time embedding into `/facecompare` upload flow. Web app sends photo to ML service, gets 512-dim vector, compares against archive. Calibrated scoring via AD-149. Replaces ONNX export approach (simpler, also solves operational dependency). 1-2 sessions after TOOLS-002. Source: PRD-031, PRD-034.
- [ ] **TOOLS-004: NL Query + Chatbot** — Wire `parse_query_intent()` prototype to Supabase queries. Build conversational UI with progressive refinement (PRODUCT-006 vision from Session 81). 3-5 sessions. Source: PRD-032, PRD-034.
- [ ] **TOOLS-005: Unified Product Identity** — Shared domain, design system (DD-001 archival aesthetic), Supabase auth, Stripe billing, PostHog analytics across all standalone tools. Enables cross-tool funnel analysis. Source: PRD-034.

**Existing code & artifacts:**
| Artifact | Location |
|----------|----------|
| Face Compare routes (shipped) | `app/match_facecompare_routes.py` |
| Compare v2 stub | `app/compare_v2_routes.py` |
| Face Compare tests (34+) | `tests/test_facecompare.py` |
| Gemini engine | `rhodesli_ml/gemini_config.py`, `rhodesli_ml/gemini_extraction.py` |
| Evidence card UI | `app/estimate_routes.py` |
| NL query parser | `rhodesli_ml/nl_query/` |
| ML service architecture + pipeline audit | `docs/architecture/ML_SERVICE.md` |
| Pipeline scripts (7 total, manual) | `scripts/download_staged.py`, `scripts/push_to_production.py`, etc. |
| Key decisions | AD-110, AD-117, AD-131, AD-132, AD-133, AD-139, AD-142, AD-149, AD-192, AD-201 |
| Design principles | Lesson 81 (separate tools), Lesson 82 (community-agnostic), Lesson 84 (museum-quality) |

### Workspace & Onboarding (PRD-036) — Session 95b
Self-service workspace and contribution UX. Vision PRD: `docs/prds/036_workspace_onboarding.md`.

- [ ] **WORKSPACE-001: Personal archive auto-creation** — Auto-create `"{first_name}'s Archive"` community on signup. Add `owner_id`, `is_personal`, `privacy` columns to communities table. 1 session. Source: PRD-036.
- [ ] **WORKSPACE-002: Sharing mode UX** — Lighter interaction mode for community members (browse + Help Identify + share). Distinct from admin mode. 1-2 sessions. Depends: WORKSPACE-001. Source: PRD-036.
- [ ] **WORKSPACE-003: Add photos to community** — Share personal photos into community archives with Gatekeeper approval. New `community_photo_shares` table. 1-2 sessions. Depends: WORKSPACE-001. Source: PRD-036.
- [ ] **WORKSPACE-004: Anonymous contributions** — Session-tracked suggestions from anonymous visitors. Email capture optional. Link to account on signup. 1 session. Source: PRD-036.
- [ ] **WORKSPACE-005: Community discovery page** — `/communities` public directory with search. Join button for membership. 1 session. Source: PRD-036.
- [ ] **WORKSPACE-006: Per-community permissions** — Viewer/member/admin roles per community. `community_members` table with role enforcement in middleware. 2 sessions. Source: PRD-036.

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

## Infrastructure & Observability (Session 95b)

- [ ] **ENV-001**: Dev/staging/prod environment separation — Separate Sentry DSNs, Railway projects, Supabase instances for each environment. Immediate: add `SENTRY_ENVIRONMENT=development` to local `.env`. Medium-term: disable Sentry in local dev (only init when `RAILWAY_ENVIRONMENT` set). Long-term: full environment split. Source: Session 95b Sentry error discussion. See OD-008.
- [ ] **OBS-001**: Observability data retention strategy — Sentry free tier retains events 90 days, PostHog free tier 1 year. If longer retention needed: export to Supabase `error_log` table via API, or upgrade tiers. Not urgent at current scale. Source: Session 95b discussion. See OD-009.
- [ ] **OBS-002**: Error classification (dev vs production) — Tag errors with source context. Dev errors should be filterable/excludable from production dashboards. Immediate fix: `SENTRY_ENVIRONMENT` tag. Source: Session 95b Nolan feedback.

---

## Sub-Files

| File | Content |
|------|---------|
| [docs/backlog/COMPLETED_SESSIONS.md](backlog/COMPLETED_SESSIONS.md) | All completed session history (Sessions 1-46) |
| [docs/backlog/FEATURE_MATRIX_FRONTEND.md](backlog/FEATURE_MATRIX_FRONTEND.md) | Bugs + Front-End/UX items (Sections 1-2) |
| [docs/backlog/FEATURE_MATRIX_BACKEND.md](backlog/FEATURE_MATRIX_BACKEND.md) | Backend + ML + Annotations + Infra (Sections 3-6) |
| [docs/backlog/FEATURE_MATRIX_OPS.md](backlog/FEATURE_MATRIX_OPS.md) | Testing + Docs + Roles + Vision (Sections 7-10) |
