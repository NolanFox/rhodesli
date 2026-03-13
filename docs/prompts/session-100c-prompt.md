# Session 100c: Fox Family Speed-Run Review + Platform Reliability

**Context:** `docs/session_context/session-100c-context.md`
**Predecessor:** Session 100b-cont3

---

## Pre-Requisites
- Read `tasks/lessons.md` + `tasks/todo.md`
- Read `docs/session_context/session-100c-context.md` (full gap analysis + architecture)
- Read `docs/assessments/session-100-face-tagging-and-fox-family-audit.md` (competing software patterns)
- Set `.claude/current_session.txt` to `100c`

---

## Act 0: Orient (3 min)

1. Set `.claude/current_session.txt` to `100c`
2. `git log --oneline -10` to confirm clean state on main
3. Confirm tests pass: `source venv/bin/activate && pytest tests/ -x -q --ignore=tests/e2e/ --timeout=120`
4. Log starting state in session log

**Commit:** `chore: session 100c orient`
**/clear**

---

## Act 1: Fix Supabase Production Connection (P0, 15 min max)

**Goal:** Production app reads from Supabase, not JSON fallback. Hard time-box: 15 min. If not fixed, use fallback and move on.

### Investigation (these can be done in parallel)
1. **Railway logs:** `mcp__railway-mcp-server__get-logs` — filter for "supabase", "postgres", "DATA_SOURCE", "Postgres identity load failed"
2. **Health endpoint:** Read `app/page_routes.py:127` — find the exact condition that produces "Supabase connection skipped"
3. **Client init:** Read `app/supabase_data.py:37` — `get_supabase_client()` — what makes it return None?
4. **Registry load:** Find `IdentityRegistry.load_from_postgres()` classmethod — grep for it. Check what exception it catches at `app/main.py:1065-1075`

### Fix
- If `get_supabase_client()` returns None: check env var names match (`SUPABASE_URL`, `SUPABASE_ANON_KEY`)
- If `load_from_postgres()` throws: check the exception in Railway logs, fix import/connection
- If health endpoint logic is wrong: fix the conditional

### Verify
- Deploy: `railway deploy` (preferred) or `git push origin main`
- `curl https://rhodesli.nolanandrewfox.com/health` — should NOT say "connection skipped"
- Verify Yaacov Jacob Franco at `/person/e88d6698-46af-478c-8106-45a1bd8cf747` shows correct face

### Fallback (if 15 min exceeded)
- Push corrected `identities.json` to Railway volume: `POST /api/sync/push` with `RHODESLI_SYNC_TOKEN`
- Add BACKLOG entry: "INFRA-001: Supabase production connection debugging"
- Continue to Act 2

**Commit:** `fix(infra): fix Supabase production connection` (or `docs: BACKLOG Supabase fix deferred`)
**/clear**

---

## Act 2: Write PRD for Batch Cluster Review (10 min)

**Goal:** Create `docs/prds/039_batch_cluster_review.md` — the spec for speed-run review UX.

### PRD must cover:
1. **Problem:** 1600 INBOX identities across 635 photos. One-at-a-time review is unusable.
2. **User flow (speed run):**
   - Admin navigates to `/c/fox-family/admin/upload-review?mode=speed`
   - Page shows first cluster: large face thumbnails (up to 8), match confidence, suggested name, face count
   - Action buttons: **Confirm All** (green), **Reject All** (red), **Skip** (grey), **Dismiss** (muted)
   - After action: HTMX swaps next cluster (no page reload). `hx-target="#speed-run-card"` `hx-swap="outerHTML"`
   - Progress bar at top: "47 of 312 clusters reviewed"
   - Keyboard shortcuts: `Y`=confirm, `N`=reject, `S`=skip, `D`=dismiss
3. **Existing infrastructure to reuse:**
   - `POST /api/cluster-review/confirm-all` (`cluster_review_routes.py:1179`)
   - `POST /api/cluster-review/reject-all` (`cluster_review_routes.py:1224`)
   - Community scoping (`cluster_review_routes.py:790-801`)
   - Grouped identities logic (`cluster_review_routes.py:810-894`)
4. **New endpoints needed:**
   - `GET /admin/cluster-review/next?offset=N` — returns next unreviewed cluster as HTMX partial
   - `POST /admin/cluster-review/dismiss` — marks cluster as dismissed (skip from queue)
   - `GET /admin/cluster-review/progress` — returns progress counter partial
5. **Data model:** No new tables. Dismissed state tracked in `localStorage` (client-side, simple, no schema change).
6. **Acceptance criteria:**
   - Speed-run page loads in <2s for Fox Family
   - Confirm-all merges all cluster faces into target identity
   - Dismiss hides cluster from queue without data change
   - Auto-advance works without page reload
   - Progress counter accurate
   - Community-scoped
   - Keyboard shortcuts work
   - Existing dashboard view unchanged (speed-run is additive)
7. **Out of scope:** Split clusters, manual face drawing, cross-community merge from within speed-run

**Commit:** `docs: PRD-039 batch cluster review — speed-run mode`
**/clear**

---

## Act 3: Implement Speed-Run Cluster Review (30 min)

**Goal:** Build the speed-run review mode per PRD-039.

### 3a. New endpoint: next cluster partial

File: `app/cluster_review_routes.py` (append after line ~1265)

```
GET /admin/cluster-review/next?offset=N&community_slug=X
```

Returns a single cluster card (HTMX partial) with:
- Large face thumbnails (up to 8, using `_get_crop_url_for_face()`)
- Identity name + face count
- Match confidence (if proposal-based)
- Confirm All / Reject All / Skip / Dismiss buttons with `hx-post` + `hx-target="#speed-run-card"`
- Each button POSTs to respective endpoint, includes `offset` param so response loads next card

### 3b. Dismiss endpoint

File: `app/cluster_review_routes.py` (append)

```
POST /api/cluster-review/dismiss
```

Parameters: `identity_id`. Action: returns the next cluster card (same as auto-advance). Client tracks dismissed IDs in localStorage.

### 3c. Modify confirm-all and reject-all responses

File: `app/cluster_review_routes.py:1179` and `1224`

Current: returns a success message Div.
Change: when `speed_run=true` param is present, return the **next cluster card** instead of the success message (HTMX auto-advance).

### 3d. Speed-run page mode

File: `app/cluster_review_routes.py:777`

When `?mode=speed` query param:
- Render speed-run layout: progress bar + single cluster card container
- First cluster loaded via `/admin/cluster-review/next?offset=0`
- Keyboard shortcut JS: `document.addEventListener('keydown', ...)` mapping Y/N/S/D to button clicks
- Link from existing dashboard to speed-run mode: "Start Speed Run →" button

### 3e. Progress component

Inline in cluster card response:
- Total = count of clusters (filtered by community)
- Reviewed = offset position
- Render: `<div class="...">47 of 312 reviewed</div>` updated with each card swap

### Tests (append to `tests/test_cluster_review.py`)
- `test_speed_run_next_returns_cluster_card` — GET next returns valid HTMX partial
- `test_speed_run_confirm_all_auto_advances` — confirm-all with speed_run=true returns next card
- `test_speed_run_reject_all_auto_advances` — same for reject
- `test_speed_run_dismiss_returns_next` — dismiss returns next card
- `test_speed_run_community_scoped` — Fox Family only sees Fox clusters
- `test_speed_run_progress_counter` — offset increments correctly
- `test_speed_run_keyboard_shortcuts_in_page` — speed mode page includes keyboard JS

### Test gate
```bash
source venv/bin/activate && pytest tests/test_cluster_review.py tests/test_cluster_review_routes.py -x -q
source venv/bin/activate && pytest tests/ -x -q --ignore=tests/e2e/ --timeout=120
```

**Commit:** `feat(ux): speed-run cluster review mode with auto-advance and keyboard shortcuts`
**/clear**

---

## Act 4: Deploy + Browser Verify (15 min)

### Deploy
- `railway deploy` (preferred) or `git push origin main`
- Wait for deploy: `mcp__railway-mcp-server__list-deployments` — confirm status=SUCCESS, builder=DOCKERFILE

### Browser verification (Chrome — admin is logged in)

| # | URL | Check | Expected |
|---|-----|-------|----------|
| 1 | `/c/fox-family/admin/upload-review` | Dashboard loads | Three sections with Fox Family clusters |
| 2 | `/c/fox-family/admin/upload-review?mode=speed` | Speed-run loads | First cluster card with action buttons |
| 3 | Speed-run: click Confirm All | Auto-advance | Next cluster loads without page reload |
| 4 | Speed-run: press `S` key | Skip works | Next cluster loads |
| 5 | Speed-run: press `D` key | Dismiss works | Next cluster loads, dismissed hidden |
| 6 | Progress bar | Counter updates | Shows "N of M reviewed" |
| 7 | `/` (Rhodes landing) | Rhodes unbroken | Landing page loads, photos visible |
| 8 | `/person/e88d6698-...` | Yaacov Franco | Correct face (if Supabase fixed) |
| 9 | Identity cards | Face cycling arrows | Visible at opacity-60 (Session 100b fix) |

Save screenshots to `docs/screenshots/session-100c/`

**Commit:** `docs: session 100c browser verification screenshots`
**/clear**

---

## Act 5: Assessment + Docs (10 min)

1. Re-read THIS PROMPT from disk: `cat docs/prompts/session-100c-prompt.md`
2. For each act, verify completion with evidence
3. Write `docs/assessments/session-100c-assessment.md`
4. Update `docs/session_logs/session-100c-log.md`
5. Update:
   - `CHANGELOG.md` — new version entry
   - `ROADMAP.md` — mark PRD037-004 complete, check UX-202, add session 100c to Recently Completed
   - `docs/BACKLOG.md` — update UX-202 status, any new items
6. Run BOTH test suites:
   ```bash
   source venv/bin/activate && pytest tests/ -x -q --ignore=tests/e2e/ --timeout=120
   source venv/bin/activate && pytest rhodesli_ml/tests/ -x -q
   ```

**Commit:** `docs: session 100c assessment — speed-run cluster review shipped`

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| Supabase working OR fallback + BACKLOG | Railway logs + curl /health | No "connection skipped" OR BACKLOG entry |
| Speed-run page loads for Fox Family | Browser screenshot #2 | Cluster card renders with action buttons |
| Confirm-all auto-advances | Browser screenshot #3 | Next cluster swaps in |
| Keyboard shortcuts work | Browser test #4 | S/D keys trigger actions |
| Progress counter | Browser screenshot #6 | Shows accurate "N of M" |
| Existing dashboard unchanged | Browser screenshot #1 | Three sections still render |
| Rhodes platform unbroken | Browser screenshot #7 | Landing page loads |
| App tests pass | pytest output | 4150+ passed |
| ML tests pass | pytest output | 578+ passed |
| Assessment file exists | ls | `docs/assessments/session-100c-assessment.md` |
| Session log exists | ls | `docs/session_logs/session-100c-log.md` |
| ROADMAP updated | grep | PRD037-004 checked, UX-202 checked |
| Screenshots saved | ls | `docs/screenshots/session-100c/` |

## Non-Negotiables

- No data loss — confirm-all and reject-all must use existing registry save paths (`registry.save()` + `_invalidate_all_caches()`)
- No breaking existing dashboard — speed-run is additive (`?mode=speed`)
- No heavy ML on request path (AD-110)
- Community scoping preserved — Fox Family speed-run shows only Fox clusters
- Keyboard shortcuts must not fire inside input fields (guard with `event.target.tagName` check)
- Every HTMX swap must include `hx-swap-oob` for the progress counter update
- Tests before every commit, /clear after every act

## Key Files Reference

| File | Line | What to change |
|------|------|---------------|
| `app/cluster_review_routes.py` | 777 | Add `?mode=speed` branch to upload-review |
| `app/cluster_review_routes.py` | 1179 | Modify confirm-all to auto-advance when speed_run=true |
| `app/cluster_review_routes.py` | 1224 | Modify reject-all to auto-advance when speed_run=true |
| `app/cluster_review_routes.py` | NEW (~1265) | `GET /admin/cluster-review/next` endpoint |
| `app/cluster_review_routes.py` | NEW | `POST /api/cluster-review/dismiss` endpoint |
| `tests/test_cluster_review.py` | append | 7+ speed-run tests |
| `app/page_routes.py` | 127 | Health endpoint (Act 1 investigation) |
| `app/supabase_data.py` | 37 | `get_supabase_client()` (Act 1 investigation) |
| `app/main.py` | 151 | `DATA_SOURCE` definition (Act 1 investigation) |
| `app/main.py` | 1065-1075 | Postgres load + fallback (Act 1 investigation) |
