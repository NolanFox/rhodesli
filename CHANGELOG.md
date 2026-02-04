# Changelog

All notable changes to this project will be documented in this file.

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
