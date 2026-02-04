# Release Notes

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
