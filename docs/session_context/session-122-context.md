# Session 122 Context — TOOLS-003 Real-Time Compare + Performance + WORKSPACE Schema

**Predecessor:** [Session 121 Context](session-121-context.md)
**Assessment:** [Session 121 Assessment](../assessments/session-121-assessment.md)
**PRD:** [PRD-053 Face Compare Real-Time](../prds/053_face_compare_realtime.md)

## Problem Statement

Three high-impact deliverables ready for implementation:
1. **TOOLS-003**: Real-time face comparison via ML service — PRD written, all infrastructure exists
2. **Performance**: Speed-run and _build_caches bottlenecks cause multi-second delays
3. **WORKSPACE-001 Phase 1**: Schema migration for personal archives

Plus browser verification of Session 121 UX changes and upload testing reminder.

## TOOLS-003: Real-Time Face Compare

### Current State
- `/tools/compare` exists (compare_routes.py) — archive-to-archive comparison only
- ML service `/api/v1/detect-and-embed` deployed and returning 512-dim embeddings
- `find_similar_faces()` in `core/neighbors.py` accepts raw embeddings directly
- `compute_face_confidence()` provides calibrated confidence scoring
- **No format conversion needed** — ML service embeddings feed directly into comparison

### Implementation Plan
In `POST /api/compare/upload` (compare_routes.py):
1. Check if ML service is available via `MLServiceClient.is_available()`
2. If yes: save uploaded file to temp, call `detect_and_embed()`, get embeddings
3. For each face: call `find_similar_faces(embedding, face_data, registry, limit=10)`
4. Render results as HTMX fragment with per-face match cards
5. If ML service unavailable: return error message

### Key Files
- `app/compare_routes.py` — upload handler + results rendering
- `core/ml_client.py` — MLServiceClient (no changes needed)
- `core/neighbors.py` — find_similar_faces (FROZEN, no changes)
- `app/admin_routes.py` — _run_ml_client_async pattern to reuse

## Performance Fixes

### PERF-P0: Speed-run cache key misses (40-60% faster)
- `app/cluster_review_routes.py:1713` — `_get_speed_run_clusters()`
- Cache key doesn't include community from API routes (skip CommunityMiddleware)
- Fix: Pass community_slug explicitly, increase TTL from 30s to 120s
- Estimated: 30 min

### PERF-P0: _build_caches batch Supabase query (5-8x faster cold start)
- `app/main.py:4067` — `_build_caches()` makes per-photo Supabase calls
- Fix: Single batch query, iterate cached dict
- **Risk**: This function is critical — extensive testing needed
- Estimated: 45 min, but high risk — defer to dedicated performance session if complex

### Decision: Do speed-run cache fix (safe, high ROI). Investigate _build_caches but only fix if straightforward.

## WORKSPACE-001 Phase 1: Schema Only

### Schema Migration
```sql
ALTER TABLE communities ADD COLUMN owner_id UUID REFERENCES auth.users(id);
ALTER TABLE communities ADD COLUMN is_personal BOOLEAN DEFAULT false;
ALTER TABLE communities ADD COLUMN privacy TEXT DEFAULT 'public'
    CHECK (privacy IN ('private', 'unlisted', 'public'));
CREATE INDEX idx_communities_owner_id ON communities(owner_id);
CREATE UNIQUE INDEX idx_communities_personal_owner
    ON communities(owner_id) WHERE is_personal = true;
```

### New Function: create_personal_archive()
In `app/supabase_data.py`:
- Idempotent: check existing before insert
- Slug: `personal-{user_id[:8]}`
- Name: `{email_name}'s Archive`
- Privacy: private by default
- Invalidate community cache after creation

### NOT This Session
- Signup hook wiring (Phase 2)
- UI changes (Phase 3)
- These depend on schema being live in Supabase first

## Browser Verification Checklist (Session 121)
- UX-207: Approvals page filtered by community
- UX-208: Community badges always visible on suggestions
- UX-211: Face overlay minimum size on group photos
- UX-212: Source URL field on photo detail (need upload to test)

## Reminder
User will do upload testing tonight — remind at session end.

## Parallelization

| Track | Files | Parallelizable? |
|-------|-------|----------------|
| TOOLS-003 | compare_routes.py | YES — worktree A |
| Performance | cluster_review_routes.py, main.py | YES — worktree B |
| WORKSPACE-001 schema | supabase_data.py, scripts/sql/ | YES — worktree C |
| Browser verify | Chrome tools | Sequential after deploy |
| Security audit + harness | docs/ | Sequential last |
