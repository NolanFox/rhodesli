# Release Notes

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
