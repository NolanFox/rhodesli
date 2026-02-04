# Release Notes

## v0.3.4 — Photo Serving Fix for Inbox Uploads

This patch fixes "View Photo" returning 404 for inbox uploads.

### Bug Summary

**Symptom:** Clicking "View Photo" for inbox faces returned 404, even though photo_id was now correctly generated.

**Root Cause:** The `/photos/` endpoint was a StaticFiles mount pointing only to `raw_photos/`. Inbox uploads are stored in `data/uploads/{job_id}/`, which the mount didn't cover.

**Fix:** Replaced StaticFiles mount with dynamic route that:
1. Checks `raw_photos/{filename}` first (legacy photos)
2. Looks up filename in `photo_path_cache` (populated from `photo_index.json` at startup)
3. Serves from the resolved absolute path

### Technical Details

- `_photo_path_cache`: dict mapping filename → full Path, loaded at startup
- `serve_photo()`: Dynamic route at `/photos/{filename:path}`, inserted at position 0 for precedence
- Startup validation warns about missing files in photo_index

### Verification

- 315 tests pass (including 5 new integration tests)
- `test_photo_serves_from_uploads`: Confirms inbox photos servable
- `test_full_user_flow_view_photo`: Tests all cached photos are servable

---

## v0.3.3 — Identity Naming and View Photo Fixes

This patch fixes two user-visible bugs in the inbox workflow.

### Bug 1: Identity Naming

**Symptom:** Identities displayed as "Identity 25f0a152..." instead of "Unidentified Person XXX"

**Root Cause:** Historical data—87 identities were created before the naming feature was added, storing `name: None` in `identities.json`.

**Fix:** Backfilled 88 identities with sequential names ("Unidentified Person 205" through "Unidentified Person 292").

### Bug 2: View Photo Collision

**Symptom:** "View Photo" showed "Could not load photo" for inbox uploads, or displayed the wrong photo.

**Root Cause:** `generate_photo_id()` used only the filename basename, so files like `uploads/session1/photo.jpg` and `uploads/session2/photo.jpg` got the same photo_id. The cache stored only the first filepath (from a deleted session).

**Fix:**
- `generate_photo_id()` now uses full path for absolute paths (inbox uploads)
- Maintains basename-only for relative paths (backward compat with raw_photos/)
- `load_embeddings_for_photos()` passes filepath to ensure correct photo_id generation

### Verification

- 292 identities now have valid names (previously: 204)
- View Photo correctly resolves inbox uploads
- 310 tests pass (including 2 new tests for photo_id generation)

---

## v0.3.2 — Face ID Index Fix

This patch fixes a critical bug where Find Similar and other embedding lookups failed for inbox faces.

### Bug Summary

After uploading images via inbox, "Find Similar" returned no results for inbox identities despite embeddings existing in `embeddings.npy`.

### Root Cause

`load_face_embeddings()` and `load_embeddings_for_photos()` in `app/main.py` ignored the stored `face_id` field and always regenerated IDs using `generate_face_id(filename, face_index)`. This created wrong keys for inbox faces:

- Stored: `inbox_574e45ca5b8d`
- Generated: `603575867.895093:face0` (WRONG)

When `find_nearest_neighbors()` looked up `inbox_574e45ca5b8d` in `face_data`, it returned nothing because the key didn't exist.

### Fix

Both functions now check for stored `face_id` first:
```python
face_id = entry.get("face_id") or generate_face_id(filename, face_index)
```

### Verification

- 261 inbox faces now correctly indexed (previously: 0)
- 286 legacy faces still work
- 305 tests pass (including 2 new contract tests)

---

## v0.3.1 — Inbox Visibility Fix

This patch fixes a critical bug where inbox items were invisible despite being correctly ingested.

### Bug Summary

After uploading images, faces were correctly extracted and identities created with `state=INBOX`, but the Inbox lane showed 0 items.

### Root Cause

The `resolve_face_image_url()` function in `app/main.py` only handled the legacy face_id format (`{stem}:face{index}`), but inbox faces use a different format (`inbox_{hash}`).

When `":face"` was not in the face_id, the function returned `None`, causing `identity_card()` to return `None`, causing the lane to render empty.

### Fix

`resolve_face_image_url()` now checks for direct `{face_id}.jpg` match first (inbox format), then falls back to legacy parsing. This is a simple, non-breaking change.

### Verification

- 87 inbox identities now render correctly
- 303 tests pass (including 3 new contract tests)
- Legacy face_id format still works

---

## v0.3.0 — Job-Aware Ingestion & Safe Rewind

This release introduces job-based tracking for all uploads, enabling surgical cleanup of failed ingestion without factory resets.

### New Features

- **Job Attribution**
  - Every identity created during upload now records its originating `job_id`
  - New `list_identities_by_job(job_id)` method for querying artifacts by job
  - All artifacts traceable back to their upload session

- **File-Level Idempotency**
  - SHA256 content hashing prevents duplicate processing on upload retries
  - Uploading the same file twice no longer creates duplicate identities
  - Hash registry stored in `data/file_hashes.json`

- **Cleanup Script (`scripts/cleanup_job.py`)**
  - Surgically remove all artifacts from a specific failed upload
  - `--dry-run` mode previews changes without executing
  - `--execute` mode removes artifacts with automatic backup
  - Creates backup in `data/cleanup_backups/` before any deletion

### Cleanup Scope

The cleanup script removes:
- Identity registry entries (by `job_id` in provenance)
- Photo registry entries (face-to-photo mappings)
- Face crop images (`app/static/crops/{face_id}.jpg`)
- File hash registry entries
- Status files (`data/inbox/{job_id}.status.json`)
- Upload directories (`data/uploads/{job_id}/`)

### Forensic Invariants Preserved

- **Embeddings are NOT modified**: `data/embeddings.npy` remains immutable
- **Soft delete via orphan tracking**: Face IDs are recorded in `data/orphaned_face_ids.json`
- **Reversible with backup**: All state files backed up before deletion

### Usage

```bash
# Preview what would be cleaned up
python scripts/cleanup_job.py JOB_ID --dry-run

# Actually remove artifacts (creates backup first)
python scripts/cleanup_job.py JOB_ID --execute
```

### Why This Matters

Previously, a failed upload could leave behind:
- Duplicate files in `uploads/`
- Duplicate identities in the registry
- No clear way to undo without a factory reset

Now you can safely retry failed uploads with confidence that duplicates will be skipped, and surgically remove artifacts if needed.

---

## v0.2.3 — Unicode Safety Fix

This release fixes a critical crash caused by Unicode surrogate escapes reaching the web rendering layer.

### Bug Fix

- **UnicodeEncodeError: surrogates not allowed**
  - The application crashed when filenames or identity names contained "surrogate escapes"
  - These are invalid UTF-8 sequences that can appear when Python's filesystem APIs encounter undecodable bytes (PEP 383)
  - Affected all response paths: HTML templates, JSON responses, and static file serving

### Solution

- **UI Boundary Sanitization**
  - New `core/ui_safety.py` module with `ensure_utf8_display()` function
  - Sanitization applied explicitly at all presentation boundaries:
    - Identity names in gallery, neighbor cards, search results
    - Display names in photo viewer overlays
    - Filenames in error messages
    - All JSON API responses
  - Internal data structures remain unchanged (no silent data corruption)

- **Malformed Emoji Fix**
  - Fixed emoji literals that used invalid surrogate pair notation (`\ud83d\udce5`)
  - Replaced with correct Unicode escape (`\U0001F4E5`)

- **Ingestion Warning**
  - Logs warning when processing files with surrogate escapes
  - Data fidelity preserved—warning only, no mutation

### Design Principle

> Sanitization is LOSSY and EXPLICIT. It must ONLY be applied at presentation boundaries.

This invariant prevents silent data corruption while guaranteeing UI stability.

### Not Changed

- Recognition logic remains frozen (per CLAUDE.md constraints)
- Internal embeddings and identity data unaffected

---

## v0.2.2 — Multi-File Upload Support

This release fixes a critical contract mismatch that prevented users from uploading multiple photos at once, plus a subprocess execution bug that could cause uploads to fail.

### Fixes

- **Subprocess Execution Context**
  - Fixed `ModuleNotFoundError: No module named 'core'` during uploads
  - Worker subprocess now uses `-m core.ingest_inbox` with explicit `cwd` set to project root
  - Created missing `core/__init__.py` package marker
  - Added regression test to prevent future subprocess invocation failures

- **Multi-File Upload**
  - Frontend now supports selecting multiple files (images and/or ZIPs)
  - Backend processes all selected files in a single batch job
  - Progress shows total files being processed, not just the first one

- **Batch Processing**
  - Mixed uploads (images + ZIPs) processed correctly
  - ZIPs within batch are expanded and processed with error isolation
  - Each file processed independently—failures don't abort the batch

### UX Improvements

- Upload text clarifies "multiple allowed"
- Status shows "Processing X files..." for multi-file uploads
- Progress bar reflects true completion across entire batch

### Not Changed

- Recognition logic remains frozen (per CLAUDE.md constraints)
- Single-file uploads continue to work as before

---

## v0.2.1 — Reliability & Hardening

This is a reliability release focused on test stability, ingestion resilience, and honest UX feedback.

### Improvements

- **Test Suite Stability**
  - Fixed legacy test failures by aligning assertions with current API contracts
  - Removed tests for intentionally-omitted centroid computation (per design doc)
  - All 258 tests now pass

- **Ingestion Resilience**
  - ZIP archives now process each image independently with error isolation
  - A single corrupt image no longer aborts the entire batch
  - Per-file errors captured and reported in job metadata

- **Upload Progress Transparency**
  - Progress bar driven by actual backend state, not timers
  - Shows real completion percentage (files processed / total)
  - Displays current file being processed
  - New "partial" status for mixed success/failure batches
  - Per-file error details visible to user

### Not Changed

- Recognition logic remains frozen (per CLAUDE.md constraints)
- No new features introduced

---

## v0.2.0 — Scale-Up & Human Review

### What's New

- **Calibrated Recognition Engine**
  - Adopted the "Leon Standard" thresholds (High < 1.0, Medium < 1.20)
  - Frozen evaluation harness with Golden Set regression testing

- **Bulk Ingestion Pipeline**
  - Atomic ZIP-based upload
  - Subprocess-driven face extraction
  - Automatic quarantine into Inbox state

- **Inbox Review Workflow**
  - Dedicated Inbox filtering
  - Human confirm vs reject actions
  - Fully logged, reversible state transitions

- **Manual Search & Merge ("God Mode")**
  - Sidebar search for confirmed identities
  - Human-authorized merges using existing safety validation
  - Provenance-aware audit logging

### Safety Guarantees

- No destructive deletes of embeddings
- All merges reversible and logged
- Human decisions override model inference
