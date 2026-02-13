# Rhodesli Project Backlog

Last updated: 2026-02-13 (Session 23b — Push + Benatar Upload Processing)

## Session 23b Completed
- [x] Push session 23 ML pipeline (4 commits) to origin/main
- [x] Download Benatar community submission (Sarina2.jpg, Job cf8d0446)
- [x] Face detection: 3 faces extracted, 3 INBOX identities created
- [x] Clustering: no strong matches (best LOW at 1.24 distance)
- [x] Upload photo + 3 crops to R2
- [x] Push data to production (156 photos, 373 identities)
- [x] Fix ingest_inbox.py absolute path bug → relative paths
- [x] Regression test for relative path invariant
- [x] Clear staging, mark job processed
- [x] Production verification: 156 photos, Community Submissions collection visible
- [x] Update Benatar feedback tracker with submission status
- [x] 1827 total tests (1826 app + 1 new)

## Session 23 Completed
- [x] Decision provenance: DATE_ESTIMATION_DECISIONS.md + AD-039 through AD-045
- [x] ML environment setup: venv, pyproject.toml (torchvision, google-genai SDK)
- [x] Gemini evidence-first date labeling script (cultural lag, 4 evidence categories, cost guardrails)
- [x] CORAL date classifier: EfficientNet-B0 backbone, soft label KL divergence
- [x] Heritage augmentations: sepia, film grain, scanning artifacts, resolution degradation, JPEG compression, geometric distortion, fading
- [x] Regression gate: adjacent accuracy ≥0.70, MAE ≤1.5, per-decade recall ≥0.20
- [x] 53 ML pipeline tests + synthetic test fixtures (30 labels + 30 images)
- [x] MLflow experiment tracking initialized (first experiment logged)
- [x] Signal harvester refresh: 959 confirmed pairs, 510 rejected pairs (+17x), 500 hard negatives
- [x] Documentation: README, CHANGELOG v0.31.0, ROADMAP, BACKLOG, current_ml_audit.md
- [x] 1879 total tests (1826 app + 53 ML)

## Session 19f Completed
- [x] Bug 1: annotations.json added to OPTIONAL_SYNC_FILES for Railway volume sync
- [x] Bug 2: Pending upload thumbnails have graceful onerror fallback
- [x] Bug 3: Mobile horizontal overflow fixed (overflow-x:hidden, responsive wrapping, nav hidden)
- [x] Bug 4: Manual search results now show Compare button before Merge
- [x] E2E sidebar test updated (Confirmed → People rename)
- [x] 12 new tests (1672 total including 19 e2e)

## Session 19e Completed
- [x] Fix test data pollution: removed 5 test annotations + 46 contaminated history entries from production
- [x] Quality scores influence Help Identify ordering: clear faces + named matches sort first
- [x] Admin staging preview: session-authenticated endpoint replaces token-only sync API for photo thumbnails
- [x] Remove duplicate Focus Mode button from admin dashboard banner
- [x] Mobile audit: verified all 5 requirements already implemented with test coverage
- [x] Feedback tracking: FEEDBACK_INDEX.md + .claude/rules/feedback-driven.md
- [x] Data safety rules: .claude/rules/data-safety.md + guard tests
- [x] 6 new tests (1641 total)

## Session 19d Completed
- [x] Face quality scoring (AD-038): composite 0-100 score, best-face selection for thumbnails
- [x] Global face crop sizing audit: larger crops everywhere, hover effects
- [x] Mobile responsiveness: verified all features already implemented (hamburger, bottom nav, stacking)
- [x] Photo enhancement research doc (docs/ml/PHOTO_ENHANCEMENT_RESEARCH.md)
- [x] Discovery UX rules (.claude/rules/discovery-ux.md) — 10 principles
- [x] Claude Benatar feedback tracker (docs/feedback/CLAUDE_BENATAR_FEEDBACK.md)
- [x] AD-038 documented in ALGORITHMIC_DECISIONS.md
- [x] CHANGELOG, ROADMAP, BACKLOG sync for v0.28.1
- [x] 13 new tests (1635 total)

## Session 19b Completed
- [x] Search AND-matching: multi-word queries now use AND logic with variant expansion
- [x] Focus Mode button routing verified (already correct from prior session)
- [x] 300px face crops in Focus Mode (w-72, ~288px desktop)
- [x] More matches strip: horizontal scrollable strip of 2nd-5th best matches
- [x] View Photo text links below face crops
- [x] Z-key undo for merge/reject/skip in Focus Mode
- [x] Admin pending uploads photo preview thumbnails
- [x] Actionability ordering verified with 3 unit tests
- [x] 22 new tests (1589 total)

## Session 19c Completed
- [x] Discovery UX research doc (docs/design/DISCOVERY_UX_RESEARCH.md)
- [x] Structured name fields (generation_qualifier, death_place, compact display)
- [x] Smart onboarding (3-step surname recognition flow)
- [x] Personalized landing page (interest surname banner)
- [x] Navigation renaming (Inbox → New Matches, Needs Help → Help Identify)
- [x] Proposal system polish (admin approvals badge, I Know This Person rename)
- [x] 33 new tests (1622 total)

## Session 19 Completed
- [x] Best Match fallback: real-time neighbor computation when proposals empty
- [x] Source photo rendering: filename fallback for photo cache
- [x] Ordering fix: batch vectorized distances via batch_best_neighbor_distances()
- [x] Welcome modal: persistent cookie replaces session-based check
- [x] Smart landing: empty inbox → Needs Help redirect
- [x] Larger face crops + confidence rings
- [x] Sticky action bar
- [x] Collapsible Similar Identities panel (toggle, not dismiss)
- [x] Reject undo toast with unreject link
- [x] 10 new tests (1567 total)

## Session 18c Completed
- [x] Focus Mode for Needs Help: guided single-identity review with photo context, actions, keyboard shortcuts
- [x] Actionability scoring: best ML leads first in Focus and Browse
- [x] Visual badges: Strong lead / Good lead in browse view
- [x] AD-030–037: 8 rejected/under-investigation approaches
- [x] DECISION_LOG.md: 18 major decisions
- [x] SUPABASE_AUDIT.md: auth-only usage
- [x] Lightbox navigation verified (49 tests, fully working)
- [x] Gender metadata assessed (not available in data, would need re-ingest)

## Active Bugs
- (none)

## Setup Required (ONE TIME)
- [ ] Generate sync token: `python scripts/generate_sync_token.py`
- [ ] Set RHODESLI_SYNC_TOKEN on Railway: `railway variables set RHODESLI_SYNC_TOKEN=<token>`
- [ ] Set RHODESLI_SYNC_TOKEN in .env: `echo 'RHODESLI_SYNC_TOKEN=<token>' >> .env`
- [ ] Deploy (push to main or Railway auto-deploy)
- [ ] Test sync: `python scripts/sync_from_production.py --dry-run`

## Ready to Apply (after sync)
- [ ] Sync production data: `python scripts/sync_from_production.py`
- [ ] Re-run ML pipeline: `bash scripts/full_ml_refresh.sh`
- [ ] Apply 19 VERY_HIGH matches: `python scripts/apply_cluster_matches.py --execute --tier very_high`
- [ ] Apply 33 HIGH matches: `python scripts/apply_cluster_matches.py --execute --tier high`
- [ ] After applying, sync to production and confirm in web UI

## Immediate (This Weekend)
- [ ] Re-run validation after sync to check if admin tagging created signal
- [ ] Test new UX features on real phone (mobile responsive, touch swipe, keyboard shortcuts)
- [ ] Share with 2-3 family members for initial feedback
- [ ] Smoke test all fixes on live site

## Near-Term (Next 1-2 Weeks)
- [ ] ML-050: Date UX integration — display estimated decade + confidence on photo viewer
- [ ] ML-051: Run `generate_date_labels.py` to silver-label all 155 photos via Gemini
- [ ] ML-052: Train date estimation model on real labels, pass regression gate
- [ ] ML-053: Integrate date labeling into upload orchestrator (process_uploads.py)
- [ ] ML-054: Multi-pass Gemini — re-label low-confidence photos with Flash model
- [ ] ML-060: Train similarity calibration model on 959 pairs + 510 rejections
- [ ] ML-061: MLS vs Euclidean golden set evaluation (does sigma_sq help?)
- [ ] OPS-001: Custom SMTP for branded "Rhodesli" email sender
- [ ] FE-041: "Help Identify" mode for non-admin users
- [ ] FE-040–FE-043: Skipped faces workflow for non-admin users

## Medium-Term (Next Month)
- [ ] FE-070–FE-073: Client-side analytics and admin dashboard
- [ ] BE-031–BE-033: Upload moderation queue with rate limiting
- [ ] ROLE-006: Email notifications for contributors
- [ ] Postgres migration (identities + photo_index -> Supabase)

## Long-Term (Quarter+)
- [ ] Family tree integration (GEDCOM, relationships)
- [ ] Auto-processing pipeline (ML on Railway, no local step)
- [ ] Age-invariant face recognition research
- [ ] Multi-tenant architecture (other communities)
- [ ] CI/CD pipeline (automated tests, staging, deploy previews)

## Completed
- [x] v0.23.0: Navigation hardening + ML pipeline scaffold (1438 tests)
  - Triage filter propagation through focus mode action chain
  - Photo nav boundary indicators (dimmed arrows at first/last)
  - Grammar pluralization helper _pl()
  - rhodesli_ml/ package: 26 files (signal harvester, date labeler, audits)
  - ML audit: 947 confirmed pairs, 29 rejections, calibration feasible
  - Photo date audit: 92% undated, silver-labeling feasible
- [x] v0.22.1: Filter consistency + promotion context (1415 tests)
  - Match mode filters (ready/rediscovered/unmatched) now work
  - Up Next thumbnails preserve active filter in navigation links
  - Promotion banners show specific context (group member names)
  - 15 new tests, lesson 63
- [x] v0.21.0: Data integrity + proposals UI + scalability (1355 tests)
  - Merge-aware push_to_production.py (production wins on conflicts)
  - Zeb Capuano identity restored (24 confirmed)
  - Clustering proposals wired to Focus/Match/Browse modes
  - Staging lifecycle (mark-processed endpoint)
  - Grammar pluralization + collections carousel
  - 4 new .claude/rules/ files
- [x] Phase A: Railway deployment + Supabase auth + permission model
- [x] Phase A stabilization: all 8 P0 bugs fixed, event delegation pattern
- [x] Phase B: Landing page, search, mobile, sync infrastructure
- [x] v0.10.0–v0.12.1: Face overlays, inline actions, fuzzy search, photo nav
- [x] v0.13.0: ML validation — threshold calibration, golden set, clustering validation
- [x] v0.14.0: Token-authenticated sync API + reliable sync script
- [x] v0.14.1: Skipped faces fix — clustering includes 192 skipped faces
- [x] v0.15.0: Upload processing pipeline — staged file sync API, download, orchestrator
- [x] v0.16.0: ML pipeline + annotation engine + collaboration (969 tests)
- [x] v0.17.0: Annotation engine + merge safety + contributor roles (1032 tests)
- [x] v0.17.1: Verification pass — golden set, permission tests, ROLES.md (1059 tests)
- [x] v0.17.2: Quality hardening — EXIF ingestion, error handling, permission tests (1152 tests)
- [x] v0.18.0: UX Overhaul + Contributor Flow (1221 tests)
  - Landing page rewrite with historical Rhodes content
  - Login prompt modals with action context
  - Section rename: Confirmed→People, Skipped→Needs Help
  - Button prominence: View All Photos + Find Similar
  - Compare faces UX: face/photo toggle, clickable names
  - Contributor merge suggestions with admin approval
  - Bulk photo select mode with collection reassignment
