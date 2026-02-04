# Release Notes

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
