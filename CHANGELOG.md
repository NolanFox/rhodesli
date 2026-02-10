# Changelog

All notable changes to this project will be documented in this file.

## [v0.19.2] - 2026-02-10

### Added
- **Pipeline Orchestrator** (`scripts/process_uploads.py`): Single-command upload processing pipeline — backup, download, ML processing, clustering, R2 upload, push to production, clear staging. Three modes: interactive (default), `--auto` (no prompts except clustering), `--dry-run` (preview only). Clustering step always pauses for human review. 15 new tests.
- **Pipeline Documentation** (`docs/ops/PIPELINE.md`): Quick start, step-by-step guide, manual commands, common issues, backup restoration.

### Changed
- Updated `.claude/rules/photo-workflow.md` to reference orchestrator as canonical pipeline command.
- Test count: 1245 → 1260 (15 new pipeline orchestrator tests)

## [v0.19.1] - 2026-02-10

### Added
- **Sync Push API** (`POST /api/sync/push`): Token-authenticated endpoint for pushing locally-processed data (identities.json, photo_index.json) back to production. Creates timestamped backups before overwriting. Companion CLI: `scripts/push_to_production.py`. 9 new tests.
- **Upload Pipeline Stress Test**: End-to-end test of the full upload pipeline — download staged, ML processing, clustering, R2 upload, push to production, clear staging. Pipeline report: `docs/sessions/pipeline-test-report-20260210.md`.

### Fixed
- **Data corruption during test suite**: `/api/photo/{id}/collection` route called `photo_reg.save()` directly instead of `save_photo_registry()`, bypassing test mocks and overwriting real `data/photo_index.json` with fixture data on every test run.

### Changed
- Test count: 1235 → 1245 (9 new sync push tests, 1 data corruption fix)

## [v0.19.0] - 2026-02-10

### Added
- **Anonymous Guest Contributions**: Visitors can suggest names and annotations without creating an account. `POST /api/annotations/submit` now shows a guest-or-login modal (not 401) for anonymous users, preserving typed input. New `POST /api/annotations/guest-submit` saves annotations as `anonymous` with `pending_unverified` status. New `POST /api/annotations/stash-and-login` stores annotation in session, shows inline login form, and auto-submits after authentication. OAuth callback also submits stashed annotations. Admin approvals page shows guest annotations with amber "Guest" badge, sorted after authenticated submissions. 12 new tests.

### Changed
- Test count: 1221 → 1235 (14 new/updated tests)

## [v0.18.0] - 2026-02-10

### Added
- **Contributor Merge Suggestions** (Phase 3): Role-aware merge buttons — admins see "Merge", contributors see "Suggest Merge". New `POST /api/identity/{target}/suggest-merge/{source}` endpoint creates `merge_suggestion` annotations. Admin approvals page shows merge suggestions with face thumbnails and "Execute Merge" button. Match mode shows "Suggest Same" for contributors. 18 new tests.
- **Bulk Photo Select Mode** (Phase 7): Select toggle in photo grid filter bar, checkboxes on photo cards, floating action bar with Select All/Clear/Move to Collection. `POST /api/photos/bulk-update-source` endpoint for admin bulk collection reassignment. Event delegation for all interactions. 13 new tests.
- **Login Prompt Modal** (Phase 1): HTMX 401 interceptor extracts `data-auth-action` from trigger element for contextual login messages. Signup link in login modal. `?next=` redirect parameter on login page.
- **Compare Faces UX Overhaul** (Phase 4): Face/photo toggle view, clickable identity names, "1 of N" navigation counter, max-w-5xl modal sizing. 7 new tests.
- **Button Prominence** (Phase 6): View All Photos and Find Similar promoted from underline links to styled buttons with icons. 3 new tests.

### Changed
- **UI Clarity** (Phase 8): "Confirmed" → "People" in sidebar, mobile tabs, stat bar. "Skipped" → "Needs Help" in sidebar and stat bar. Section descriptions added to Inbox, People, Needs Help headers. Empty states rewritten with friendly guidance messages. 9 new tests.
- **Landing Page** (Phase 5): Fixed unidentified stat to include SKIPPED faces. Rewrote About section with historical Rhodes community content (La Juderia, 1492, diaspora). Dynamic `/about` page with community/diaspora/project/FAQ sections. 11 new tests.
- Test count: 1152 → 1221 (69 new tests across 6 new test files)

## [v0.17.2] - 2026-02-10

### Added
- **EXIF Ingestion Integration** (BE-013): `extract_exif()` now runs during `process_single_image()`, storing date_taken, camera, and GPS location on photo records. Camera added to PhotoRegistry metadata allowlist. Best-effort — EXIF failures never break ingestion. 9 new tests.
- **Route Permission Boundary Tests**: 61 tests covering 14 admin data-modification routes (confirm, reject, merge, undo-merge, detach, rename, skip, reset, bulk-merge, bulk-reject, collection, identity/photo metadata). Each route tested for anonymous(401), non-admin(403), admin(success), auth-disabled(pass). Cross-cutting tests for 401 empty body, 403 toast, no 303 redirects.

### Fixed
- **Graceful Error Handling**: `IdentityRegistry.load()` and `PhotoRegistry.load()` now catch `JSONDecodeError` and `KeyError` with descriptive messages. `load_registry()`, `load_photo_registry()`, and `_load_annotations()` degrade to empty defaults instead of crashing the server. 23 new tests.

### Changed
- Test count: 1059 → 1152 (93 new tests across 3 new test files)

## [v0.17.1] - 2026-02-10

### Added
- **Golden Set Analysis Improvements** (ML-011): Refactored `analyze_golden_set.py` into testable `analyze_golden_set()` function, auto-generates from confirmed identities when golden set is missing, graceful empty-set handling. 15 new tests.
- **Contributor Permission Boundary Tests**: 7 safety tests confirming contributors cannot merge, confirm, reject, skip, or approve annotations. Verified `is_trusted_contributor()` is not wired into any route guard.
- **Role Permissions Documentation**: `docs/ROLES.md` with complete permission matrix for viewer/contributor/trusted/admin roles.
- **Undo Merge Route Tests**: 5 route-level HTTP tests covering undo button in toast, contributor rejection, identity restoration, and error paths (no history, nonexistent identity).
- Test count: 1032 → 1059

## [v0.17.0] - 2026-02-10

### Added
- **Merge Audit Snapshots** (BE-005): `source_snapshot` and `target_snapshot_before` saved in every merge_history entry for full reversibility
- **Annotation Merging** (BE-006): `_merge_annotations()` retargets identity annotations when identities are merged
- **Photo-Level Annotations** (AN-002–AN-006): `_photo_annotations_section()` displays approved annotations and provides submission form for captions, dates, locations, stories, and source attributions
- **Photo Metadata** (BE-012): `set_metadata()`/`get_metadata()` on PhotoRegistry with allowlisted fields (date_taken, location, caption, occasion, donor, camera). Admin endpoint `POST /api/photo/{id}/metadata`. Display integrated into photo viewer.
- **EXIF Extraction** (BE-013): `core/exif.py` extracts date, camera, GPS from uploaded photos with deferred PIL imports for testability
- **Golden Set Diversity Analysis** (ML-011): `scripts/analyze_golden_set.py` examines identity distribution, pairwise potential, collection coverage. Dashboard section shows key metrics.
- **Identity Metadata Display** (AN-012): `_identity_metadata_display()` shows bio, birth/death years, birthplace, maiden name, relationships on identity cards
- **Identity Annotations Section** (AN-013/AN-014): `_identity_annotations_section()` with approved annotation display and contributor submission form for bio, relationship, story types
- **Contributor Role** (ROLE-002): `User.role` field (admin/contributor/viewer), `CONTRIBUTOR_EMAILS` env var, `_check_contributor()` permission helper
- **Trusted Contributor** (ROLE-003): `is_trusted_contributor()` auto-promotes users with 5+ approved annotations
- **63 new tests** across 5 new test files (test_merge_enhancements, test_photo_annotations, test_photo_metadata, test_identity_annotations, test_contributor_roles)
- Test count: 969 → 1032

## [v0.16.0] - 2026-02-10

### Added
- **ML Pipeline Improvements**:
  - Post-merge re-evaluation: after merging identities, nearby HIGH+ confidence faces are shown inline for immediate review
  - Rejection memory in clustering: `cluster_new_faces.py` now checks `negative_ids` before matching, preventing re-suggestion of explicitly rejected pairs
  - Ambiguity detection: margin-based flagging when top two matches are within 15% distance of each other
- **ML Evaluation Dashboard** (ML-013): Admin page at `/admin/ml-dashboard` showing identity stats, golden set results, calibrated thresholds, and recent actions
- **Annotation System** (AN-001–AN-005): Full submit/review/approve/reject workflow
  - `POST /api/annotations/submit` — logged-in users submit name suggestions with confidence levels
  - `GET /my-contributions` — user's annotation history with status tracking
  - `GET /admin/approvals` — admin review queue for pending annotations
  - `POST /admin/approvals/{id}/approve` and `/reject` — annotation moderation
- **Structured Names** (BE-010): `rename_identity()` auto-parses first_name/last_name from display name
- **Identity Metadata** (BE-011): `set_metadata()` on IdentityRegistry with allowlisted keys (birth_year, death_year, birth_place, maiden_name, bio, etc.)
  - `POST /api/identity/{id}/metadata` — admin endpoint for editing metadata fields
- **Suggest Name UX**: Non-admin users see "Suggest Name" button on identity focus cards, submitting via annotation system
- **Activity Feed** (ROLE-005): `/activity` route showing recent identifications and approved annotations
- **Welcome Modal** (FE-052): First-time visitor welcome with archive overview, dismissed via session flag
- **43 new tests** across 5 new test files (test_post_merge, test_cluster_new_faces additions, test_ml_dashboard, test_annotations, test_metadata, test_activity_feed)
- Test count: 926 → 969

## [v0.15.0] - 2026-02-10

### Added
- **Staged File Sync API**: Three new endpoints for downloading uploaded photos from production to local machine for ML processing:
  - `GET /api/sync/staged` — list all staged upload files with metadata
  - `GET /api/sync/staged/download/{path}` — download individual staged files (path traversal protected)
  - `POST /api/sync/staged/clear` — remove staged files after processing
- **Download Script** (`scripts/download_staged.py`): Pull staged uploads from production with `--dry-run`, `--clear-after`, and `--dest` flags.
- **Upload Processing Orchestrator** (`scripts/process_uploads.sh`): End-to-end pipeline — download → ingest → cluster → R2 upload → deploy → clear staging. Supports `--dry-run`.
- **18 new tests** for staged sync endpoints (auth, listing, download, path traversal, clearing).
- Test count: 925 → 943

### Changed
- Updated `docs/PHOTO_WORKFLOW.md` with complete upload processing pipeline documentation.

## [v0.14.1] - 2026-02-10

### Fixed
- **Clustering ignores skipped faces**: `cluster_new_faces.py` now includes SKIPPED identities (192 faces) as candidates alongside INBOX and PROPOSED. Previously reported "0 new proposals" for the largest pool of unresolved work.
- **Lightbox face overlays not clickable**: Face overlays in the identity-card lightbox now have click handlers — clicking navigates to the identity's face card in the correct section.
- **Identity links route to wrong section**: `neighbor_card`, `identity_card_mini`, and lightbox face overlays now route to the correct section based on identity state (confirmed/skipped/to_review/rejected) instead of hardcoding `section=to_review`.
- **Footer stats exclude skipped**: Sidebar footer "X of Y identified" now includes skipped faces in denominator (was "23 of 23" → "23 of 215 identified").

### Added
- `_section_for_state()` helper in `app/main.py` — canonical mapping from identity state to sidebar section.
- 9 new tests in `tests/test_skipped_faces.py` covering all 4 bugs.
- Test count: 891 → 900

## [v0.14.0] - 2026-02-10

### Added
- **Token-Authenticated Sync API**: Three new endpoints — `/api/sync/status` (public stats), `/api/sync/identities` and `/api/sync/photo-index` (Bearer token auth). Replaces cookie-based export that never worked for scripts.
- **Sync Script** (`scripts/sync_from_production.py`): Python script with `--dry-run`, `--from-zip` fallback, auto-backup before overwrite, diff summary. Uses `RHODESLI_SYNC_TOKEN` env var.
- **Token Generator** (`scripts/generate_sync_token.py`): Generates secure token with Railway + local setup instructions.
- **Backup Script** (`scripts/backup_production.sh`): Timestamped backups of data files, auto-cleans to keep last 10.
- **ML Refresh Pipeline** (`scripts/full_ml_refresh.sh`): One-command sync -> backup -> golden set -> evaluate -> validate -> dry-run apply.
- **12 new tests** for sync API permission matrix (token validation, 503 on unconfigured, public status endpoint).

### Changed
- `SYNC_API_TOKEN` added to `core/config.py` (from `RHODESLI_SYNC_TOKEN` env var)
- Test count: 879 → 891

## [v0.13.0] - 2026-02-09

### Added
- **AD-013: Evidence-Based Threshold Calibration**: Four-tier confidence system (VERY_HIGH/HIGH/MODERATE/LOW) based on golden set evaluation (90 faces, 23 identities, 4005 pairwise comparisons). Zero false positives up to distance 1.05.
- **Clustering Validation Script** (`scripts/validate_clustering.py`): Compares clustering proposals against admin tagging decisions. Reports agreed/disagreed/skipped/rejected with per-distance-band analysis.
- **Threshold Calibration Script** (`scripts/calibrate_thresholds.py`): Combines golden set evaluation + clustering validation to recommend evidence-based thresholds.
- **Cluster Match Application** (`scripts/apply_cluster_matches.py`): Tiered application of clustering matches with --tier very_high|high|moderate and mandatory dry-run default. 33 matches ready at HIGH tier.
- **15 new tests**: confidence_label boundaries (7), apply_suggestions safety (4), threshold config ordering (4).

### Changed
- `MATCH_THRESHOLD_HIGH` raised from 1.00 to 1.05 (zero false positives, +10pp recall)
- New thresholds: `MATCH_THRESHOLD_VERY_HIGH=0.80`, `MATCH_THRESHOLD_MODERATE=1.15`, `MATCH_THRESHOLD_LOW=1.25`
- UI confidence labels now show 5 tiers: Very High, High, Moderate, Medium, Low
- `cluster_new_faces.py` uses calibrated `confidence_label()` function
- Test count: 864 → 879

## [v0.12.1] - 2026-02-09

### Fixed
- **BUG-005: Face count badges wildly wrong**: Badge denominator used raw embedding detection count (e.g., 63 for a 3-person newspaper photo). Now filters to only registered faces from photo_index.json. Also fixes lightbox "N faces detected" and removes noise face overlays. 5 tests.
- **BUG-006: Photo navigation dies after few clicks**: Duplicate keydown listeners (one in photo_nav_script, one in global delegation) caused double navigation per key press. Removed the per-section handler. 6 tests.
- **BUG-007: Rhodesli logo doesn't link home**: Sidebar header "Rhodesli / Identity System" wrapped in `<a href="/">`. 2 tests.
- **BUG-008: Client-side fuzzy search not working**: Sidebar filter used `indexOf` (exact substring). Now includes JS Levenshtein distance with threshold-based fuzzy matching per word. "Capeluto" matches "Capelluto". 4 tests.

### Changed
- Test count: 847 → 864 (17 new tests across 4 test files)
- `_build_caches()` restructured: loads photo_index.json first, filters faces, then builds reverse mapping

## [v0.12.0] - 2026-02-08

### Added
- **Identity-Context Photo Navigation**: Face card and search result clicks now compute prev/next arrows from the identity's photo list. No more "no arrows" dead ends. 11 tests.
- **Mobile Bottom Tabs** (FE-011): Fixed bottom tab bar with Photos, Confirmed, Inbox, Search tabs. Hidden on desktop (lg:hidden). Active section highlighting. 6 tests.
- **Progress Dashboard** (FE-053): Landing page identification progress bar showing "X of Y faces identified" with percentage and help CTA. 5 tests.
- **Fuzzy Name Search** (FE-033): Levenshtein edit distance fallback when exact substring match returns no results. "Capeluto" finds "Capelouto" (distance 1). 6 tests.
- **Search Match Highlighting**: Matched portion of names highlighted in amber in search results. 5 tests.
- **Inline Face Actions**: Admin users see hover-visible confirm/skip/reject icon buttons on face overlays in photo view. New `/api/face/quick-action` endpoint. 17 tests.
- **Confirmed Face Click**: Clicking a confirmed face overlay in photo view navigates to the identity card instead of opening the tag dialog.

### Fixed
- **Search Navigation**: Search results now navigate to the correct identity via hash fragment scrolling + 2s highlight ring animation (was silently ignoring `?current=` param)
- **Merge History Backfill**: Added `scripts/backfill_merge_history.py` to populate stub merge_history entries for 24 pre-existing merges. Undo UI no longer shows empty state unexpectedly.

### Changed
- Test count: 799 → 847 (48 new tests across 5 test files)
- Photo view routes now pass admin status for conditional inline actions
- All `photo_view_content()` callers updated with `is_admin` parameter

## [v0.11.0] - 2026-02-08

### Added
- **Merge Direction Tests**: 18 tests covering auto-correction (named identity always survives), undo safety, state promotion, name conflict resolution, and tiebreakers
- **Event Delegation Lightbox** (BUG-001 permanent fix): All photo navigation uses data-action attributes with ONE global click/keydown listener. No more HTMX swap breakage. 16 regression tests.
- **Universal Keyboard Shortcuts** (FE-002/FE-003): Match mode (Y/N/S), Focus mode (C/S/R/F), and photo navigation all consolidated in one global keydown handler with input field suppression. 10 tests.
- **Client-side Instant Search** (FE-030/FE-031): Sidebar identity list has data-name attributes and 150ms debounced client-side filter. Server-side search preserved as fallback. 13 tests.
- **Skip Hints**: Skipped section lazy-loads ML suggestions showing top 3 similar confirmed identities ("Might be: Leon Capeluto (dist 0.82, +15% gap)"). 6 tests.
- **Confidence Gap**: Neighbor results now show relative ranking — how much closer the best match is vs next-best, as a percentage margin. Helps humans adjudicate comparative evidence.
- **Smoke Tests**: 21 tests verifying all major routes return 200, required scripts are loaded, interactive elements have correct attributes.
- **Canonical Collection Stats** (BUG-004 fix): `_compute_sidebar_counts()` replaces 4 inline stats computations. 11 regression tests.
- **About Page** (`/about`): Heritage context, how-to-help guide, FAQ (Skip, Merge, Undo), live archive stats. 10 tests.
- **Unified Lightbox** (FE-004): Consolidated two separate modal systems (#photo-modal and #photo-lightbox) into one. "View All Photos" and face-click photo viewing now share the same modal component. 11 tests.

### Fixed
- **BUG-001**: Lightbox arrows disappear after HTMX swap — permanent fix with event delegation (4th and final attempt)
- **BUG-002**: Face count label now shows displayed face boxes, not raw detection count
- **BUG-003**: Merge direction already fixed in v0.10.0 code; now has 18 direction-specific tests confirming correctness
- **BUG-004**: Collection stats inconsistency — single canonical function

### Changed
- Test count: 663 → 787 (124 new tests)
- CLAUDE.md rule #12: event delegation mandatory for HTMX apps
- Neighbor cards show confidence gap instead of raw percentile
- Focus mode keyboard handler removed (consolidated into global handler)

## [v0.10.0] - 2026-02-08

### Added
- **Face Overlay Status Colors**: Overlays now use status-based colors instead of all-green
  - CONFIRMED: green border + ✓ badge
  - PROPOSED: indigo border (ML suggestion)
  - SKIPPED: amber border + ⏭ badge
  - REJECTED: red border + ✗ badge
  - INBOX/unassigned: dashed gray border (needs attention)
- **Photo Completion Badges**: Grid cards show progress (green=all done, indigo=partial N/M, dark=none)
- **Single Tag Dropdown**: Clicking a face overlay now closes other open dropdowns first
- **Create Identity from Tag**: "+ Create New Identity" button in tag search autocomplete
- **Keyboard Shortcuts**: Focus mode actions via C=Confirm, S=Skip, R=Reject, F=Find Similar
- **Proposals Admin Page**: `/admin/proposals` page with sidebar nav link for reviewing proposed matches
- **Mobile Touch Swipe**: Swipe left/right to navigate photos in the photo modal
- **AD-013**: Documented cluster_new_faces.py fix from centroid to multi-anchor matching

### Fixed
- **Multi-merge bug (3rd attempt)**: FastHTML bare `list` annotation splits strings into character lists; fixed to `list[str]`
- **Lightbox arrows disappearing**: Arrows after photo 2+ broke because prev_id/next_id weren't passed; switched to client-side `photoNavTo()`
- **Collection stats wrong when filtered**: Subtitle showed global stats instead of filtered collection count
- **AD-001 violation in cluster_new_faces.py**: Replaced centroid averaging with multi-anchor best-linkage using `scipy.cdist`
- **Mobile responsive**: Match mode stacks vertically, modals fill screen, 44px touch targets, responsive autocomplete

### Changed
- Mobile responsive improvements across all workstation pages
- Focus mode action buttons now have id attributes for keyboard targeting
- Photo grid face count badge redesigned with completion semantics
- Golden set rebuilt: 90 faces, 23 identities, threshold analysis saved

## [v0.9.0] - 2026-02-07

### Added
- **Photo Navigation**: Keyboard arrow keys (Left/Right) and prev/next buttons for browsing photos in lightbox; Escape to close
- **Match Mode Redesign**: Larger face display, confidence percentage bar, clickable faces to view source photo, decision logging to JSONL
- **Face Tagging**: Instagram-style tag dropdown on face overlays with autocomplete search and one-click merge
- **Identity Notes**: Add/view notes on identities with author tracking and timestamps
- **Proposed Matches**: Propose, list, accept/reject match suggestions between identities without immediate merge
- **Collection Stats Cards**: Per-collection photo/face/identified counts displayed above photo grid, clickable to filter
- **Collection Reassignment**: Admin endpoint to change a photo's collection (`POST /api/photo/{id}/collection`)
- **Clustering Report**: Dry-run clustering report for Betty Capeluto collection (35 high-confidence matches found)

### Fixed
- **Multi-merge form bug**: HTMX ignored `formaction` on buttons; moved `hx_post` to individual buttons with `hx_include`
- **Checkbox toggle bug**: `toggle @checked` modified HTML attribute, not JS `.checked` property; switched to property assignment
- **Carousel "+N More" count static**: `get_next_focus_card()` now returns both card and carousel in `#focus-container`
- **Main face image not clickable**: Wrapped main face in Focus mode with photo modal trigger
- **Registry shallow-copy bug**: `add_note()` and `resolve_proposed_match()` modified copies from `get_identity()` instead of originals

## [v0.8.0] - 2026-02-06

### Added
- **UX Overhaul**: Merge system, redesigned landing page, sidebar navigation, face cards, inbox workflow
- **Pending Upload Queue**: Admin moderation queue for user-submitted photos
- **ML Clustering Pipeline**: Golden set evaluation harness and face matching
- **Landing Page**: Public-facing landing page with project intro
- **Admin Export**: Data export functionality for admin users
- **Mobile CSS**: Responsive layout improvements for mobile devices
- **Design Docs**: `docs/design/MERGE_DESIGN.md`, `docs/design/FUTURE_COMMUNITY.md`

### Fixed
- **9 pre-existing test failures**: Stale assertions from UI changes (landing page, colors, URL prefixes)
- **Uploaded photos not rendering in R2 mode**: Photos served from R2 instead of local filesystem
- **Photo source lookup for inbox IDs**: Added filename-based fallback in `_build_caches()` for inbox-style photo IDs

### Changed
- Consolidated photo storage to single `raw_photos/` path (removed separate uploads directory)
- Split `docs/SYSTEM_DESIGN_WEB.md` (1,373 lines) into 4 focused docs under `docs/architecture/`
- Restructured `CLAUDE.md` to stay under 80 lines with `@` references to docs

## [v0.7.0] - 2026-02-05

### Added
- **Password Recovery**: Full forgot-password flow with Supabase `/auth/v1/recover`
- **Google OAuth Social Login**: One-click Google Sign-In via Supabase OAuth
- **Email Templates**: Branded confirmation and recovery email templates via Supabase Management API
- **Login Modal**: HTMX-powered login modal for protected actions (no page redirect)
- **Styled Confirmation Dialog**: Custom confirmation dialog replacing browser `confirm()`
- **Regression Test Suite**: Comprehensive test harness with permission matrix tests
- **Testing Requirements**: Mandatory testing rules added to `CLAUDE.md`

### Fixed
- **Facebook login button removed**: OAuth deferred — Meta requires Business Verification
- **Email button legibility**: Inline styles instead of `<style>` blocks (stripped by email clients)
- **Password recovery redirect**: Added `redirect_to` parameter for correct landing page
- **PKCE code exchange**: Fixed auth hash fragment handling for Supabase PKCE flow
- **Auth hash fragment errors**: Friendly error messages for malformed auth callbacks
- **Upload permissions**: Restricted to admin-only until moderation queue exists

### Changed
- Google Sign-In button uses official branding guidelines
- All HTMX auth failures return 401 (not 303) with `beforeSwap` handler for login modal

## [v0.6.0] - 2026-02-05

### Added
- **Supabase Authentication (Phase B)**: Invite-only auth with login/signup/logout
  - `app/auth.py` — Supabase client with graceful degradation (disabled when env vars unset)
  - Login, signup, and logout routes in `app/main.py`
  - Beforeware-based route protection (conditional on auth being configured)
  - Invite code validation for signup access control
  - Session management via FastHTML's built-in session support

### Fixed
- **Find Similar 500 error**: Added `scipy` to `requirements.txt` (was missing — only in requirements-local.txt). Added error handling around the neighbors endpoint.

### Changed
- `requirements.txt` — Added scipy, supabase>=2.0.0
- `.env.example` — Updated auth configuration section with Supabase env vars
- `CLAUDE.md` — Added Boris Cherny autonomous workflow protocol

## [v0.5.1] - 2026-02-05

### Fixed
- **Single Railway Volume**: Railway only supports one volume per service
  - Added `STORAGE_DIR` environment variable for single-volume mode
  - When set, `DATA_DIR` and `PHOTOS_DIR` are derived automatically
  - Init script creates subdirectories: `data/`, `raw_photos/`, `staging/`
  - Local development unchanged (uses `DATA_DIR` and `PHOTOS_DIR` directly)

### Changed
- `core/config.py`: Added `STORAGE_DIR` logic with fallback to individual paths
- `scripts/init_railway_volume.py`: Supports single-volume mode
- `app/main.py`: Uses config paths instead of hardcoded project-relative paths
- `Dockerfile`: Creates `/app/storage` directory, updated comments
- `docs/DEPLOYMENT_GUIDE.md`: Updated for single volume setup
- `.env.example`: Added `STORAGE_DIR` documentation

### Documentation
- Added "Deployment Impact Rule" to CLAUDE.md

## [v0.5.0] - 2026-02-05

### Added
- **Railway Deployment**: Full Docker-based deployment configuration
- `Dockerfile` using python:3.11-slim with lightweight web dependencies only
- `.dockerignore` excluding dev files, tests, and ML dependencies
- `railway.toml` with health check configuration
- `.env.example` documenting all environment variables
- `scripts/init_railway_volume.py` for first-run data seeding
- `/health` endpoint returning status, identity/photo counts, processing mode
- `PROCESSING_ENABLED` environment variable to control ML processing
- `docs/DEPLOYMENT_GUIDE.md` with step-by-step Railway + Cloudflare setup

### Changed
- `core/config.py` now includes server configuration (HOST, PORT, DEBUG, etc.)
- `app/main.py` uses environment variables for host/port/debug settings
- Upload handler checks `PROCESSING_ENABLED`:
  - When `false`: stores files in `data/staging/` for admin review (no ML)
  - When `true`: spawns subprocess for ML processing (local dev)
- Added Pillow to `requirements.txt` (needed for image dimensions)
- Updated `.gitignore`: added `.env`, `data/staging/`
- Comprehensive startup logging showing config and data stats

### Architecture
- **Clean Vercel Constraint Maintained**: Docker image uses only `requirements.txt`
- ML dependencies (`requirements-local.txt`) are NOT installed in production
- Production workflow: web users upload → staging → admin processes locally → sync back

## [v0.4.0] - 2026-02-04

### Added
- **Source Attribution**: Photos now track provenance/collection metadata
- `source` field in PhotoRegistry schema (backward compatible)
- Source input field on upload form with autocomplete suggestions
- Source display in Photo Context modal
- **Photo Viewer**: New photo-centric browsing section
- "Browse > Photos" sidebar navigation
- Photo grid showing thumbnails, face counts, identified faces
- Filter by collection dropdown
- Sort options: newest, oldest, most faces, by collection
- `scripts/migrate_photo_sources.py` for classifying existing photos
- `--source` CLI argument for ingestion pipeline

### Changed
- PhotoRegistry now stores `source` alongside `path` and `face_ids`
- Upload endpoint accepts and passes source to subprocess
- Index route accepts `filter_source` and `sort_by` query params

### Fixed
- N/A

## [v0.3.9] - 2026-02-04

### Added
- **Darkroom Theme**: Professional dark mode for forensic workstation aesthetic
- `.font-data` CSS class for monospace data elements (filenames, IDs, quality scores)
- Photo filename display in Photo Context modal

### Changed
- Body background from light gray (#f9fafb) to slate-900 (#0f172a)
- Sidebar to slate-800 with slate-700 borders
- All UI components (cards, modals, inputs, buttons) themed for dark mode
- Text colors updated: gray/stone-* to slate-* equivalents
- Accent colors maintained for state indicators (green=confirmed, yellow=skipped, red=rejected, blue=inbox)

### Fixed
- **Photo filename not showing**: Filename now displays in Photo Context modal with monospace styling
- **Face click navigation broken**: Clicking a face bounding box in Photo Context now properly navigates to that identity's section based on state (Confirmed/Inbox/Skipped/Rejected)

## [v0.3.8] - 2026-02-04

### Added
- **Command Center UI**: Complete redesign with fixed sidebar navigation
- `sidebar()` component with section navigation and live counts
- Focus Mode: Review one identity at a time with prominent actions
- Browse Mode: Traditional grid view for scanning
- `identity_card_expanded()` for focus mode display
- `identity_card_mini()` for queue preview
- `get_next_focus_card()` helper for focus mode flow
- `section_header()` component with Focus/Browse toggle
- Section-specific rendering functions
- URL parameters: `section` (to_review/confirmed/skipped/rejected) and `view` (focus/browse)

### Changed
- Main route now uses sidebar + main content layout
- Action endpoints support `from_focus=true` to return next focus card
- Default view is Focus mode showing one item prominently
- Removed old header with "Rhodesli Forensic Workstation" title

### Fixed
- Actions in focus mode now advance to next item instead of showing completed card
- **Upload button 405**: Added GET handler for `/upload` route
- **View Full Photo stuck loading**: Fixed endpoint from non-existent `/api/photo/{id}/context` to `/photo/{id}/partial`
- **Face thumbnails not clickable**: Wrapped faces in buttons with photo modal handler
- **Find Similar anchor navigation fails**: Added fallback navigation when target element doesn't exist in Focus mode
- **Up Next thumbnails not clickable**: Made thumbnails links with `current` parameter to load specific identity
- **Skip ordering mismatch**: Aligned sorting in `get_next_focus_card()` with visual queue (sort by date then face count)

### Documentation
- Added `docs/POST_MORTEM_UI_BUGS.md` - Root cause analysis of 6 interaction bugs
- Added `docs/INTERACTION_TESTING_PROTOCOL.md` - Testing protocol to prevent render-but-don't-work bugs

## [v0.3.7] - 2026-02-04

### Added
- `SKIPPED` state to `IdentityState` enum for deferred reviews
- `skip_identity()` and `reset_identity()` functions in registry
- `SKIP` and `RESET` action types for event logging
- `/identity/{id}/skip` endpoint to defer items for later
- `/identity/{id}/reset` endpoint to return any state to Inbox
- Unified `review_action_buttons()` showing state-appropriate buttons
- stone/rose colors for Skipped/Rejected sections

### Fixed
- **Vanishing reject bug**: Rejected items now fetched and rendered in Rejected section
- `confirm_identity()` and `reject_identity()` now accept SKIPPED state

### Changed
- Main page shows 4 sections: Inbox, Confirmed, Skipped, Rejected
- Inbox section combines INBOX + PROPOSED states
- Rejected combines REJECTED + CONTESTED states
- All identity cards now show appropriate action buttons for their state

### Removed
- Old `action_buttons()` with UI-only hyperscript skip
- Old `skipped_section()` collapsible (replaced with proper lane_section)

## [v0.3.6] - 2026-02-04

### Added
- Ingestion-time face grouping: similar faces are automatically grouped into one inbox identity
- `core/grouping.py`: `group_faces()` using Union-Find for transitive grouping
- `GROUPING_THRESHOLD = 0.95` in `core/config.py` (stricter than Find Similar)
- `grouped_faces` count in identity provenance for transparency
- 15 new tests for grouping functionality (`tests/test_grouping.py`)

### Changed
- `create_inbox_identities()` now groups faces before creating identities
- Uploading 10 photos of same person → 1 inbox identity (was 10)

## [v0.3.5] - 2026-02-04

### Fixed
- Manual search showing blank grey thumbnails instead of face photos
- Manual search results not clickable (missing navigation links)
- `search_identities()` now falls back to `candidate_ids` when `anchor_ids` is empty
- `search_result_card()` now wraps thumbnail and name in clickable `<a>` tags

### Changed
- `test_rename_identity` now restores original name after test (prevents data corruption)

### Data
- Restored "Victoria Cukran Capeluto" identity name (corrupted by test to "Test Person Name")

## [v0.3.4] - 2026-02-04

### Fixed
- View Photo returning 404 for inbox uploads stored in `data/uploads/`
- `/photos/` endpoint now serves from both `raw_photos/` and `data/uploads/`

### Added
- `_photo_path_cache` for O(1) photo path resolution from photo_index.json
- `serve_photo()` dynamic route replacing StaticFiles mount
- Startup validation warns about missing photo files
- Integration tests for photo serving (`tests/test_photo_serving_integration.py`)

## [v0.3.3] - 2026-02-04

### Fixed
- Identities displaying as "Identity <UUID>..." instead of "Unidentified Person XXX"
- View Photo showing wrong photo or "Could not load" for inbox uploads
- `generate_photo_id()` now uses full path for absolute paths to avoid collisions

### Changed
- Backfilled 88 historical identities with proper sequential names

## [v0.3.2] - 2026-02-03

### Fixed
- Find Similar returning no results for inbox faces
- `load_face_embeddings()` now preserves stored `face_id` instead of regenerating
- `load_embeddings_for_photos()` applies same fix for photo context views

### Added
- Contract tests for face_id preservation (`tests/test_face_record_contract.py`)

## [v0.3.1] - 2026-02-03

### Fixed
- Inbox lane showing 0 items despite identities existing with `state=INBOX`
- `resolve_face_image_url()` now handles inbox face_id format (`inbox_{hash}`)

### Added
- Contract tests for inbox visibility invariant (`tests/test_inbox_contract.py`)

## [v0.3.0] - 2026-02-03

### Added
- `list_identities_by_job(job_id)` method to IdentityRegistry for querying artifacts by job
- `core/file_hash_registry.py` module for SHA256 content hashing and deduplication
- File-level idempotency checking in ingestion pipeline (skip already-processed files)
- `scripts/cleanup_job.py` script for surgical cleanup of failed uploads
- `--dry-run` and `--execute` modes for cleanup with automatic backup
- `data/orphaned_face_ids.json` for soft-delete tracking (embeddings remain immutable)

### Changed
- Ingestion pipeline now checks file hashes before processing to prevent duplicates
- All process_single_image calls now pass file_hash_path for idempotency tracking

### Fixed
- Duplicate identities created when retrying failed uploads

## [v0.2.3] - 2026-02-03

### Fixed
- UnicodeEncodeError crash when rendering strings with surrogate escapes
- Malformed emoji literals using invalid surrogate pair notation

### Added
- `core/ui_safety.py` module with `ensure_utf8_display()` for UI boundary sanitization
- `has_surrogate_escapes()` detection function for logging without mutation
- Ingestion warning for filenames containing surrogate escapes
- Comprehensive regression tests for Unicode boundary handling

### Changed
- All UI rendering paths now sanitize text through `ensure_utf8_display()`
- Emoji escapes updated from `\ud83d\udce5` to `\U0001F4E5`

## [v0.2.2] - 2026-02-03

### Fixed
- Frontend/backend contract mismatch preventing multi-file uploads
- Upload input now uses `name="files"` with `multiple=True`
- Subprocess execution context causing `ModuleNotFoundError: No module named 'core'`
- Worker subprocess now invoked with `-m core.ingest_inbox` and explicit `cwd=PROJECT_ROOT`

### Added
- `--directory` CLI option for batch ingestion of multiple files
- Support for mixed uploads (images + ZIPs in same selection)
- Job-specific upload directories for batch isolation
- `core/__init__.py` package marker (was missing)
- Regression test for worker subprocess entrypoint invocation

### Changed
- Upload handler accepts `files: list[UploadFile]` instead of single file
- Ingestion spawned with `--directory` instead of `--file` for batches
- Status message shows file count for multi-file uploads

## [v0.2.1] - 2026-02-03

### Fixed
- Test suite aligned with current API contracts (mls_score -> distance)
- Removed tests for compute_identity_centroid (intentionally omitted per design)

### Added
- ZIP ingestion with per-file error isolation
- Per-file error tracking in job metadata
- Partial success status for batch uploads with mixed results
- Real-time progress reporting driven by backend job state

### Changed
- Upload progress bar now reflects actual completion percentage
- Error reporting shows per-file failure details

## [v0.2.0] - 2026-02-03

### Added
- Inbox Review workflow with confirm/reject actions
- Manual Search & Merge for human-authorized identity merges
- Bulk ZIP-based ingestion pipeline
- Evaluation harness with Golden Set regression testing

### Changed
- Calibration updated to Leon Standard (High < 1.0, Medium < 1.20)

### Fixed
- Scalar sigma computation in uncertainty estimation (ADR-006)
