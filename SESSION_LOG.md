# Session 66b Log
## Mission: Fix Upload Silent Data Loss (CRITICAL)
## Started: 2026-02-25
## Context: b-path from Session 66 — upload still broken after 4 "fix" sessions
## Rule: /clear between phases, NEVER /compact
## Predecessor: Session 66 (v0.72.0 — parallel worktrees, enrichment, GEDCOM UI, portfolio)

### Phase 0: Diagnose the Upload Bug
- [x] Read all mandatory files (CLAUDE.md, session-66 context/assessment/log, AD head)
- [x] Set .claude/current_session.txt to "66b"
- [x] Traced full upload code path: POST /upload → _background_ingest → process_directory → process_single_image
- [x] Checked production state via health endpoint + Chrome sidebar
- [x] Checked R2 for uploaded photo file

#### 0A: Production State Check
- Health endpoint: 666 identities, **273 photos**, processing_enabled=true, ml_pipeline=ready
- Sidebar: 407 New Matches, 202 Help Identify, 55 People, **271 Photos**
- **KEY DISCREPANCY**: Health shows 273 photos (reads disk), sidebar shows 271 (stale cache)
- This 2-photo gap PROVES data IS being written to disk but NOT reflected in UI

#### 0B: R2 Upload Check
- `morris_mazal_ancestry_murry_army.jpeg` → **404 on R2**
- Photo file was NOT uploaded to R2 despite "success" status
- Data records (identities.json, photo_index.json) WERE written to disk

#### 0C: Root Cause Analysis

**BUG 1: In-memory cache staleness (CRITICAL)**
- Background upload thread writes to identities.json, photo_index.json, embeddings.npy on disk
- Web app has global caches (`_photo_cache`, `_face_data_cache`, `_face_to_photo_cache`, `_photo_registry_cache`) built once, never invalidated after upload
- Sidebar "Photos" count uses `len(_photo_cache)` → stale 271 instead of 273
- Photo grid uses `_photo_cache` → new photos invisible
- Code location: app/main.py caches at lines 2001, 2002, 2348, 2349 — never invalidated by upload
- The /api/sync/push endpoint HAS proper cache invalidation (line 28457-28475), but the upload status endpoint does NOT

**BUG 2: R2 upload race condition (CRITICAL)**
- Background thread's `finally` block (line 22772-22779) deletes staging directory after processing
- Status endpoint R2 upload (line 23015-23048) runs on first successful poll
- By then, staging directory is already deleted → `staging_dir.exists()` is False → no R2 upload
- Photo URL on R2 → 404 → broken images even if caches were fixed
- Code location: app/main.py lines 22772-22779 (delete) vs 23015-23048 (R2 upload)

**NOT A BUG: Help Identify count (202) is correct**
- INBOX identities go to "New Matches" (to_review section), not "Help Identify" (skipped section)
- The 3 new INBOX identities are likely in the 407 "New Matches" count
- Nolan expected Help Identify to increase, but that section only shows SKIPPED identities

**Why previous fixes (65a, 65c, 65d, 66) didn't catch this:**
- 65a: Fixed subprocess death detection + timeout → never addressed caches
- 65c: Replaced subprocess with background thread → thread works, but cache invalidation missing
- 65d: Fixed disk space → disk is fine, data writes succeed
- 66: "Chrome can't handle file dialogs" → never tested with real upload
- ALL sessions verified processing status == "success" but never checked if data appears in UI

#### Phase 0 VERDICT: ROOT CAUSE FOUND — Two bugs in app/main.py

### Phase 1: Fix the Upload Bug (IN PROGRESS)
