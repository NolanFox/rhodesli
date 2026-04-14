# Session 148b — Overnight Implementation Sprint

**Mode:** Implementation (autonomous)
**Predecessor:** Session 148 (interactive Fader exploration + P0 fix)
**Context:** `docs/session_context/session-148b-context.md`

## Orientation

Read at session start:
- `tasks/lessons.md` + `tasks/todo.md`
- `docs/session_context/session-148b-context.md`
- `ROADMAP.md` current state

Set session: `echo "148b" > .claude/current_session.txt && echo "implementation" > .claude/session_mode.txt`
Baseline: `source venv/bin/activate && make test-fast`

---

## Phase 1: Session 147 Deferred Quick Wins (~30 min)

### 1a: Browser verify evidence panel
- Navigate to a person page with identity suggestions on production
- Take screenshots of the evidence panel UI (signal bars, accept/reject/needmore buttons)
- Verify the panel only shows for admin, only for PENDING suggestions
- Save screenshots to `docs/screenshots/session-148b/`

### 1b: Rejected list UX — restore buttons
- Session 147 built POST `/api/identity/{id}/restore` endpoint
- Add "Restore to Inbox" button on dismissed section identity cards
- It should appear on each card in the Dismissed section, similar to the existing action buttons
- Tests: verify button renders for admin, doesn't render for non-admin, POST returns 200

**Commit after Phase 1. /clear.**

---

## Phase 2: REFACTOR-001 Phase 4 — Photo Routes Extraction (~60 min)

Extract photo-related routes from `app/main.py` to `app/photo_routes.py`.

### Approach (follow Phases 1-3 pattern):
1. Identify all photo routes in main.py (GET/POST /photo/*, /photos/*, /api/photos/*)
2. Create `app/photo_routes.py` with the same pattern as existing extracted route files
3. Move routes one at a time, running tests after each move
4. Update imports in main.py
5. Structural test: verify no photo route handlers remain in main.py

### Parallelization: This is SEQUENTIAL — touches main.py.

**Target:** main.py drops below 8,000 lines.

**Commit after Phase 2. /clear.**

---

## Phase 3: Cross-Collection Search Admin Tool (TOOLS-007) (~45 min)

Build the admin tool that Session 148 needed but didn't have.

### Endpoint: GET /api/admin/search-person-in-collection
- Parameters: `person_id` (identity UUID), `collection_id` (community UUID), `limit` (default 20)
- Returns: ranked list of faces by embedding distance, with photo thumbnails and distances
- Uses the same centroid-distance approach as `scripts/sherry_search.py`

### UI: Admin-only panel on person page
- "Search in other collections" button → dropdown of collections → results panel
- Each result shows face crop, photo thumbnail, distance, link to photo page

### Tests:
- Endpoint returns ranked results for known person
- Endpoint requires admin auth
- Results are scoped to specified collection

### Parallelization: Can run in WORKTREE parallel with Phase 4 if Phase 2 is done.

**Commit after Phase 3. /clear.**

---

## Phase 4: Upload Pipeline Audit (UPLOAD-003) (~60 min)

End-to-end audit of upload → staging → R2 → Postgres → photo page pipeline.

### Known bugs (from BACKLOG):
1. 404 after approval — compare_mode detection broken
2. Anonymous attribution — auth gate removed but attribution lost
3. Missing thumbnails — R2 path fix needed

### Approach:
1. Read all upload code paths: `app/upload_routes.py`, `app/admin_routes.py` upload sections
2. Trace the full journey of a photo from upload form to visible on photo page
3. Fix each bug with tests
4. Add structural test: "approved photo must be reachable at /photo/{id}"

### Parallelization: Can run in WORKTREE parallel with Phase 3.

**Commit after Phase 4. /clear.**

---

## Phase 5: Session Close

1. Assessment: `docs/assessments/session-148b-assessment.md`
2. Update CHANGELOG (increment version)
3. Update ROADMAP + BACKLOG (close done items, add new)
4. Deploy: `git push origin main`, verify health 200
5. Browser verify: landing, people grid, person page, compare, estimate
6. `git log origin/main..HEAD` must be empty
7. Memory backup: `./scripts/backup-memory.sh`
8. Run /session-review skill

---

## Parallelization Plan

```
Phase 1 (sequential — browser + small fix)
  ↓
Phase 2 (sequential — touches main.py)
  ↓
Phase 3 ←→ Phase 4 (PARALLEL worktrees — independent files)
  ↓
Phase 5 (sequential — session close)
```

## Success Criteria
- Evidence panel browser-verified with screenshots
- Restore buttons on dismissed cards
- main.py < 8,000 lines
- Cross-collection search tool working
- Upload pipeline bugs fixed with tests
- All tests pass, deployed, browser verified
