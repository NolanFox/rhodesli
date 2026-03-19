# Session 122 — TOOLS-003 Real-Time Compare + Performance + WORKSPACE Schema

@docs/session_context/session-122-context.md
@docs/prds/053_face_compare_realtime.md
@tasks/lessons.md

## Goal

Ship real-time face comparison (TOOLS-003), fix the top performance bottleneck, lay schema foundation for personal archives (WORKSPACE-001), and browser-verify Session 121 UX changes.

## CRITICAL CONSTRAINTS

1. **Browser automation is READ-ONLY on production** (Lesson 149).
2. **DO NOT touch**: `core/neighbors.py` (frozen), `core/pfe.py`, `app/perf_cache.py`.
3. **Every change gets tests** — happy path + failure + regression.
4. **/clear between phases** — commit first, then /clear immediately.
5. **Parallelization**: 3 worktrees possible. See context file.
6. **Security audit**: After all code phases, audit changed files.
7. **Gap check**: Re-read this prompt at end. Auto-fix any gaps.
8. **REMINDER**: Tell user to do upload testing tonight (AD-229 criteria).

## Pre-Requisites

```bash
echo "122" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline
```

---

## Phase 0: Orient (3 min)

Create session log. Verify baseline tests pass. Record count.

**Commit:** `docs: session 122 phase 0 — orient`
**/clear**

---

## Phase 1: TOOLS-003 — Real-Time Face Compare (30 min)

**Worktree A — only touches compare_routes.py**

### 1A: Add real-time compare endpoint

In `app/compare_routes.py`, modify `POST /api/compare/upload` (or add new endpoint):

When ML service is available:
1. Save uploaded file to temp path
2. Call `_run_ml_client_async(lambda c: c.detect_and_embed(tmp_path))` — reuse pattern from admin_routes.py
3. For each face in result: call `find_similar_faces(embedding, face_data, registry, limit=10)`
4. Render results as HTMX fragment — one section per face with top 10 matches
5. Clean up temp file

When ML service unavailable:
- Return error div: "Real-time comparison requires the ML service. Please try again later."

### 1B: Results rendering

Reuse existing compare result card patterns. Each face section shows:
- Face thumbnail (from uploaded image bbox crop — or just bbox coordinates)
- Top 10 matches with confidence %, distance, identity name, crop thumbnail
- "Compare" and "View Person" links

### 1C: Tests

- Test real-time compare with mock ML service (returns synthetic embeddings)
- Test graceful error when ML service unavailable
- Test per-face result rendering with multiple faces
- Test admin-only gate
- Test temp file cleanup

**Commit:** `feat(tools): session 122 phase 1 — TOOLS-003 real-time face compare`
**/clear**

---

## Phase 2: Performance — Speed-Run Cache Fix (15 min)

**Worktree B — touches cluster_review_routes.py**

### 2A: Fix cache key for API routes

In `_get_speed_run_clusters()` at cluster_review_routes.py ~line 1713:
- Ensure community_slug is passed explicitly to cache key
- API routes (`/api/...`) skip CommunityMiddleware — need to extract community from request or parameter
- Increase TTL from 30s to 120s (speed-run is user-driven, data changes infrequently)

### 2B: Investigate _build_caches

Read `app/main.py:4067-4266` — `_build_caches()`. Check if it makes per-photo Supabase calls.
If yes and fix is straightforward (batch query): implement.
If complex: document in BACKLOG with specific findings and defer.

### 2C: Tests

- Test cache key includes community parameter
- Test TTL is 120s (not 30s)

**Commit:** `perf: session 122 phase 2 — speed-run cache fix`
**/clear**

---

## Phase 3: WORKSPACE-001 Schema + Function (20 min)

**Worktree C — touches supabase_data.py + scripts/sql/**

### 3A: Create SQL migration

Create `scripts/sql/session_122_workspace_schema.sql`:
```sql
ALTER TABLE communities ADD COLUMN IF NOT EXISTS owner_id UUID;
ALTER TABLE communities ADD COLUMN IF NOT EXISTS is_personal BOOLEAN DEFAULT false;
ALTER TABLE communities ADD COLUMN IF NOT EXISTS privacy TEXT DEFAULT 'public';
CREATE INDEX IF NOT EXISTS idx_communities_owner_id ON communities(owner_id);
```
Note: Don't add REFERENCES constraint (auth.users may not be accessible). Don't add community_members table yet (WORKSPACE-006).

### 3B: Add create_personal_archive function

In `app/supabase_data.py`:
```python
def create_personal_archive(user_id: str, email: str) -> dict | None:
    """Create a personal community archive for a new user. Idempotent."""
```
- Check existing by owner_id + is_personal
- If exists: return it
- If not: insert with slug=personal-{user_id[:8]}, privacy=private
- Invalidate community cache
- Return created dict

### 3C: Tests

- Test create_personal_archive creates community with correct fields
- Test idempotency (second call returns existing)
- Test SQL migration file exists and has correct statements

**Commit:** `feat(workspace): session 122 phase 3 — WORKSPACE-001 schema + create function`
**/clear**

---

## Phase 4: Browser Verify Session 121 (10 min)

**Sequential on main — after deploy**

Screenshots of:
1. Approvals page — community badge visible (UX-207)
2. Person page — community badge on ALL suggestion cards (UX-208)
3. Photo page — face overlays with minimum size (UX-211)
4. Any photo detail — source URL field (UX-212, if a photo has one)

Save to `docs/screenshots/session-122/`

**Commit:** docs only if screenshots saved
**/clear**

---

## Phase 5: Security Audit + Harness Outputs (15 min)

### 5A: Security audit of changed files
- compare_routes.py: auth guards, temp file cleanup, input validation
- cluster_review_routes.py: cache poisoning risk?
- supabase_data.py: SQL injection via slug generation?

### 5B: Harness outputs
1. Assessment: `docs/assessments/session-122-assessment.md`
2. CHANGELOG: v0.99.32
3. ROADMAP: update TOOLS-003, WORKSPACE-001 statuses
4. SESSION_HISTORY: Session 122 entry
5. BACKLOG: update statuses

### 5C: Gap check
Re-read this prompt. Verify every phase. Auto-fix gaps.

### 5D: Remind user
"Remember to do upload testing tonight for AD-229 criteria (#2: 3 successful uploads, #3: cosine similarity via compare script)."

**Commit:** `docs: session 122 harness outputs`
**Push to origin main**

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| TOOLS-003 works? | Test | Upload → embeddings → matches returned |
| Speed-run faster? | Test | Cache key fixed, TTL 120s |
| WORKSPACE schema? | SQL file exists | Migration ready |
| create_personal_archive? | Test | Idempotent creation |
| Browser verified? | Screenshots | 4 UX items checked |
| Security audit clean? | Audit file | No P0/P1 |
| All tests pass? | `make test-fast` | PASS |
| Assessment exists? | File check | Exists |
| `git log origin/main..HEAD` empty? | git log | Empty |

## Parallelization

**3 parallel worktrees:**
- **Worktree A:** Phase 1 (TOOLS-003) — compare_routes.py only
- **Worktree B:** Phase 2 (Performance) — cluster_review_routes.py, main.py investigation
- **Worktree C:** Phase 3 (WORKSPACE) — supabase_data.py, scripts/sql/
- **Sequential:** Phase 0 → merge all → Phase 4 (browser) → Phase 5 (harness)
