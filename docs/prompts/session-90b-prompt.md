# Session 90b: Fix Sorting + Refactor main.py + Supabase + Performance

**Context**: `docs/session_context/session-90b-context.md`
**Predecessor**: Session 90 (v0.92.2, 42caecd)

## Problem Statement

Session 90 shipped upload date sorting but it's broken on production — switching sort order doesn't change photo order. The photo page is missing upload metadata and ML enrichment. main.py at 34K lines blocks parallel development and causes merge failures. Supabase migration hasn't started. The site feels slow.

## Session Protocol
- Set `.claude/current_session.txt` to `90b`
- Read `tasks/lessons.md` and `tasks/todo.md` at start
- Commit after every act, `/clear` between acts
- Use Claude Chrome for ALL frontend verification — no exceptions (Lesson 97)
- Run `/session-review` at session end
- Browser verify with Claude Chrome (admin is logged in)
- Screenshots to `docs/screenshots/session-90b/`

---

## Parallelization Plan

**Phase 1** (Act 0-1): Sequential on main — orient + fix sorting bug + browser verify
**Phase 2** (Acts 2-5): Parallel worktree subagents:
- Track A: main.py refactor (worktree: `session-90b/refactor`)
- Track B: Supabase shadow writes (worktree: `session-90b/supabase`)
- Track C: Performance optimization (worktree: `session-90b/perf`)
- Track D: Testing + hooks cleanup (worktree: `session-90b/testing`)
- Track E: Review sections UX fix + Notification PRD (worktree: `session-90b/review-ux`)
**Phase 3** (Act 6): Merge all tracks, browser verify, assessment

**File conflict analysis**:
- Track A touches `app/main.py` exclusively (splitting it) — merges FIRST
- Track B touches `app/supabase_data.py` + new files — independent
- Track C may touch templates in main.py — merges AFTER Track A
- Track D touches `tests/` + `.claude/` — independent
- Track E touches discoveries/review routes in main.py — merges AFTER Track A
- **Merge order**: A first, then B+D (independent), then C+E (depend on A's file structure)

---

## Act 0: Orient (5 min)

1. Read this prompt, context file, `tasks/lessons.md`
2. Read `docs/assessments/session-90-assessment.md` and `docs/session_logs/session-90-log.md`
3. Verify current state: `git log --oneline -5`, `git status`, test suite passes
4. Set `.claude/current_session.txt` to `90b`
5. Create `docs/session_logs/session-90b-log.md` with phase checklist

---

## Act 1: Fix Upload Date Sorting + Photo Page Metadata (30 min)

**This is the P0. Fix it, browser verify it, commit it.**

### 1a. Debug and Fix Sorting Bug

**Symptoms**: On production, `sort_by=upload_newest` and `sort_by=upload_oldest` show the same photo order.

**Investigation steps**:
1. Check `_build_caches()` at `app/main.py:3002` — does `upload_date` make it into `_photo_cache`?
2. Trace: `photo_registry.get_metadata(photo_id)` at line 3072 — for SHA256 photo IDs that exist in `_photo_cache`, does the matching photo_index.json entry also use SHA256 IDs? Or do some use `inbox_*` IDs?
3. Add a temporary debug log or test: After `_build_caches()`, count how many `_photo_cache` entries have `upload_date` set.
4. Check `render_photos_section()` at line 6174: `photo_data.get("upload_date", "")` — is `photo_data` from `_photo_cache`? If `upload_date` isn't in `_photo_cache`, it'll always be `""`.
5. Check if `_sort_photos()` receives photos with empty `upload_date` — if all are empty, `NO_DATE` logic makes them unsorted.

**Most likely root cause**: `_build_caches()` builds `_photo_cache` from `load_embeddings_for_photos()` which uses SHA256 IDs. Then `get_metadata(photo_id)` on line 3072 looks up by SHA256 ID in `photo_registry._photos`. But `photo_registry._photos` keys community photos by `inbox_*` IDs. So `get_metadata()` returns `{}` for those — and `upload_date` never gets merged into `_photo_cache`. Even for original photos where SHA256 IDs match, `upload_date` needs to be in `photo_index.json` AND returned by `get_metadata()`.

**Fix approach**: In `_build_caches()`, after the main loop, add a filename-based fallback for `upload_date` (same pattern as `filename_to_source` at line 3022-3040). Build a `filename_to_metadata` dict, and for each `_photo_cache` entry that's missing `upload_date`, look it up by filename.

**Tests**:
- Test that `_sort_photos()` with `upload_newest` puts newer dates first
- Test that photos with mixed dates sort correctly
- Test that the `render_photos_section` output has different first photo for newest vs oldest

### 1b. Display Upload Date on Photo Pages

Currently no photo page shows upload date. Fix:
1. Find the photo detail route handler (search for `@rt("/photo/{photo_id}")` in `app/main.py`)
2. After the photo metadata section, add upload date display: "Added to archive: March 5, 2026"
3. Use the existing `_format_display_date()` helper (already used at line 735)

### 1c. Browser Verify with Claude Chrome

**MANDATORY** — this is the lesson from Session 90. Do not skip.

1. Open `https://rhodesli.nolanandrewfox.com/?section=photos&sort_by=upload_newest`
2. Screenshot — the 24 March 5 photos should be at the top
3. Switch to `sort_by=upload_oldest` — the 155 Feb 10 photos should be first
4. Screenshot showing different order
5. Open a photo page — verify upload date is displayed
6. Save screenshots to `docs/screenshots/session-90b/`

Commit: `fix(photos): upload date sorting + display on photo pages`

---

## Act 2: Parallel Tracks — Launch Subagents (5 min)

After Act 1 is committed and verified, launch 4 parallel worktree subagents.

**CRITICAL**: Do NOT start these until Act 1 is merged to main, since all worktrees fork from main.

### Track A: main.py Refactor

**Worktree**: `session-90b/refactor`
**Goal**: Split `app/main.py` (34K lines) into logical route modules.

**Extraction plan** (from existing patterns in `compare_routes.py` and `estimate_routes.py`):

| New File | Routes | Approx Lines |
|----------|--------|-------------|
| `app/upload_routes.py` | `/upload/*`, `/api/upload/*`, staging, processing | ~2,000 |
| `app/admin_routes.py` | `/admin/*`, `/api/admin/*`, pending, proposals | ~3,000 |
| `app/person_routes.py` | `/person/*`, `/api/person/*`, identity CRUD | ~3,000 |
| `app/photo_routes.py` | `/photo/*`, `/api/photo/*`, gallery, reanalyze | ~2,000 |
| `app/browse_routes.py` | Photos/People/Collections sections, landing page | ~3,000 |
| `app/shared.py` | Shared helpers, caches, UI components | ~3,000 |

**Rules**:
- Each extracted file should be self-contained with its own imports
- Shared state (`_photo_cache`, `_face_to_photo_cache`, registry, etc.) stays in `app/shared.py` or `app/main.py` and is imported
- Use the same pattern as `compare_routes.py`: define routes in the file, register them in main.py via `include_router` or similar
- Run `make test-fast` after each extraction — tests must pass
- Don't change behavior, only move code

**Acceptance**: main.py < 15,000 lines. Each extracted file < 4,000 lines. All tests pass.

### Track B: Supabase Shadow Writes

**Worktree**: `session-90b/supabase`
**Goal**: Start writing core data to Supabase alongside JSON files.

1. **Create Supabase tables** (SQL scripts in `scripts/sql/`):
   - `photos` table: photo_id, path, source, collection, source_url, upload_date, width, height, face_count, uploaded_by, created_at, updated_at
   - `identities` table: identity_id, name, state, display_name, anchor_ids (JSONB), candidate_ids (JSONB), negative_ids (JSONB), version_id, created_at, updated_at, merged_into
   - `photo_faces` table: face_id, photo_id, bbox (JSONB), det_score, quality
   - `date_labels` table: photo_id, estimated_decade, best_year_estimate, confidence, model_used, labeled_by, raw_response (JSONB)
   - `photo_locations` table: photo_id, lat, lng, location_name, location_estimate, confidence, geocoded_from

2. **Shadow write functions** in `app/supabase_data.py`:
   - `shadow_write_photo(photo_data)` — called after any photo_index.json write
   - `shadow_write_identity(identity_data)` — called after any identities.json write
   - Fire-and-forget (don't block the main write path)
   - Log errors but don't fail the request

3. **Backfill script**: `scripts/backfill_supabase.py` — one-time load of all existing JSON data into Supabase tables.

4. **Tests**: Mock Supabase calls, verify shadow writes are called on key operations.

**Acceptance**: Tables created. Shadow write functions exist. Backfill script runs without error.

### Track C: Performance Optimization

**Worktree**: `session-90b/perf`
**Goal**: Measurable page load improvement.

**Investigation & fixes**:
1. **Pagination**: The photos page renders all 294 photos at once. Add server-side pagination or HTMX infinite scroll (load 40 at a time).
2. **Startup optimization**: Profile `_build_caches()` — does it run synchronously on first request? Consider lazy loading or background thread.
3. **Image optimization**: Are images served with proper `Cache-Control` headers from R2? Add `?v=hash` cache-busting to allow long cache TTLs.
4. **CSS/JS bundle**: Check total transfer size. Consider inlining critical CSS, deferring non-critical JS.
5. **Supabase connection**: Is the Supabase client initialized on startup or lazily? Connection pooling?

**Measure**: Use Claude Chrome to capture network waterfall (or `read_network_requests`). Before/after comparison.

**Acceptance**: Photos page initial load noticeably faster. Document what changed and by how much.

### Track D: Testing + Hooks Cleanup

**Worktree**: `session-90b/testing`
**Goal**: Fix hooks, reduce test count, fix flaky tests.

**Hooks**:
1. **Fix Stop hook**: `settings.json` checks for `docs/sessions/SESSION_0${S}.md` but actual path is `docs/session_logs/session-${S}-log.md`. Fix the path.
2. **Clean up orphaned hook scripts**: `session-stop-gate.py`, `session-stop-gate.sh` in `.claude/hooks/` are NOT referenced in `settings.json`. Either wire them in or delete them.
3. **Verify all hooks work**: Run a test commit cycle and confirm no errors.

**Testing**:
1. **Fix 21 flaky xdist tests**: Identify shared state issues (global caches, file locks, etc.). Add proper test isolation.
2. **Continue pruning**: Target another 200+ tests. Focus on:
   - Tests checking specific CSS classes or HTML strings (brittle)
   - Duplicate coverage (same route tested in multiple files)
   - Tests for removed/changed features
3. **Runtime optimization**: Profile test suite. Identify slowest test files. Consider:
   - Shared fixtures that reduce setup/teardown
   - `pytest-randomly` to surface order-dependent tests
   - Mock heavy imports (InsightFace, etc.) at conftest level

**Acceptance**: Hooks produce no errors. Flaky tests fixed. Test count < 3400. Runtime < 4 min.

### Track E: Review Sections UX Fix + Contributor Notification PRD

**Worktree**: `session-90b/review-ux`
**Merges AFTER Track A** (both touch main.py).

**Background (Claude Benatar feedback)**: Community contributor asked "if someone uploads a picture, how does he or she know if there's a match?" Nolan's vision: Facebook-style notifications — email + in-app when anything changes about uploaded photos or people in them.

**Prior decisions**: DD-003 (Discovery Notification UX, Session 69), AD-179 (Two-Tier Auto-Clustering, Session 76a), AD-183 (Tier 2 threshold 1.30, Session 79), DD-006 (Unified Face Cards, Session 84).

**Three Review sections must be clearly differentiated**:
- **New Matches** (to_review): Raw ML output — INBOX + PROPOSED faces. Admin triage. ~499 items.
- **Discoveries**: High-confidence Tier 2 matches to confirmed identities. Admin confirms. ~194 items.
- **Help Identify**: SKIPPED faces needing community help. Everyone can see. ~202 items.

**Fixes (this session)**:
1. **Confidence filter**: Verify HTMX buttons work (`/api/discoveries?min_confidence=70`). Fix if broken.
2. **Photo dropdown**: Empty on production. Debug `hx_get="/api/discoveries/photo-options"` at main.py:25866.
3. **Hide raw ML metrics**: Cards show "Dist: 0.80" — replace with calibrated confidence labels only (violates UX rule).
4. **Face card consistency**: Update discovery cards to match unified `identity_card` (DD-006).
5. **Uploader context**: Add ability to filter discoveries by "from your photos" if `uploaded_by` exists.

**PRD to write**: `docs/prds/028_contributor_notifications.md` — notification system for contributors (email on match, in-app activity feed, first+second order notifications). This is planning for future sessions, NOT implementation this session.

**Acceptance**: Filters work. Raw distances hidden. PRD-028 written. Cards consistent with DD-006.

---

## Act 3: Photo Enrichment — Benatar + Leon's Restaurant (20 min)

**While subagents run**, fix ML enrichment on two photos that are visibly broken.

### 3a. Benatar Photo (inbox_0c57277a_0_unknown / a75e6b54b0eb6c50)

1. **Verify photo state**: Check `data/photo_index.json` for `inbox_0c57277a_0_unknown` — confirm it has source "Claude Benatar upload"
2. **Run Gemini analysis**: Use the admin "Re-analyze with Gemini" button (added in Session 89) on production, OR use `scripts/reprocess_with_gedcom.py --photo-id inbox_0c57277a_0_unknown`
3. **Expected outputs**: Date estimate, location estimate, face analysis
4. **Verify on photo page**: Date label, location on map, face analysis section should all populate
5. **DO NOT delete a75e6b54b0eb6c50** — it exists on production and user shared the link

### 3b. Leon's Restaurant Photo (3192877a90a174e9) — MUST FIX

**This photo has been broken since Session 89. Nolan has flagged it twice.**

Photo shows Victoria and Victor Capeluto standing in front of "LEON'S RESTAURANT" in Tampa, FL. It's from the "Nace Capeluto Tampa Collection."

**Current state (all WRONG)**:
- **Location estimate**: Says "Miami, Florida, United States" (WRONG — should be Tampa, FL)
- **Geographic Analysis**: Says "Likely San Francisco, CA or New York, NY" (WRONG)
- **Location pin**: Points at Miami on map (WRONG)
- **Face Analysis**: Says "No face descriptions available yet" — face alignment was never run
- **Gemini analysis WAS run** (Photo Detective shows evidence cards with Gemini 3.1-pro) but it got the location wrong
- **GEDCOM context IS partially working** — the evidence cards mention "Victor Capelluto's brother, Leon Capeluto" and "Victor's timeline places him in San Francisco in 1938 and 1940"

**What's needed**:
1. **Run face alignment** ("Detect Faces" button or `face_alignment.py`) to populate face descriptions
2. **Re-run Gemini with corrected GEDCOM context** — the restaurant sign literally says "LEON'S" and the collection is Tampa. The GEDCOM should link Leon Capeluto to Tampa, not SF.
3. **Fix location**: Update `data/photo_locations.json` entry to Tampa, FL (lat: ~27.9506, lng: ~-82.4572)
4. **Verify**: Photo page shows Tampa on map, face analysis populated, date estimate reasonable

**Key investigation**: Why did Gemini say San Francisco when the GEDCOM context mentions Leon had a restaurant? Check if the GEDCOM data for Leon Capeluto has Tampa residence events. If not, that's the root cause — the GEDCOM data may be incomplete or the wrong Leon is being referenced.

Commit: `fix(data): enrichment for Benatar + Leon's Restaurant photos`

---

## Act 4: Merge Tracks + Resolve Conflicts (20 min)

1. Check all subagent branches for completion
2. **Merge order**: Track A (refactor) FIRST, then Track D (testing), then Track B (supabase), then Track C (perf)
3. Use `./scripts/merge.sh session-90b/refactor session-90b/testing session-90b/supabase session-90b/perf`
4. Run `make test-fast` after each merge
5. Resolve conflicts (Track C may conflict with Track A if both touched main.py templates)

Commit: merge commits per track

---

## Act 5: Browser Verification + Production Smoke (15 min)

**ALL of these must be verified with Claude Chrome. No exceptions.**

1. **Sorting**: `/photos` page — upload_newest shows March photos first, upload_oldest shows Feb photos first
2. **Photo page**: Any photo shows upload date
3. **Benatar photo**: `a75e6b54b0eb6c50` still loads correctly with ML enrichment
4. **Leon's Restaurant**: `3192877a90a174e9` — map shows Tampa FL, face analysis populated
5. **Upload page**: Still works (regression check from Session 90 merge issues)
5. **Performance**: Photos page feels faster (subjective check + network timing)
6. **General smoke**: Landing page, People page, Compare page all load
7. Save screenshots to `docs/screenshots/session-90b/`

---

## Act 6: Assessment + Docs (10 min)

Standard mandatory outputs:

1. Write `docs/assessments/session-90b-assessment.md`
2. Update `docs/session_logs/session-90b-log.md`
3. Update `CHANGELOG.md` — new version entry
4. Update `ROADMAP.md`:
   - Move completed items to "Recently Completed"
   - Update Supabase migration status
   - Update main.py refactor status
5. Update `docs/BACKLOG.md` — FB-40-22 (upload attribution) status
6. Update `docs/roadmap/SESSION_HISTORY.md` — session 90b entry
7. Update `docs/ml/ALGORITHMIC_DECISIONS.md` if any ML decisions made
8. Verify all breadcrumbs:
   - Context file references predecessor + prompt
   - Assessment references context file + prompt
   - BACKLOG items updated with session 90b reference
   - New AD entries (if any) reference related ADs

---

## Acceptance Criteria

- [ ] Upload date sorting works on production (browser verified with screenshots)
- [ ] Upload date displayed on photo pages
- [ ] Benatar photo has ML enrichment (date + location + face analysis)
- [ ] a75e6b54b0eb6c50 still works on production (DO NOT DELETE)
- [ ] Leon's Restaurant photo (3192877a90a174e9) shows Tampa, FL (not Miami/SF)
- [ ] Leon's Restaurant photo has face analysis populated (not "No face descriptions")
- [ ] main.py < 15,000 lines (route extraction complete)
- [ ] Supabase shadow write tables created + backfill script exists
- [ ] Performance: photos page measurably faster
- [ ] Hooks produce no errors, stop hook path fixed
- [ ] Test count < 3400, flaky tests fixed
- [ ] Discoveries: confidence filter + photo dropdown work, raw distances hidden
- [ ] PRD-028 (contributor notifications) written
- [ ] All tests pass (`make test-fast`)
- [ ] Browser verified via Claude Chrome with screenshots
- [ ] Assessment + session log + CHANGELOG + ROADMAP + BACKLOG updated

## Key Skills to Use

- `/simplify` — after implementation acts
- `/session-review` — at session end (mandatory)
- Claude Chrome — for ALL frontend verification
- Worktree subagents — for parallel tracks

## Non-Goals

- Full Supabase migration (shadow writes only, not replacing JSON as source of truth)
- New features or UX redesigns
- Running ML on all 294 photos (just Benatar + Leon's Restaurant)
- Compare/Estimate page changes

## Architecture Notes (from research)

**Two photo pages exist** — be aware when fixing upload date display:
- **Modal viewer** (`photo_view_content` at line 11729) — used from browse/compare. MISSING upload provenance.
- **Public page** (`public_photo_page` at line 20199) — standalone shareable page. Already HAS upload provenance via `_build_upload_provenance_line()` at line 733.
- **Fix**: Add `_build_upload_provenance_line()` call to the modal viewer too.

**Performance top 3** (from research):
1. O(N) identity lookup per photo card render (`get_identity_for_face` at line 15754) — 600-1500 lookups per page. Fix: pre-build face_id→state lookup dict.
2. Synchronous JSON file loads (date_labels 1.1MB, photo_index 246KB) block first request after deploy.
3. Tailwind JIT CDN compilation adds 300-800ms per page. Consider static CSS build.

## Tradeoff Guidance

**main.py refactor vs feature work**: Do the refactor. Every future session pays the merge-conflict tax. The ROI is immediate.

**Shadow writes vs full migration**: Shadow writes only. Get the tables and write path working. Full cutover is Session 91+.

**Test count target**: Don't spend more than 30 min on test pruning. Fix the flaky ones, remove obvious duplicates, move on.

**Performance**: Quick wins only. Pagination is the biggest bang-for-buck. Don't over-engineer caching.
