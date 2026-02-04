# Changelog

All notable changes to this project will be documented in this file.

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
