# Release Notes

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
