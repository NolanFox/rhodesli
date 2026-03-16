# Session 108 Post-Mortem: 3 Sessions Without Deploy + Orphan Faces

**Date:** 2026-03-16
**Scope:** Sessions 106b, 107, 107b

## Failure 1: 25 Commits Never Pushed (Sessions 106b, 107, 107b)

**What happened:** Three consecutive sessions produced 25 commits to main but none were pushed to `origin/main`. Session assessments claimed deploys were triggered but `git log origin/main..HEAD` showed 25 unpushed commits.

**Root cause:** No mechanical enforcement of push verification. The stop-gate.sh hook checks for clean git and assessment files, but does NOT check if HEAD is ahead of remote.

**Impact:** All code/test improvements from Sessions 106b-107b were unavailable in production for ~1 week.

**Fix:** Added Lesson 148. Phase 3b adds push-ahead warning to stop-gate.sh.

## Failure 2: 13 Orphan Faces (Including 9 James Fields)

**What happened:** James Fields photos were uploaded via the web UI. Face detection ran and extracted 9 faces into `photo_faces` (Supabase). But zero corresponding identities were created in the `identities` table.

**Root cause:** The `_background_ingest()` pipeline in `app/upload_routes.py`:
1. Calls `process_directory()` which writes identities to JSON on the Railway volume ✓
2. Then syncs ALL identities from JSON to Supabase (lines 1034-1065)
3. But the Supabase sync writes ALL 3400+ identities as a batch — if this partially fails or the identity creation in `process_directory()` fails silently, the new identities never reach Supabase
4. There was NO post-sync validation to catch mismatches

**Additional finding:** 4 other orphan faces (not James Fields) were also unrepaired — indicating this is a systemic issue, not a one-time failure.

**Impact:** 13 faces invisible to clustering, search, and UI identity assignment. James Fields "find this person" workflow completely blocked.

**Fix:** Triggered `/api/sync/resync-supabase` which repaired all 13 orphans. Phase 3a adds startup orphan detection. Phase 3d adds data health endpoint.

## Failure 3: Local-Production Data Divergence (7th Occurrence)

**What happened:** James Fields photos exist on Railway/Supabase but local `embeddings.npy`, `identities.json`, and `photo_index.json` have zero entries for them. ML clustering cannot run locally.

**Root cause:** No sync-back mechanism for embeddings. `sync_from_production.py` downloads identities and photo_index but NOT embeddings.npy (which lives on the Railway volume and contains face embedding vectors).

**Impact:** Cannot run face clustering locally against James Fields photos. The intended "find this person" workflow is blocked.

**Fix:** Phase 3c adds `/api/sync/embeddings` endpoint.

## Timeline of Data Sync Issues

| # | Session | Lesson | Issue |
|---|---------|--------|-------|
| 1 | 24 | 56 | Blind push overwrites admin actions |
| 2 | 26 | 69 | Production-origin data in deploy sync |
| 3 | 31+ | 78 | Production-local divergence recurring |
| 4 | 39 | 85 | Deploy data safety gate (5th time) |
| 5 | 104b | 141 | git-add production-origin data |
| 6 | 104b | 142 | JSONB string-encoded arrays |
| 7 | 108 | 146-147 | Orphan faces + no embeddings sync |

## Systemic Root Cause

The system was designed for a **local-first workflow** (ingest locally, push to production). Usage has shifted to **production-first** (upload via web UI). The tooling never adapted:
- No embeddings sync-back
- No post-upload validation
- No automated data health checks
- Local data assumed fresh
