# Session 96e-cont7/cont8 Assessment

## Shipped (cont7)
- [x] **Post-deploy Supabase resync**: 938 photos, 3023 identities synced
- [x] **Browser verification**: Halfon, Benatar, Discoveries verified
- [x] **PRD-038 comprehensive rewrite**: Hub + 4 sub-files (960 lines)
- [x] **BACKLOG breadcrumbs**: ML-110 through ML-116

## Shipped (cont8)
- [x] **Sort cache fix**: `_invalidate_all_caches()` replaces `_photo_registry_cache = None` in resync. Commit 7545545.
- [x] **Orphan face repair**: Resync now creates INBOX identities for faces in photo_index with no identity. Commit 10914ce.
- [x] **Person 2973 reverted**: Was incorrectly CONFIRMED, reverted to SKIPPED via /api/identity/skip
- [x] **Test identity reverted**: Accidental identity created during debugging, reverted to SKIPPED

## CRITICAL: Deploy Blocked by Railway Incident
- Railway experiencing "partially degraded performance" since 3:19 PM March 10
- Deploy e00bd690 stuck in INITIALIZING with DOCKERFILE builder
- **Current production is running OLD code** without the orphan fix or sort cache fix
- **AFTER deploy completes**: Must trigger `/api/sync/resync-supabase` (POST, no Content-Type header) to:
  1. Create INBOX identities for orphan faces → fixes Create Identity 404
  2. Backfill upload_dates (already done once, but cache fix ensures they're visible)
  3. Full cache invalidation → fixes sort order

## Data Integrity Issues Found (cont8)
- [HIGH] **Orphan faces**: Some faces in photo_index/embeddings have no identity record. Create Identity returns 404 for these faces. Root cause: ingest pipeline partial failure. Fix: resync endpoint now repairs these.
- [HIGH] **Person 2973 auto-confirmed**: Identity was CONFIRMED without user action. Root cause unclear — may be from startup Supabase sync or face grouping pipeline. Reverted manually.
- [HIGH] **Test identity created on production**: I accidentally called create-identity API on production during debugging. Reverted. LESSON: NEVER test against production APIs.
- [MEDIUM] **Sort cache**: `_photo_cache` not cleared by resync, only `_photo_registry_cache` was. Fixed.

## Red Flags
- [HIGH] Data integrity regressions across upload pipeline — orphan faces, auto-confirm, cache staleness
- [MEDIUM] Railway deploy incident blocking fixes from reaching production
- [LOW] Recalibration hooks silently failing in production
- [LOW] Flaky test `test_my_contributions_page_accessible`

## Next Session MUST Do First
1. **Verify deploy completed** — check `mcp__railway-mcp-server__list-deployments` for SUCCESS
2. **Trigger resync**: `fetch('/api/sync/resync-supabase', {method: 'POST'})` in browser
3. **Verify resync output**: `orphan_faces_repaired > 0`, `upload_date_backfilled >= 0`
4. **Verify Create Identity works**: Click a face, type name, click Create — should succeed
5. **Verify sort**: Photos page with "Upload Date (Newest)" shows recent uploads at top
6. **Verify Person 2973**: Should be SKIPPED, not CONFIRMED
7. **Audit auto-confirm paths**: Find how Person 2973 got CONFIRMED without user action
