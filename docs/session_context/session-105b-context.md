# Session 105b Context — Data Integrity Final Fix

**Predecessor:** Session 105 (sync push Supabase write)
**Priority:** P0 — platform data reliability is existential

## Problem Statement

Session 105 fixed the sync push endpoint but left 4 critical gaps:

### Gap 1: photo_faces table never written after migration — FIXED (105b)
- `shadow_write_photo_faces_batch()` wired into ALL 4 write paths

### Gap 2: save_registry() uses background thread — FIXED (105b)
- Both save functions now use synchronous strict=True for Supabase writes

### Gap 3: 1,511 stale Supabase identity rows — RESOLVED (105b continuation)
- Reconcile audit showed 0 stale identities (3433 == 3433)
- The 1,511 diff was a false alarm: health compared active (1922) vs total including merged (3433)
- Fixed health parity to use `include_merged=True`
- 1 stale photo pruned

### Gap 4: Upload pipeline uses print() error handling — FIXED (105b)
- Changed to `logging.error` for visibility

## What Was Actually Done (105b continuation)
1. Production reconciliation executed via Chrome browser — audit, prune
2. Health parity fix — `include_merged=True` for correct comparison
3. Startup parity check — background thread in startup_event
4. 8 structural prevention tests — read source code to verify dual-write patterns
5. AD-225 written
6. All harness docs updated (CHANGELOG, ROADMAP, SESSION_HISTORY, assessment)

## Architecture Decision: Write-Through with JSON Backup (AD-225)
- When DATA_SOURCE=postgres: Supabase is primary write, JSON is backup
- Writes are synchronous (not background thread)
- If Supabase fails: log ERROR + Sentry, write JSON, surface to admin
- Reconciliation endpoint for manual drift recovery
- Structural tests prevent regression

## Breadcrumbs
- Lesson 123: Additive-only shadow sync is not reconciliation
- Lesson 136: Fire-and-forget Supabase syncs create invisible data loss
- Lesson 144: DATA_SOURCE split-brain
- Lesson 145: photo_faces must be written alongside photos
- BACKLOG: DATA-014 (silent sync failures) — now DONE
- AD-225: Write-Through Architecture for Dual-Store Data Integrity
