# Session 130 Log — Data Integrity Deep Audit + Structural Prevention
Started: 2026-03-21 (Phase 1), Resumed: 2026-03-22 (Phases 2-6)
Mode: implementation
Prompt: docs/prompts/session-130-prompt.md

## Phase Checklist
- [x] Phase 1: Production Data Audit — audit script run, found 82 CONFIRMED identities with missing faces
- [x] Phase 2: Fix photo_faces ID mismatch (FB-016) — backfilled 212 missing rows, 0 issues remaining
- [x] Phase 3: Dead code removal + table cleanup — removed identity_overrides from startup sync
- [x] Phase 4: Production health check endpoint — added confirmed integrity check to /api/health/data
- [x] Phase 5: Structural prevention tests — 13 invariant tests + data_reconciliation.py
- [x] Phase 6: Documentation + assessment

## Baseline
- Tests: 3573 passed (36.66s)
- Version: v0.99.39

## Phase 1 Audit Results (2026-03-21)
- 6 CONFIRMED identities initially flagged (expanded to 82 on deeper audit)
- 0 duplicate face assignments
- 2 CONFIRMED still named "Unidentified Person"
- 67 orphan faces
- 355 merged chains (some orphaned)
- photo_faces ID mismatch confirmed (inbox vs SHA256)

## Phase 2 Results (2026-03-22)
**Root cause:** 212 faces in embeddings.npy had no entries in photo_faces table.
29 files were never migrated from JSON to Supabase photos table.
These were legacy photos (numeric filenames like 603575867.895093.jpg).

**Fix:** `scripts/backfill_photo_faces.py` — resolved inbox vs SHA256 ID
mapping through filename bridging. Used existing inbox photo_ids from photos
table instead of creating duplicate SHA256 entries.

**Result:** 0 CONFIRMED identities with missing faces (was 82).

Also added `PhotoRegistry.resolve_photo_id()` for cross-ID resolution,
and pre-existing test fix (blue→indigo from Session 126).

## Phase 3 Results (2026-03-22)
**CRITICAL FIX FOUND:** `sync_from_supabase_on_startup()` was STILL reading
from `identity_overrides` table on every deploy. Session 129 only removed the
WRITE path, not the startup READ. This meant every restart applied stale data.

**Fix:**
- Removed identity_overrides read from startup sync
- Stubbed `sync_identity_overrides()` and `load_identity_overrides_from_supabase()`
- Truncated identity_overrides table (2369 stale rows → 0)
- Added 2 structural invariant tests

## Phase 4 Results (2026-03-22)
Enhanced `/api/health/data` with confirmed identity face integrity check.
Reports `status=critical` when any CONFIRMED identity has missing faces.
3 new tests.

## Phase 5 Results (2026-03-22)
- 6 new structural invariant tests (13 total across TestNoOverrideLayers,
  TestNoJsonReadsInPostgresMode, TestPhotoFacesConsistency)
- `scripts/data_reconciliation.py` — cross-source consistency checker
- All 5 reconciliation checks PASS on production data

## Verification Gate
| Check | Result |
|-------|--------|
| All CONFIRMED identities have faces in photo_faces? | PASS (0 missing, was 82) |
| identity_overrides table empty? | PASS (truncated from 2369 rows) |
| No code reads identity_overrides? | PASS (structural test enforced) |
| Reconciliation script passes? | PASS (all 5 checks) |
| Tests pass? | PASS |
