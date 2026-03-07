# Session 91b: Complete Everything — Supabase + Refactor + Discoveries + Testing + Collection Fix

**Context**: `docs/session_context/session-91b-context.md`
**Predecessor**: Session 91 (claimed 6 tracks shipped; audit found major gaps)

## Problem Statement

Sessions 90-91 promised: main.py fully refactored, testing speed fixed, discoveries overhauled, notifications wired, Supabase tables created. None of these are actually done. This session finishes ALL of it — no more deferring.

Nolan's exact words: "Everything currently in the prompt plus everything you are going to add based on this feedback better be done."

## Session Protocol
- Set `.claude/current_session.txt` to `91b`
- Read `tasks/lessons.md` at start
- Commit after every act, `/clear` between acts (NON-NEGOTIABLE — Lesson 89)
- Use Claude Chrome for ALL frontend verification (Lesson 97)
- Run `/session-review` at session end (mandatory)
- Use subagents in worktrees for parallel tracks
- Screenshots to `docs/screenshots/session-91b/`

---

## Parallelization Plan

### Phase 1: Orient (Act 0) — sequential on main
### Phase 2: Parallel tracks (Acts 1-5) — worktree subagents
### Phase 3: Sequential merge + verify (Act 6) — on main

| Track | Branch | Scope | Independent? |
|-------|--------|-------|-------------|
| A | `session-91b/supabase-notify` | Supabase migrations + notification wiring | Yes (until merge) |
| B | `session-91b/main-refactor` | Extract 4 route modules from main.py | Yes |
| C | `session-91b/discoveries` | Extract + overhaul discoveries | **Depends on B** |
| D | `session-91b/collection-fix` | AD-209 collection name fix + evals | Yes |
| E | `session-91b/test-speed` | Test speed optimization | Yes |

**Parallel Group 1**: A + B + D + E (all independent)
**Sequential**: C runs after B merges (both extract from main.py)
**Merge Order**: D → E → B → C → A

---

## Act 0: Orient + Verify State (5 min)

1. Read this prompt, context file, `tasks/lessons.md`
2. `git status`, `git log --oneline -5`, verify `make test-fast` passes
3. Set `.claude/current_session.txt` to `91b`
4. Create `docs/session_logs/session-91b-log.md` with phase checklist
5. Record current `make test-fast` timing as baseline

Commit: `chore: session 91b orient`

**IMMEDIATELY /clear after this commit.**

---

## Act 1 (Track A): Supabase Migrations + Notification Wiring

**Worktree**: `session-91b/supabase-notify`
**Key files**: `app/notification_routes.py`, `app/main.py` (save_registry), `scripts/sql/`, `.env`
**Goal**: Create all missing Supabase tables. Wire notification triggers so confirming an identity actually creates a notification.

### 1a. Execute Supabase Migrations

Use Supabase MCP, CLI, or psycopg2 with DATABASE_URL from .env to run SQL:

1. First, check which tables already exist:
   ```sql
   SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
   ```

2. Execute missing table SQL (in order — all use `IF NOT EXISTS`):
   - `scripts/sql/create_communities.sql`
   - `scripts/sql/seed_rhodes_community.sql`
   - `scripts/sql/create_global_person_links.sql`
   - `scripts/sql/create_life_events.sql`
   - `scripts/sql/007_notifications.sql`
   - `scripts/sql/alter_photos_media_group.sql`

3. Verify all tables exist:
   ```sql
   SELECT count(*) FROM communities;  -- expect 1 (Rhodes)
   SELECT count(*) FROM life_events;  -- expect 0 (seed next)
   SELECT count(*) FROM notifications; -- expect 0
   SELECT count(*) FROM global_person_links; -- expect 0
   ```

### 1b. Run Seed Scripts
```bash
python scripts/seed_life_events.py
```
Verify: `SELECT count(*) FROM life_events;` should return > 0.

### 1c. Wire Notification Triggers into save_registry()

In `app/main.py`, find `save_registry()`. Add logic:

1. Before saving, snapshot the identity's current state
2. After saving, if state changed from non-CONFIRMED → CONFIRMED:
   - Gather the identity's face IDs
   - Look up which photos contain those faces
   - Call `create_identity_confirmed_notification(identity_id, identity_name, photo_ids)`
3. Import from `app.notification_routes import create_identity_confirmed_notification`

### 1d. Fix Placeholder User ID

In `notification_routes.py`, `create_identity_confirmed_notification()` uses placeholder `"00000000..."`. Fix:
- Accept a `user_id` parameter (the admin who confirmed it)
- Fall back to checking `uploaded_by` on the photo
- The calling code in save_registry passes the current session user's Supabase auth ID

### 1e. Tests

- Confirming identity → notification created (mock Supabase, verify insert call)
- Non-CONFIRMED state change → NO notification
- Notification has correct identity_id, title, photo_ids
- Seed data produces correct life_events count

Commit: `feat(data): Supabase migrations + notification triggers wired`

### Subagent MUST:
- Run `make test-fast` before commit
- Commit ALL files
- NOT touch files outside scope

---

## Act 2 (Track B): Complete main.py Refactor — Route Extraction

**Worktree**: `session-91b/main-refactor`
**Key files**: `app/main.py` (26,100 lines → target ~16K)
**Goal**: Extract all remaining route groups into dedicated files. main.py becomes a utility/orchestrator hub.

### CRITICAL: This is mechanical extraction only. No logic changes. Each route moves with its helper functions.

### 2a. Extract `app/identity_routes.py`

Move all identity POST operations (~30 routes, ~2,500 lines):
- `/confirm/{identity_id}`, `/reject/{identity_id}`
- `/api/identity/{id}/merge/{source_id}`
- `/api/identity/{id}/reject-match/{neighbor_id}`
- `/api/identity/{id}/rename`, `/api/identity/{id}/names`
- `/api/identity/{id}/metadata`, `/api/identity/{id}/notes`
- `/api/identity/{id}/bulk-merge`, `/api/identity/{id}/bulk-reject`
- `/api/identity/{id}/skip`, `/api/identity/{id}/set-state`
- Associated helper functions that are ONLY used by these routes

Pattern: Same as existing extracted files (e.g., `person_routes.py`):
```python
import app.main as _main_mod

def register_identity_routes(rt):
    @rt("/confirm/{identity_id}", methods=["POST"])
    def confirm_identity(identity_id: str, sess):
        ...
```

### 2b. Extract `app/engagement_routes.py`

Move contribution/activity routes (~15 routes, ~1,000 lines):
- `/api/annotations/submit`, `/api/annotations/guest-submit`
- `/my-contributions`, `/activity`
- `/api/proposed-matches`
- `/inbox/{id}/review`, `/inbox/{id}/confirm`, `/inbox/{id}/reject`
- Associated helpers

### 2c. Extract `app/relationship_routes.py`

Move GEDCOM/relationship routes (~8 routes, ~400 lines):
- `/api/relationship/add`, `/api/relationship/update`, `/api/relationship/remove`
- `/api/gedcom/search`, `/api/gedcom/link`, `/api/gedcom/unlink`
- Associated GEDCOM helpers

### 2d. Extract `app/page_routes.py`

Move core page render routes (~15 routes, ~3,000+ lines):
- `/` (landing page)
- `/about`, `/help`
- `/collections`, `/collection/{slug}`
- `/map`, `/timeline`, `/tree`, `/connect`
- `/photos/{filename:path}` (static photo serving)
- `/health` (health check)
- Exception handler
- Associated page-building helpers

### 2e. Wire All New Route Files

In `app/main.py`, add imports and registration:
```python
from app.identity_routes import register_identity_routes
from app.engagement_routes import register_engagement_routes
from app.relationship_routes import register_relationship_routes
from app.page_routes import register_page_routes

register_identity_routes(rt)
register_engagement_routes(rt)
register_relationship_routes(rt)
register_page_routes(rt)
```

### 2f. Verify

After extraction:
- `wc -l app/main.py` should be ~14-17K lines (utility functions only, no @rt() routes)
- `make test-fast` passes with zero regression
- Every existing URL still resolves to the same handler

### 2g. Tests

- Add a test that verifies main.py has 0 remaining @rt() decorators (enforcement)
- All existing tests pass (zero regression is the acceptance criteria)

Commit: `refactor: complete main.py route extraction — identity, engagement, relationship, page routes`

### Subagent MUST:
- Run `make test-fast` before commit
- Verify `wc -l app/main.py` and report final line count
- NOT change any route logic — mechanical extraction only

---

## Act 3 (Track C): Discoveries Extraction + UX Overhaul

**Worktree**: `session-91b/discoveries` (starts AFTER Track B merges)
**Depends on**: Track B (main.py must already have routes extracted)
**Key files**: `app/main.py` (discoveries code), NEW `app/discoveries_routes.py`
**Key reference**: `docs/session_logs/discoveries_audit.md`, Session 71D context, Benatar feedback
**Goal**: Extract discoveries from main.py, then fix all known UX bugs.

### 3a. Extract `app/discoveries_routes.py`

Move all discoveries code from main.py (~25 routes, ~1,500 lines):
- `/discoveries` page route
- `/api/discoveries` paginated feed
- `/api/discoveries/photo-options`
- Discovery reject/confirm endpoints
- `_compute_discoveries()`, `_count_discoveries()`
- Discovery card builder helpers
- Discovery log loading

### 3b. Fix Sort Order — Recency First (P1)

Current: `discoveries.sort(key=lambda d: d.get("confidence_pct", 0), reverse=True)`

Fix: Sort by **timestamp descending** (most recent first):
```python
discoveries.sort(key=lambda d: d.get("created_at", ""), reverse=True)
```

If `created_at` doesn't exist on discovery entries:
- Add it when discoveries are computed (from the discovery_log entry timestamp)
- For auto-added Tier 1 entries, use the log timestamp
- For Tier 2 suggestions, use the computation timestamp

### 3c. Fix Navigation Dead Ends (P1)

Every discovery card MUST have:
- **Source face**: clickable → `/person/{identity_id}`
- **Source photo**: clickable thumbnail → `/photo/{photo_id}`
- **Target identity**: clickable name → `/person/{target_id}`
- **View photo**: link to photo page showing both faces in context
- **Co-occurrence**: show who else appears in the same photo

### 3d. Fix Confidence Display (P2)

Replace misleading percentage with confidence tier labels:
- Delete: `confidence_pct = (1 - distance / 2.0) * 100`
- Use existing `_CONFIDENCE_LABEL` tiers or AD-173 labels:
  - Distance < 0.80: "Strong match" (green)
  - 0.80-1.00: "Good match" (blue)
  - 1.00-1.20: "Possible match" (yellow)
  - > 1.20: "Weak match" (gray)

### 3e. Unify Card Design — Consistent with Rest of App (P2)

- Use the unified `identity_card` component (DD-006) for discovery cards
- Add share buttons (like every other page)
- Add collection name display
- Match the visual language of browse/person/compare pages
- Each card should feel like it belongs in the same app

### 3f. Maintain Three-Section Distinction

The three admin review sections must be visually and functionally distinct:

1. **Discoveries** (proactive, ML-generated)
   - Header: "Recent Discoveries" with count
   - Purpose text: "ML found these potential matches — newest first"
   - Shows: Tier 1 auto-adds + Tier 2 suggestions
   - Actions: Confirm / Reject / View Details

2. **New Matches** (triage inbox)
   - Purpose: All proposals requiring admin review
   - Different card layout from discoveries

3. **Help Identify** (community contribution)
   - Purpose: Cold cases for community help
   - Different layout emphasizing "Can you help?"

Each section should have:
- Clear header with icon and count
- One-sentence purpose statement
- Distinct card styling (color accent, layout)
- Consistent action buttons within section

### 3g. Tests

- Discoveries sorted by recency (newest first)
- Navigation links work: source face → person, source photo → photo, target → person
- Confidence labels show tiers not percentages
- Card renders use identity_card component
- Three sections have distinct styling
- Share buttons present on discovery cards

Commit: `feat(discoveries): extract + overhaul — recency sort, navigation, confidence labels, unified cards`

### Subagent MUST:
- Read `docs/session_logs/discoveries_audit.md` and Session 71D context FIRST
- Run `make test-fast` before commit
- Commit ALL files

---

## Act 4 (Track D): Fix Collection Name Overindexing — AD-209

**Worktree**: `session-91b/collection-fix`
**Key files**: `rhodesli_ml/gemini_extraction.py` (lines 257-276)
**Goal**: Fix the prompt so collection name is treated as weak provenance, not strong location signal.

### 4a. Fix the Prompt

In `rhodesli_ml/gemini_extraction.py`, replace the Photo Metadata Context section (lines 268-275):

**Current (WRONG)**:
```
IMPORTANT: The collection name often indicates the geographic origin of photos.
For example, "Tampa Collection" strongly suggests photos were taken in or near Tampa.
Use this as corroborating evidence alongside visual and biographical analysis.
```

**Replace with**:
```
NOTE ON COLLECTION NAMES: A collection name indicates WHO HAD these photos and
WHERE THEY WERE STORED, not necessarily where the photos were taken. For example,
a "Tampa Collection" means the photos were found in Tampa — but the actual photos
may depict locations the family visited or previously lived in (e.g., Asheville, NC;
New York; Rhodes).
Collection name is WEAK contextual evidence about the collector's later residence.
Visual evidence (signage, architecture) and GEDCOM residence data at the time of
the photo are MUCH STRONGER signals for actual photo location.
Do NOT assume the collection city is the photo location.
```

### 4b. Eval Tests

Create `rhodesli_ml/tests/test_collection_location_bias.py`:

**Test 1 — Prompt content (anti-regression)**: Verify prompt does NOT contain "strongly suggests photos were taken" or "geographic origin of photos".

**Test 2 — Prompt content (correctness)**: Verify prompt DOES contain "WHO HAD these photos" and "WEAK contextual evidence".

**Test 3 — Leon's Restaurant eval** (mark `@pytest.mark.gemini` — requires API key):
- Build prompt with: collection="Nace Capeluto Tampa Collection"
- GEDCOM: Leon Capeluto residence Asheville 1928-1940, occupation Asheville 1930
- Visible text: "LEON'S RESTAURANT"
- Send to Gemini with the actual Leon's Restaurant photo
- Assert location contains "Asheville" (case-insensitive)
- Assert location does NOT contain "Tampa" as primary location

**Test 4 — No over-correction**: Verify that when GEDCOM + visual evidence both point to Tampa, Gemini still returns Tampa (collection name being weak doesn't mean it's ignored when everything agrees).

**Test 5 — Collection absent**: When photo_metadata is None, metadata section not added.

### 4c. Write AD-209

Add to `docs/ml/ALGORITHMIC_DECISIONS.md`:

```
## AD-209: Collection Name as Weak Provenance, Not Location Signal

**Date**: 2026-03-07 | **Session**: 91b | **Supersedes**: Part of AD-204

**Problem**: AD-204 introduced collection name as a strong location signal. This caused Leon's Restaurant photo (3192877a90a174e9, "Nace Capeluto Tampa Collection") to be estimated as Tampa instead of Asheville, NC.

**Ground truth**: GEDCOM shows Leon Capeluto residence at 33 Elizabeth St, Asheville, NC (1928-1940). Family moved to Tampa after 1940. Collection named after Nace who ended up in Tampa.

**Decision**: Collection name is WEAK provenance context (who had the photos), not location evidence. Visual evidence and GEDCOM residence data at the time are stronger signals.

**Eval**: Leon's Restaurant → must return Asheville. Tampa photos with Tampa evidence → must still return Tampa.
```

Commit: `fix(ml): AD-209 — collection name is weak provenance, not location signal`

### Subagent MUST:
- Run both `make test-fast` AND `make test-ml` before commit
- Commit ALL files

---

## Act 5 (Track E): Testing Speed Optimization

**Worktree**: `session-91b/test-speed`
**Key files**: `tests/conftest.py`, `Makefile`, pytest config
**Goal**: `make test-fast` under 30 seconds.

### 5a. Diagnose Current Bottleneck

Run and profile:
```bash
source venv/bin/activate
time pytest tests/ -x -q --co -q 2>&1 | tail -5   # collection time only
time make test-fast 2>&1 | tail -5                   # full run time
pytest tests/ --durations=20 -q 2>&1 | tail -25      # slowest tests
```

### 5b. Session-Scoped App Fixture

In `tests/conftest.py`, change the app/TestClient fixture from function-scoped to session-scoped:
```python
@pytest.fixture(scope="session")
def app():
    """Load app once for entire test session."""
    from app.main import app as _app
    return _app

@pytest.fixture(scope="session")
def client(app):
    """Reuse TestClient across all tests."""
    from starlette.testclient import TestClient
    with TestClient(app) as c:
        yield c
```

This eliminates repeated app import + initialization per test.

### 5c. Lazy Imports for Heavy Modules

If InsightFace or other ML modules are imported at app startup:
- Wrap in lazy import pattern: `def get_insightface(): import insightface; ...`
- Only load when actually called (route handler), not at import time
- This reduces test collection time significantly

### 5d. Mock Expensive Imports at conftest Level

Add to conftest.py:
```python
# Mock expensive ML imports before any test imports app
import sys
from unittest.mock import MagicMock

# Prevent InsightFace from loading during tests
if 'insightface' not in sys.modules:
    sys.modules['insightface'] = MagicMock()
```

### 5e. Verify

After changes:
```bash
time make test-fast  # target: <30s
```

If still >30s, identify remaining bottleneck with `--durations=20` and address.

### 5f. Tests

- All existing tests still pass (zero regression)
- `make test-fast` completes in <30 seconds
- `make test-full` still works (no breaking changes to test infrastructure)

Commit: `perf(tests): optimize test speed — session-scoped fixtures + lazy imports`

### Subagent MUST:
- Run `make test-fast` and `make test-full` before commit
- Report before/after timing
- NOT break any existing tests

---

## Act 6: Merge + Deploy + Browser Verify + Assessment (30 min)

### 6a. Merge All Tracks

**Merge order**: D (collection fix) → E (test speed) → B (main refactor) → C (discoveries) → A (supabase + notifications)

Use `./scripts/merge.sh` or manual merge. Run `make test-fast` after EACH merge.

### 6b. Re-analyze Leon's Restaurant Photo

After deploying collection fix:
1. Navigate to https://rhodesli.nolanandrewfox.com/photo/3192877a90a174e9
2. Click "Re-analyze" (admin)
3. Verify location says Asheville, NC (not Tampa)
4. Take screenshot as evidence

### 6c. Browser Verify ALL Features (Claude Chrome)

**End-to-end verification — not just "page loads":**

1. **Notifications**:
   - Bell icon visible when logged in
   - Confirm an identity → bell badge updates
   - Click bell → /notifications → notification appears with identity name
   - "Mark as read" works, badge count decreases

2. **Life Events**:
   - /events page shows seeded events (NOT empty)
   - "Create New Event" form works (admin)
   - Event detail page shows title, date, description

3. **Discoveries**:
   - /discoveries page loads with clear section headers
   - Cards show confidence LABELS (not percentages)
   - Source face is clickable → person page
   - Source photo is clickable → photo page
   - Sorted by recency (newest first)
   - Cards visually consistent with rest of app

4. **Photo Backs**: David Franco photo flip, browse "Has back" filter

5. **General**: Landing page, person page, compare page still work

Save screenshots to `docs/screenshots/session-91b/`

### 6d. Write AD Entries

**AD-206**: GlobalPersonID schema — communities, global_person_links, community_id on identities/photos

**AD-207**: Postgres as source of truth — DATA_SOURCE feature flag, load_from_postgres()

**AD-208**: Observability — Sentry + PostHog + structlog, all env-gated

**AD-209**: Collection name as weak provenance (written in Track D)

### 6e. Update tasks/todo.md

The current todo.md is from Session 50. Rewrite to reflect current state.

### 6f. Mandatory Session Outputs

1. `docs/assessments/session-91b-assessment.md` — honest self-evaluation per phase with evidence
2. Update `docs/session_logs/session-91b-log.md` — actual completion per phase
3. Update `CHANGELOG.md` — v0.94.1
4. Update `ROADMAP.md` — mark completed items, move to Recently Completed
5. Update `docs/BACKLOG.md` — update status on relevant items
6. Update `docs/roadmap/SESSION_HISTORY.md` — session 91b entry
7. Run `/session-review`

Commit: `docs: session 91b completion — merge + browser verify + assessment`

---

## Acceptance Criteria

### MUST Ship (session is not complete without ALL of these)
- [ ] All Session 91 Supabase tables exist and are queryable (verified with SELECT)
- [ ] Life events table seeded, /events shows events (not empty)
- [ ] Notification trigger fires when identity confirmed (browser verified)
- [ ] Bell icon shows actual unread count (not always 0)
- [ ] main.py < 17,000 lines with 0 remaining @rt() decorators
- [ ] 4 new route files: identity_routes, engagement_routes, relationship_routes, page_routes
- [ ] discoveries_routes.py extracted from main.py
- [ ] Discoveries sorted by recency (newest first), not confidence
- [ ] Discovery cards have clickable navigation (face→person, photo→photo)
- [ ] Confidence labels (Strong/Good/Possible/Weak), NOT percentages
- [ ] Three admin review sections visually distinct
- [ ] Collection name prompt rewritten as weak provenance (AD-209)
- [ ] Leon's Restaurant re-analyzed → Asheville, not Tampa
- [ ] Eval tests for collection name bias
- [ ] `make test-fast` < 30 seconds
- [ ] All tests pass (zero regression from refactor)
- [ ] Browser verified with screenshots (end-to-end, not superficial)
- [ ] AD-206, AD-207, AD-208, AD-209 written
- [ ] Assessment + session log + CHANGELOG + ROADMAP updated

### Should Ship
- [ ] tasks/todo.md rewritten to current state
- [ ] Regression test: Tampa photo still returns Tampa after collection fix
- [ ] Discovery share buttons

### Deferred (Session 92+)
- [ ] DATA_SOURCE=postgres tested on Railway (requires env var flip)
- [ ] SENTRY_DSN + POSTHOG_API_KEY set on Railway (user creates accounts)
- [ ] Email notifications (PRD-028 P1+ — needs RESEND_API_KEY)
- [ ] Timeline integration for life events
- [ ] pgvector migration (embeddings stay as .npy)
- [ ] ML service extraction

## Key Lessons to Enforce

1. **"SHIPPED" means Feature Reality Contract passes** — data in database, app loads it, route works, UI renders real data, browser confirms it.
2. **main.py refactor was promised in Session 90b** and deferred through 91. No more deferring.
3. **Discoveries feedback from Benatar** was paired with notifications (both part of growth loop). Can't ship one without the other.
4. **Testing speed** directly blocks development velocity. main.py size contributes. Fix both.
5. **Supabase MCP/CLI** is available. "SQL files in git" is not "tables in database."
6. **Browser verification must be end-to-end** — "page loads" without testing features is theater (Lesson 97).

## Non-Goals
- Removing JSON files from repo (keep as fallback)
- ML pipeline changes or running ML on new photos
- Email notifications (PRD-028 P1+)
- UX redesign beyond discoveries fixes
- Frontend framework migration
