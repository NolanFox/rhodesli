# Session 95: Fox MVP + Standalone Tool Suite

**Context**: `docs/session_context/session-95-context.md`
**Predecessor**: Session 94 (`docs/assessments/session-94-assessment.md`)

## Problem Statement

PRD-035 Phase 1 (Fox Family MVP) and TOOLS-001 (Standalone Tool Suite) are the
top two priorities. They have zero file overlap and can run in parallel via
worktrees. This session builds both simultaneously.

## Session Protocol
- Set `.claude/current_session.txt` to `95`
- Read `tasks/lessons.md` at start
- Commit after every sub-task, `/clear` between acts (NON-NEGOTIABLE)
- Use worktree subagents for parallel tracks
- Run `make test-fast` before every commit
- Run `/session-review` at session end

---

## Act 0: Orient + Merge Session 94 Branches (10 min) — sequential on main

1. Read this prompt, context file, PRD-035, and `tasks/lessons.md`
2. `git status`, `git log --oneline -10`, verify `make test-fast` passes
3. Set `.claude/current_session.txt` to `95`
4. Create `docs/session_logs/session-95-log.md` with phase checklist

5. **Merge Session 94 branches** (in order):
   ```bash
   ./scripts/merge.sh session-94/doc-sync session-94/ci-verify session-94/branch-cleanup session-94/ux-fixes
   ```
   Run `make test-fast` after merge. Fix any conflicts.

6. Push to origin (deploys to Railway):
   ```bash
   git push origin main
   ```

Commit: `chore: session 95 orient + merge session 94 branches`

**IMMEDIATELY /clear after this commit.**

---

## Act 1: Create Supabase Tables + Migration (15 min) — sequential on main

Before launching parallel tracks, create the shared database infrastructure
both tracks may need.

1. **Create new Supabase tables** (run SQL via Supabase dashboard or script):
   - `photo_communities` (photo_id TEXT, community_id UUID, added_at, added_by)
   - `identity_communities` (identity_id UUID, community_id UUID, is_primary BOOLEAN, added_at)
   - `upload_batches` (id UUID, community_id UUID, source_description, date_range_hint, location_hint, notes, photo_count, created_at)
   - Add `upload_batch_id` column to `photos` table
   - Add `landing_title`, `landing_subtitle`, `landing_hero_style` columns to `communities`

2. **Create Fox Family community** in Supabase:
   ```sql
   INSERT INTO communities (slug, name, admin_emails, r2_prefix, landing_title, landing_subtitle)
   VALUES ('fox-family', 'Fox Family Archive', ARRAY['NolanFox@gmail.com'],
           'fox_photos/', 'Fox Family Archive', 'Preserving our family''s visual history');
   ```

3. **Write migration script** to tag existing photos/identities with Rhodes community:
   - Script: `scripts/migrate_community_membership.py`
   - Insert into `photo_communities` for all existing photos → rhodes community
   - Insert into `identity_communities` for all existing identities → rhodes community
   - Dry-run mode first, then execute

4. **Add Supabase sync functions** to `app/supabase_data.py`:
   - `load_communities()` — fetch all communities
   - `get_community_by_slug(slug)` — fetch community by slug
   - `load_photos_for_community(community_id)` — community-scoped photo query
   - `load_identities_for_community(community_id)` — community-scoped identity query

5. **Write tests** for all new sync functions.

Commit: `feat(data): community tables + migration + sync functions`

**IMMEDIATELY /clear after this commit.**

---

## Act 2: Launch Parallel Tracks (main thread manages, worktrees execute)

Launch both tracks as worktree subagents. Monitor progress. Do NOT do
other work on main while tracks run — wait for completion.

### Track 1: Community Infrastructure (`session-95/community-infra`)
**Files:** `app/page_routes.py`, `app/upload_routes.py`, `app/admin_routes.py`, `app/main.py`

#### 1a. Community Routing Middleware
- Add middleware to `app/main.py` that extracts community from `/c/{slug}/...` URL prefix
- Set `request.state.community_slug` and `request.state.community` (fetched from Supabase)
- If no `/c/` prefix, default to Rhodes community
- Add community context to all route handlers that need it

#### 1b. Community-Scoped Browse
- Modify browse page in `app/page_routes.py` to filter by active community
- Use `load_photos_for_community()` from Act 1
- Show community name in page header
- Community badge on nav bar showing active community

#### 1c. Community Landing Pages
- New route: `/c/{slug}` serves community-specific landing page
- Per-community hero section with `landing_title`, `landing_subtitle`
- Community-specific stats (photo count, identity count for that community)
- Featured photos from that community only

#### 1d. Community-Scoped Upload + Bulk Improvements
- Modify upload in `app/upload_routes.py`:
  - `MAX_FILES_PER_UPLOAD = 200` (was 50)
  - Add TIFF detection: check file extension + magic bytes
  - TIFF→JPG conversion via Pillow (95% quality, preserve EXIF)
  - Add batch metadata form: source_description, date_range_hint, location_hint, notes
  - Create `upload_batches` record on each upload
  - Associate photos with batch via `upload_batch_id`
  - Photos auto-tagged to active community via `photo_communities`
- Client-side: chunk uploads into groups of 20 with progress bar

#### 1e. Community Admin CRUD
- New routes in `app/admin_routes.py`:
  - `GET /admin/communities` — list all communities
  - `GET /admin/communities/new` — create form
  - `POST /admin/communities` — create community
  - `GET /admin/communities/{slug}/edit` — edit form
  - `POST /admin/communities/{slug}` — update community

#### 1f. Backward Compatibility
- `/browse` serves Rhodes content (community defaults to Rhodes when no prefix)
- `/identify/{id}` serves with Rhodes context
- All existing share links (shared on Facebook) continue to work
- No existing URLs return 404
- **TEST THIS EXTENSIVELY** — regression tests for all existing routes

#### 1g. Tests
- Community routing middleware tests (with prefix, without prefix, invalid slug)
- Community-scoped browse tests
- Community landing page tests
- Upload batch metadata tests
- TIFF conversion tests
- Backward compatibility tests (every existing URL still works)
- Community CRUD tests

Run `make test-fast` before commit. Conventional commit.

### Track 2: Standalone Tool Suite (`session-95/tools-standalone`)
**Files:** `app/estimate_routes.py`, `app/compare_routes.py`, new `app/tools_routes.py`

#### 2a. Tools Hub Landing Page
- New file: `app/tools_routes.py`
- Route: `GET /tools` — landing page showing all available tools
- Cards for each tool: Date & Location Estimator, Face Comparison
- Clean, community-agnostic design
- Register routes in `app/main.py` (add import)

#### 2b. Shared Tool Navigation Bar
- Create reusable function `tools_nav_bar(active_tool=None)` in `app/tools_routes.py`
- Renders: `[Tools Hub] | [Date Estimator] | [Face Compare]`
- Active tool highlighted
- Consistent with site design but community-agnostic
- Import and use in both estimate_routes and compare_routes

#### 2c. Standalone Date Estimator
- Move `/estimate` to `/tools/estimate` (keep `/estimate` as redirect)
- Add `tools_nav_bar(active_tool="estimate")` at top of page
- Remove any Rhodes-specific language (community-agnostic)
- Keep all existing functionality (Gemini analysis, photo upload, results)
- Update any hardcoded references to "Rhodes" in estimate copy

#### 2d. Standalone Face Compare
- Move `/compare` to `/tools/compare` (keep `/compare` as redirect)
- Add `tools_nav_bar(active_tool="compare")` at top of page
- Remove any Rhodes-specific language
- Keep all existing functionality (upload, workspace, results)
- Update any hardcoded references to "Rhodes" in compare copy

#### 2e. URL Redirects
- `/estimate` → 302 redirect to `/tools/estimate`
- `/compare` → 302 redirect to `/tools/compare`
- All existing API routes (`/api/estimate/*`, `/api/compare/*`) remain unchanged
- Share links from existing compare results continue to work

#### 2f. Tests
- Tools hub page renders with tool cards
- Tool navigation bar renders on all tool pages
- Redirects from old URLs work
- All existing estimate/compare tests pass (no regressions)
- No Rhodes-specific language in standalone tool pages

Run `make test-fast` before commit. Conventional commit.

**IMMEDIATELY /clear after both tracks complete and are committed.**

---

## Act 3: Merge Parallel Tracks + Integration Test (15 min) — sequential on main

1. Merge Track 2 first (less code impact):
   ```bash
   ./scripts/merge.sh session-95/tools-standalone
   ```
   Run `make test-fast`. Fix conflicts if any.

2. Merge Track 1:
   ```bash
   ./scripts/merge.sh session-95/community-infra
   ```
   Run `make test-fast`. Fix conflicts if any.

3. **Integration verification:**
   - `/c/rhodes/browse` returns 200 with Rhodes photos
   - `/c/fox-family` returns 200 with Fox landing page
   - `/browse` still works (backward compat → Rhodes)
   - `/tools` returns 200 with tool cards
   - `/tools/estimate` returns 200 with date estimator
   - `/tools/compare` returns 200 with face compare
   - `/estimate` redirects to `/tools/estimate`

4. Push to origin: `git push origin main`

Commit: `chore: merge session 95 parallel tracks`

**IMMEDIATELY /clear after this commit.**

---

## Act 4: Browser Verification + Deploy (15 min) — sequential on main

1. Wait for Railway deploy to complete (check logs or health endpoint)
2. **Verify in production browser** (Claude Chrome — admin is logged in):
   - `/c/rhodes/browse` — Rhodes photos render correctly
   - `/c/fox-family` — Fox landing page renders (empty but correct)
   - `/browse` — backward compat works
   - `/tools` — tools hub renders with cards
   - `/tools/estimate` — upload + estimate flow works
   - `/tools/compare` — upload + compare flow works
   - Navigation bar shows on all tool pages
   - Community switcher/indicator shows in nav
3. Take screenshots for evidence
4. Log results in session log

Commit: `docs: browser verification screenshots`

**IMMEDIATELY /clear after this commit.**

---

## Act 5: Session Review + Assessment

1. Re-read this prompt
2. Verify all acceptance criteria from PRD-035 Phase 1
3. Run `/session-review`
4. Write `docs/assessments/session-95-assessment.md`
5. Update ROADMAP.md, BACKLOG.md, CHANGELOG.md, SESSION_HISTORY.md
6. Update `docs/prds/035_multi_community/PHASES.md` — check off Phase 1 items

---

## Acceptance Criteria

### Community Infrastructure (Track 1)
- [ ] `/c/fox-family` serves Fox Family Archive landing page
- [ ] `/c/fox-family/browse` returns 200 (empty, no photos yet)
- [ ] `/c/rhodes/browse` shows only Rhodes photos
- [ ] `/browse` still works (defaults to Rhodes)
- [ ] `/identify/{id}` still works for existing identities
- [ ] Upload cap raised to 200
- [ ] TIFF files auto-convert to JPG on upload
- [ ] Upload batch metadata form works (source, date, location, notes)
- [ ] Admin can create new communities at `/admin/communities`
- [ ] Community indicator visible in navigation
- [ ] All existing share links still work (backward compat)
- [ ] All existing tests pass (no regressions)

### Standalone Tool Suite (Track 2)
- [ ] `/tools` serves tools hub with cards for each tool
- [ ] `/tools/estimate` serves date estimator with tool nav bar
- [ ] `/tools/compare` serves face compare with tool nav bar
- [ ] `/estimate` redirects to `/tools/estimate`
- [ ] `/compare` redirects to `/tools/compare`
- [ ] No Rhodes-specific language on standalone tool pages
- [ ] Tool nav bar appears on all tool pages
- [ ] All existing estimate/compare API routes still work
- [ ] All existing tests pass (no regressions)

### Infrastructure
- [ ] Session 94 branches merged
- [ ] New Supabase tables created
- [ ] Existing data tagged with Rhodes community
- [ ] Browser verification screenshots saved
- [ ] Assessment written with evidence
