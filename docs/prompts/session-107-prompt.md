# Session 107 — Data Fix + Bug Fixes (User Triage)

**Context:** Interactive user triage session
**Priority:** P0 data fix + P1 bug fixes
**Predecessor:** Session 106b (triage fix sprint)

## Issues

### P0: James Henry Fields photos in wrong community
- Two photos uploaded to Fox Family ended up in Rhodes community
- Root cause: upload done without `/c/fox-family/` prefix, CommunityMiddleware defaulted to Rhodes
- Fix: Update `photo_communities` table in Supabase
- Status: FIXED — moved to Fox Family, metadata (source=Instagram, collection=Fox Family Internet Research) preserved
- 9 faces detected, no identities yet, no embeddings locally

### P1: Approvals sidebar count = 0
- Sidebar shows "Approvals 0" but /admin/approvals shows 12 pending
- Root cause: `_compute_sidebar_counts()` iterates dict keys instead of `.values()`
- Fix: Change to `.values()` with `isinstance(ann, dict)` guard
- Status: FIXED

### P1: Anonymous pending uploads still showing
- Two anonymous Compare Upload entries from 2026-03-13 (job IDs 8add8b91, b8de4b5f)
- Staging files auto-cleaned but JSON entries persist on Railway volume
- Fix: Admin can reject manually, or add auto-expiry on startup

### P2: Approvals UX issues (BACKLOG)
- No batch select (port pattern from pending uploads)
- No submission timestamps shown
- No history preservation on person page
- Auto-confirm on approve?
- Email batching for approvals

## Acceptance
- James Henry Fields photos appear in Fox Family, not Rhodes
- Sidebar shows correct approvals count
- Tests pass
