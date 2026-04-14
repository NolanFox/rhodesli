---
name: Session 130 Critical Findings
description: Two critical data integrity bugs found and fixed — identity_overrides startup read and 212 missing photo_faces rows
type: project
---

Session 130 found and fixed two critical data integrity issues:

1. **identity_overrides startup read was NEVER removed** — Session 129 only removed
   the write path from `save_registry()`. `sync_from_supabase_on_startup()` was STILL
   reading from `identity_overrides` on every deploy, re-applying 2369 stale rows.
   **Why:** Incomplete fix in Session 129 — the startup sync code path was missed.
   **How to apply:** Structural invariant tests now scan ALL production code for
   `identity_overrides` table queries. Any reintroduction fails CI.

2. **212 faces missing from photo_faces table** — 82/125 CONFIRMED identities had
   faces that existed in embeddings.npy but not in Supabase photo_faces. Legacy photos
   (numeric filenames) were never migrated. The `_build_caches()` filename bridging
   masked this in rendering but direct registry queries failed silently.
   **Why:** Migration to Supabase was incomplete for pre-existing photos.
   **How to apply:** `scripts/data_reconciliation.py` should be run after every deploy.
   `scripts/backfill_photo_faces.py` can fix gaps if found.
