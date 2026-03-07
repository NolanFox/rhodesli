# Session 91: Ship PRD Backlog + Postgres Migration + Platform Foundation

**Context**: `docs/session_context/session-91-context.md`
**Predecessor**: Session 90c (Gemini prompt fix, face alignment timestamp, flaky test cleanup)

## Problem Statement

Rhodesli has two categories of unfinished work that must ship together:

**User-facing features (4 PRDs written but not implemented):**
1. **PRD-028**: Contributor Notifications (P0 — growth loop is broken, Benatar feedback)
2. **PRD-027 Phase A**: R2 nightly backup (total data loss risk)
3. **PRD-011**: Life Events & Context Graph (event tagging + timeline)
4. **PRD-029**: Photo Back & Media Groups (half-built from Session 90b)

**Platform foundation (architectural work for multi-collection future):**
5. **PRD-027 Phases B/C**: Postgres read flip — eliminate JSON as source of truth
6. **GlobalPersonID + community schema** — low cost now, very high cost later
7. **Observability**: Sentry + PostHog + structlog

After this session: contributors get feedback, data is backed up, reads come from Postgres, schema supports future collections, and we have error tracking + analytics.

## Session Protocol
- Set `.claude/current_session.txt` to `91`
- Read `tasks/lessons.md` and `tasks/todo.md` at start
- Commit after every act, `/clear` between acts (NON-NEGOTIABLE — Lesson 89, failed 5 times)
- Use Claude Chrome for ALL frontend verification (Lesson 97)
- Run `/session-review` at session end (mandatory)
- Screenshots to `docs/screenshots/session-91/`
- Use `/simplify` after implementation phases

---

## Dependencies on Prior Sessions

Session 90b shipped shadow writes (`save_registry()` and `save_photo_registry()` fire-and-forget to Supabase). Session 90c shipped Gemini prompt improvements. This session builds on both.

**Verify before starting:**
- [ ] Shadow writes work (check `app/supabase_data.py` has `shadow_write_identity` and `shadow_write_photo`)
- [ ] Back image upload route exists (`POST /api/photo/{photo_id}/back-image` in `app/photo_routes.py`)
- [ ] Timeline route exists (`/timeline`)
- [ ] Supabase tables from Session 90b exist (check `app/supabase_data.py` for table references)
- [ ] `make test-fast` passes on main

**If any dependency is incomplete**, Act 1 must finish it before launching parallel tracks.

---

## Parallelization Plan

**Phase 1** (Act 0): Sequential on main — orient, verify state, fix gaps
**Phase 2** (Acts 1-6): Parallel worktree subagents — 6 tracks
**Phase 3** (Act 7): Sequential on main — merge all tracks, browser verify, assessment

### Track Layout

| Track | Worktree Branch | Scope | Files Touched |
|-------|----------------|-------|---------------|
| A | `session-91/notifications` | PRD-028 Notifications | NEW `app/notification_routes.py`, Supabase tables, `app/main.py` (header bell icon) |
| B | `session-91/r2-backup` | PRD-027 Phase A R2 Backup | NEW `scripts/backup_to_r2.py`, `scripts/restore_from_r2.py` |
| C | `session-91/life-events` | PRD-011 Life Events | NEW `app/event_routes.py`, Supabase tables, timeline UI |
| D | `session-91/photo-backs` | PRD-029 Photo Backs | `app/photo_routes.py`, `app/browse_routes.py`, Supabase photo columns |
| E | `session-91/postgres-reads` | Postgres Read Flip + GlobalPersonID | `core/registry.py`, `core/photo_registry.py`, `app/supabase_data.py`, NEW `scripts/sql/` files |
| F | `session-91/observability-docs` | Sentry + PostHog + structlog + Doc Updates | `requirements.txt`, `app/main.py` (middleware), docs/ |

### File Conflict Analysis

- **Track B**: Fully independent (new scripts only) — merge FIRST
- **Track C**: Mostly independent (new event_routes.py) — merge SECOND
- **Track D**: Touches photo_routes.py, browse_routes.py — merge THIRD
- **Track F**: Touches requirements.txt, main.py (middleware init), docs only — merge FOURTH
- **Track A**: Touches main.py (header bell icon), new notification_routes.py — merge FIFTH
- **Track E**: Heaviest — core/registry.py, core/photo_registry.py, supabase_data.py — merge LAST

**Merge order**: B -> C -> D -> F -> A -> E

### Subagent Context Briefs

Each subagent gets:
1. This prompt (their track section only)
2. The session context file (`docs/session_context/session-91-context.md`)
3. `tasks/lessons.md`
4. The relevant PRD (if applicable)
5. Key source files listed in their track section

Each subagent MUST:
- Run `make test-fast` before every commit (Lesson 80)
- Commit ALL files before completing (Lesson 87)
- Use conventional commits: `feat/fix(scope): description`
- NOT touch files outside their listed scope

---

## Act 0: Orient + Verify State (10 min)

1. Read this prompt, context file, `tasks/lessons.md`
2. `git log --oneline -5`, `git status`, verify `make test-fast` passes
3. Set `.claude/current_session.txt` to `91`
4. Create `docs/session_logs/session-91-log.md` with phase checklist
5. **Verify all dependencies** listed above
6. **Verify Supabase tables** — check what tables already exist from 90b shadow writes
7. If any gaps: fix them here before launching subagents

Commit: `chore: session 91 orient + verify state`

**IMMEDIATELY /clear after this commit.**

---

## Act 1 (Track A): PRD-028 — Contributor Notifications P0

**Worktree**: `session-91/notifications`
**PRD**: `docs/prds/028_contributor_notifications.md`
**Key files to read**: `app/main.py` (header/nav), `app/supabase_data.py`, `app/auth.py`
**Goal**: In-app notification center with event triggers for identity confirmation and auto-clustering matches.

### 1a. Supabase Tables

```sql
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    photo_id TEXT,
    identity_id UUID,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_unread
    ON notifications(user_id, is_read)
    WHERE is_read = FALSE;

CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id UUID PRIMARY KEY,
    email_enabled BOOLEAN DEFAULT TRUE,
    in_app_enabled BOOLEAN DEFAULT TRUE,
    digest_frequency TEXT DEFAULT 'daily',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 1b. Notification Routes

Create `app/notification_routes.py`:

1. `GET /notifications` — Page with chronological list for logged-in user
   - HTMX-powered, paginated (20 per page)
   - Unread items highlighted
   - Each item: icon (by type), title, body preview, timestamp, link to photo/person
   - "Mark all as read" button
2. `POST /api/notifications/{id}/read` — Mark single notification as read
3. `POST /api/notifications/mark-all-read` — Mark all as read
4. `GET /api/notifications/count` — Returns unread count (for bell icon polling)

### 1c. Bell Icon in Header

Add to the site header (in `app/main.py` nav):
- Bell icon visible to all logged-in users
- Red badge with unread count (hidden when 0)
- `hx-get="/api/notifications/count" hx-trigger="every 30s"` for polling
- Click navigates to `/notifications`

### 1d. Event Triggers

Hook into existing flows to create notifications:

1. **Identity confirmation** — When state changes to CONFIRMED in `save_registry()`:
   - Find photo(s) containing that identity's faces
   - Find uploader (`uploaded_by` in photo metadata)
   - Create notification: "Isaac Cohen identified in your photo"
2. **Auto-clustering match** — When Tier 1 match auto-added:
   - Create notification for photo uploader: "New face match found in your photo"
3. **Manual creation** — Admin endpoint `POST /api/notifications/create` for testing

### 1e. Photo Uploader Tracking

If `uploaded_by` field doesn't exist in photo metadata:
- Add to photo upload flow (store current user's email/ID)
- Backfill: set existing Benatar photos to `uploaded_by` if known

### 1f. Tests

- Notification CRUD (create, list, mark read, count)
- Event trigger on identity confirmation creates notification
- Bell icon renders for logged-in users, hidden for anonymous
- Pagination works
- Mark-all-read clears badge count

**Acceptance**: Logged-in user sees bell icon. Confirming an identity creates a notification. /notifications page shows chronological list. Mark-as-read works.

Commit: `feat(notifications): PRD-028 P0 — in-app notification center + event triggers`

---

## Act 2 (Track B): PRD-027 Phase A — R2 Nightly Backup

**Worktree**: `session-91/r2-backup`
**PRD**: `docs/prds/027_data_migration.md` (Phase A)
**Key files to read**: `scripts/upload_to_r2.py` (R2 boto3 patterns), `scripts/init_railway_volume.py`
**Goal**: Nightly backup of critical JSON/NPY files to R2.

### 2a. Backup Script

Create `scripts/backup_to_r2.py`:
- Uploads to `r2://rhodesli-photos/backups/YYYY-MM-DD/`:
  - `identities.json`
  - `photo_index.json`
  - `embeddings.npy`
  - `date_labels.json`
  - `photo_locations.json`
- Uses boto3 (same as existing R2 upload scripts)
- Requires: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`
- Prunes backups older than 30 days (keep max 30 snapshots)
- Logs success/failure with file sizes and timestamps
- `--dry-run` flag for preview

### 2b. Restore Script

Create `scripts/restore_from_r2.py`:
- Lists available backup dates
- `--date YYYY-MM-DD` to restore specific backup
- Downloads to `data/` directory (with confirmation prompt)
- `--list` flag to show available backups without restoring

### 2c. Startup Hook (Optional)

Add to Railway startup or `scripts/init_railway_volume.py`:
- If `AUTO_BACKUP=true` env var set, run backup on app startup
- Also configurable as Railway cron job

### 2d. Tests

- Backup script generates correct R2 keys
- Restore script lists backups correctly
- Pruning logic (keep 30 days)
- Dry-run doesn't upload

**Acceptance**: `python scripts/backup_to_r2.py --dry-run` shows correct files and R2 paths. Restore script lists available backups.

Commit: `feat(ops): PRD-027 Phase A — R2 nightly backup for critical data files`

---

## Act 3 (Track C): PRD-011 — Life Events & Context Graph

**Worktree**: `session-91/life-events`
**PRD**: `docs/prds/011_life_events_context_graph.md`
**Key files to read**: `data/rhodes_context_events.json`, timeline route code, person page code
**Goal**: Event tagging system connecting photos, people, places, and dates.

### 3a. Flesh Out PRD-011

The PRD is currently a stub. Before implementing, expand it with:
- Event types: wedding, funeral, holiday, reunion, immigration, graduation, birthday, military, business
- Data model (Supabase tables)
- UI flows (tag from photo page, browse events, filter timeline by event)
- Acceptance criteria

### 3b. Supabase Tables

```sql
CREATE TABLE IF NOT EXISTS life_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    location_name TEXT,
    lat NUMERIC(10,7),
    lng NUMERIC(10,7),
    event_date DATE,
    event_year INTEGER,
    date_precision TEXT DEFAULT 'year',  -- 'exact', 'month', 'year', 'decade'
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES life_events(id) ON DELETE CASCADE,
    identity_id UUID NOT NULL,
    role TEXT DEFAULT 'attendee',  -- 'subject', 'attendee', 'photographer', 'mentioned'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(event_id, identity_id)
);

CREATE TABLE IF NOT EXISTS event_photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES life_events(id) ON DELETE CASCADE,
    photo_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(event_id, photo_id)
);

CREATE INDEX idx_event_participants_identity ON event_participants(identity_id);
CREATE INDEX idx_event_photos_photo ON event_photos(photo_id);
CREATE INDEX idx_life_events_year ON life_events(event_year);
```

### 3c. Event Routes

Create `app/event_routes.py`:

1. `GET /events` — Browse all events (admin view initially)
   - Chronological list with event type icons
   - Filter by type, year range, person
2. `GET /events/{id}` — Event detail page
   - Title, description, date, location
   - Linked photos (thumbnails)
   - Participants list with links to person pages
3. `POST /api/events` — Create event (admin only)
   - Form: type, title, description, date, location
4. `POST /api/events/{id}/photos` — Link photo to event
5. `POST /api/events/{id}/participants` — Link person to event
6. `DELETE /api/events/{id}/photos/{photo_id}` — Unlink photo
7. `DELETE /api/events/{id}/participants/{identity_id}` — Unlink person

### 3d. Photo Page Integration

On photo detail pages, add an "Events" section (admin-visible):
- Show events this photo is linked to
- "Add to Event" button — dropdown of existing events + "Create New Event"
- HTMX-powered: adding to event updates the section without full reload

### 3e. Person Page Integration

On person detail pages, add a "Life Events" section:
- Chronological list of events this person participated in
- Each event shows: type icon, title, date, photo count

### 3f. Timeline Integration

If `/timeline` route exists, add event markers:
- Life events appear as distinct cards (different styling from photo cards)
- Events without photos still appear on timeline
- Combine with existing `rhodes_context_events.json` historical events

### 3g. Seed Data

Import key Rhodes community events from `data/rhodes_context_events.json` into the life_events table.

### 3h. Tests

- Event CRUD (create, read, update, delete)
- Link/unlink photos and participants
- Photo page shows events section
- Person page shows life events
- Timeline includes event markers
- Event type filtering works

**Acceptance**: Admin can create events, link photos and people, see events on photo/person pages and timeline.

Commit: `feat(events): PRD-011 — life events & context graph`

---

## Act 4 (Track D): PRD-029 — Complete Photo Backs & Media Groups

**Worktree**: `session-91/photo-backs`
**PRD**: `docs/prds/029_photo_back_and_media_groups.md`
**Key files to read**: `app/photo_routes.py` (back-image route), `app/browse_routes.py`, `tests/test_back_image.py`
**Goal**: Complete the remaining work from PRD-029 that wasn't finished in Session 90b.

### What's already built (Session 90b):
- `POST /api/photo/{photo_id}/back-image` — Upload back image
- `POST /api/photo/{photo_id}/back-transcription` — Update transcription
- 3D flip CSS animation with `rotateY(180deg)`
- Photo metadata with `back_image`, `media_group_id`, `related_media` fields
- Tests in `test_back_image.py` and `test_photo_flip.py`
- **Verified working in production** (David Franco family photo — Session 90c audit confirmed Turn Over button, Front/Back labels, back image, transcription, orientation controls all present)

### What's remaining:

### 4a. Supabase Photo Table Columns

Add media group columns to the photos Supabase table:
```sql
ALTER TABLE photos ADD COLUMN IF NOT EXISTS media_group_id TEXT;
ALTER TABLE photos ADD COLUMN IF NOT EXISTS media_role TEXT DEFAULT 'front';
ALTER TABLE photos ADD COLUMN IF NOT EXISTS parent_photo_id TEXT;
```

### 4b. Media Group API Endpoint

`GET /api/photo/{photo_id}/media-group` — Returns all related media:
```json
{
  "group_id": "3192877a90a174e9",
  "items": [
    {"photo_id": "3192877a90a174e9", "role": "front", "url": "..."},
    {"photo_id": "3192877a90a174e9_back", "role": "back", "url": "..."}
  ]
}
```

### 4c. Front/Back Label During Flip

Add a visual indicator showing "Front" or "Back" during/after the flip animation:
- Small badge in top-right corner of photo
- Toggles between "Front" and "Back" as the card flips
- CSS transition matches the flip timing

### 4d. Browse Page "Has Back" Filter

Add to the sort/filter bar on `/photos`:
- New filter option: "All" | "Front only" | "Has back image"
- Filter is preserved across pagination (in URL query params)

### 4e. Visual Badge on Photo Cards

On the browse grid, show a small flip icon on photo cards that have back images:
- Subtle icon in card corner (e.g., a two-sided card icon)
- Tooltip: "This photo has a back image"

### 4f. Tests

- Media group endpoint returns correct structure
- Front/Back label toggles on flip
- Browse filter by "Has back" works
- Badge appears on cards with back images
- Back image inherits collection/source from front

**Acceptance**: David Franco photo shows flip with Front/Back label. Browse page has "Has back" filter. Cards with backs show badge.

Commit: `feat(photos): PRD-029 — complete photo backs & media groups`

---

## Act 5 (Track E): Postgres Read Flip + GlobalPersonID Schema

**Worktree**: `session-91/postgres-reads`
**PRD**: `docs/prds/027_data_migration.md` (Phases B/C)
**Key files to read**: `core/registry.py`, `core/photo_registry.py`, `app/supabase_data.py`, `scripts/sql/` (existing schemas)
**Goal**: IdentityRegistry and PhotoRegistry read from Supabase instead of JSON. Add GlobalPersonID schema.

### 5a. Verify Supabase Tables Exist

Run the backfill script if not already run. Verify record counts match JSON:
- `photos` table: should have ~296 rows
- `identities` table: should have ~777 rows
- `photo_faces` table: should have ~982 rows

If tables don't exist yet, create them:

```sql
CREATE TABLE IF NOT EXISTS photos (
    photo_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    source TEXT,
    collection TEXT,
    source_url TEXT,
    upload_date TIMESTAMPTZ,
    width INTEGER,
    height INTEGER,
    face_count INTEGER,
    uploaded_by TEXT,
    community_id UUID,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS identities (
    identity_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT,
    state TEXT NOT NULL DEFAULT 'INBOX',
    anchor_ids JSONB DEFAULT '[]',
    candidate_ids JSONB DEFAULT '[]',
    negative_ids JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    version_id INTEGER DEFAULT 1,
    merged_into UUID,
    community_id UUID,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS photo_faces (
    face_id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL REFERENCES photos(photo_id),
    identity_id UUID REFERENCES identities(identity_id),
    bbox JSONB,
    det_score NUMERIC(6,4),
    quality NUMERIC(6,4),
    embedding float4[],
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS date_labels (
    photo_id TEXT PRIMARY KEY REFERENCES photos(photo_id),
    estimated_decade TEXT,
    best_year_estimate INTEGER,
    confidence TEXT,
    model_used TEXT,
    labeled_by TEXT,
    raw_response JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS photo_locations (
    photo_id TEXT PRIMARY KEY REFERENCES photos(photo_id),
    lat NUMERIC(10,7),
    lng NUMERIC(10,7),
    location_name TEXT,
    location_estimate TEXT,
    confidence TEXT,
    geocoded_from TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### 5b. Feature Flag: DATA_SOURCE

Add `DATA_SOURCE` env var (`json` or `postgres`, default `json`):
- When `json`: existing behavior (read from JSON files, shadow write to Supabase)
- When `postgres`: read from Supabase, write to Supabase only

### 5c. IdentityRegistry Postgres Adapter

In `core/registry.py`:
1. New classmethod `load_from_postgres(cls)`:
   - Queries `identities` table
   - Constructs same in-memory dict structure as JSON load
   - Falls back to JSON if Supabase unavailable
2. Wire into `load()`: if `DATA_SOURCE=postgres`, use Postgres path

### 5d. PhotoRegistry Postgres Adapter

In `core/photo_registry.py`:
1. New classmethod `load_from_postgres(cls)`:
   - Queries `photos` + `photo_faces` tables
   - Reconstructs `_photos` dict and `_face_to_photo` mapping
2. Wire into `load()`: if `DATA_SOURCE=postgres`, use Postgres path

### 5e. Date Labels + Photo Locations from Postgres

- Read from `date_labels` and `photo_locations` Supabase tables when `DATA_SOURCE=postgres`
- Replace JSON file reads in `app/estimate_routes.py`

### 5f. Write Path Update

When `DATA_SOURCE=postgres`:
- `save_registry()` writes ONLY to Supabase (not JSON)
- `save_photo_registry()` writes ONLY to Supabase
- JSON files become export-only artifacts

### 5g. Embeddings

Keep reading `embeddings.npy` from disk for now (pgvector migration is future work). Add TODO comment.

### 5h. GlobalPersonID Schema

Create `scripts/sql/create_communities.sql`:
```sql
CREATE TABLE IF NOT EXISTS communities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    admin_emails TEXT[],
    r2_prefix TEXT NOT NULL,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

Create `scripts/sql/create_global_person_links.sql`:
```sql
CREATE TABLE IF NOT EXISTS global_person_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    global_person_id UUID NOT NULL,
    community_id UUID NOT NULL REFERENCES communities(id),
    identity_id UUID NOT NULL,
    link_type TEXT NOT NULL,  -- 'gedcom', 'ml_proposal', 'human_confirmed'
    confidence NUMERIC(5,4),
    linked_by TEXT,
    evidence JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(community_id, identity_id)
);

CREATE INDEX IF NOT EXISTS idx_gpl_global ON global_person_links(global_person_id);
CREATE INDEX IF NOT EXISTS idx_gpl_identity ON global_person_links(identity_id);
CREATE INDEX IF NOT EXISTS idx_gpl_community ON global_person_links(community_id);
```

### 5i. Seed Rhodes Community + Backfill community_id

```sql
INSERT INTO communities (slug, name, description, admin_emails, r2_prefix)
VALUES ('rhodes', 'Jewish Community of Rhodes',
        'Heritage photo archive for the Sephardic Jewish community of Rhodes',
        ARRAY['NolanFox@gmail.com'], 'raw_photos/')
ON CONFLICT (slug) DO NOTHING;

-- Backfill community_id on existing tables
ALTER TABLE identities ADD COLUMN IF NOT EXISTS community_id UUID REFERENCES communities(id);
ALTER TABLE photos ADD COLUMN IF NOT EXISTS community_id UUID REFERENCES communities(id);

UPDATE identities SET community_id = (SELECT id FROM communities WHERE slug = 'rhodes') WHERE community_id IS NULL;
UPDATE photos SET community_id = (SELECT id FROM communities WHERE slug = 'rhodes') WHERE community_id IS NULL;
```

### 5j. Critical Invariants to Preserve

- `neighbors.py` is FROZEN — must still receive same embedding data format
- Co-occurrence validation still works (face_to_photo mapping)
- Optimistic concurrency (version_id) still works
- All admin actions (confirm, merge, rename, detach, reject) still work

### 5k. Tests

- `load_from_postgres()` returns same structure as `load()` from JSON
- `save_registry()` with `DATA_SOURCE=postgres` writes to Supabase
- All existing tests pass with `DATA_SOURCE=json` (default — zero regression)
- Integration test: round-trip identity through Postgres
- SQL scripts run without error
- Backfill populates community_id
- GlobalPersonID schema exists (empty, ready)

**Acceptance**: With `DATA_SOURCE=postgres` on Railway, app loads identities + photos from Supabase. With `DATA_SOURCE=json`, everything works as before. Communities table exists with Rhodes seeded. All existing identities + photos have `community_id` set.

Commit: `feat(data): PRD-027 Phases B/C — Postgres read flip + GlobalPersonID schema`

---

## Act 6 (Track F): Observability + Documentation Updates

**Worktree**: `session-91/observability-docs`
**Key files to read**: `requirements.txt`, `app/main.py` (startup), context file research sections
**Goal**: Add Sentry, PostHog, structlog. Update all architecture and planning docs.

### 6a. Sentry (Error Tracking)

1. Add `sentry-sdk` to `requirements.txt`
2. In app startup:
   ```python
   import sentry_sdk

   if os.environ.get("SENTRY_DSN"):
       sentry_sdk.init(
           dsn=os.environ["SENTRY_DSN"],
           environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
           traces_sample_rate=0.1,
           send_default_pii=False,  # Heritage app — faces are PII
       )
   ```
3. Do NOT wrap in SentryAsgiMiddleware yet (test FastHTML ASGI compatibility first)
4. `SENTRY_DSN` set on Railway by user

### 6b. PostHog (Analytics)

1. Add PostHog JS snippet to the base HTML `<head>` (in main.py):
   ```python
   def _posthog_script():
       key = os.environ.get("POSTHOG_API_KEY", "")
       if not key:
           return ""
       return Script("""...""")  # Standard PostHog snippet with respect_dnt
   ```
2. Gated on `POSTHOG_API_KEY` env var — absent = no analytics
3. Do NOT add `posthog-python` yet — client-side JS is sufficient

### 6c. Structured Logging

1. Add `structlog` to `requirements.txt`
2. Configure in app startup:
   ```python
   import structlog

   structlog.configure(
       processors=[
           structlog.contextvars.merge_contextvars,
           structlog.processors.add_log_level,
           structlog.processors.TimeStamper(fmt="iso"),
           structlog.dev.ConsoleRenderer()
       ],
       wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
   )
   ```
3. Do NOT convert existing `logging.getLogger()` calls — just configure alongside stdlib
4. Use structlog for NEW code going forward

### 6d. Documentation Updates

1. **ROADMAP.md**:
   - Add strategic items: GlobalPersonID, ML service extraction, second collection, standalone tooling, chatbot
   - Update Phase F status
   - Add Session 91 to "Recently Completed" (after session ends)

2. **BACKLOG.md** — Add new items:
   - `PLATFORM-001`: GlobalPersonID schema
   - `PLATFORM-002`: ML service extraction (standalone FastAPI)
   - `PLATFORM-003`: Second collection onboarding (Fox family photos)
   - `PLATFORM-004`: Standalone Gemini tooling product
   - `OPS-005`: Sentry error tracking
   - `OPS-006`: PostHog analytics
   - `OPS-007`: Structured logging (structlog)
   - Update `DATA-007` status based on migration progress
   - Update `GEN-001` with concrete architecture from context file

3. **Architecture docs**:
   - `docs/architecture/OVERVIEW.md` — update data layer for Postgres migration
   - `docs/architecture/DATA_MODEL.md` — add Supabase table schemas, note JSON deprecated
   - Create `docs/architecture/MULTI_TENANT.md` — GlobalPersonID design, community schema, R2 organization

4. **ALGORITHMIC_DECISIONS.md** — New entries:
   - AD-206: GlobalPersonID schema design (3 linking mechanisms)
   - AD-207: Postgres as source of truth (DATA_SOURCE feature flag)
   - AD-208: Observability stack (Sentry + PostHog + structlog)

5. **`docs/roadmap/FEATURE_STATUS.md`** — Phase F checkboxes

6. **`docs/roadmap/SESSION_HISTORY.md`** — Session 91 entry

7. **Write `docs/prds/030_multi_collection.md`**:
   - Problem: Single-community architecture limits growth
   - Solution: Community-scoped data + GlobalPersonID for cross-linking
   - Schema from context file
   - Migration plan
   - Out of scope: RLS policies, ML service extraction, UX changes

### 6e. Tests

- Sentry init doesn't crash when DSN not set
- PostHog snippet renders when key set, absent when not
- structlog configures without errors

**Acceptance**: `sentry-sdk` and `structlog` in requirements.txt. Sentry gated on env var. PostHog gated on env var. All docs updated with breadcrumbs. New BACKLOG items have IDs. Architecture docs reflect Postgres migration + multi-tenant schema.

Commit: `feat(ops): Sentry + PostHog + structlog + architecture docs update`

---

## Act 7: Merge + Deploy + Browser Verify + Assessment (30 min)

### 7a. Merge All Tracks

1. Check all subagent branches for completion
2. **Merge order**: B (scripts) -> C (events) -> D (photo-backs) -> F (observability+docs) -> A (notifications) -> E (postgres-reads)
3. Use: `./scripts/merge.sh session-91/r2-backup session-91/life-events session-91/photo-backs session-91/observability-docs session-91/notifications session-91/postgres-reads`
4. Run `make test-fast` after each merge
5. Resolve any conflicts

### 7b. Deploy + Railway Env Vars

1. Document what needs to be set manually on Railway:
   - `DATA_SOURCE=json` initially (flip to `postgres` after verification)
   - `SENTRY_DSN` (user creates Sentry project)
   - `POSTHOG_API_KEY` (user creates PostHog project)
2. `git push origin main` to deploy
3. Wait for deploy completion (Lesson 94 — do NOT verify during deploy)

### 7c. Browser Verification (Claude Chrome)

**ALL must be verified with Claude Chrome. No exceptions.**

1. **Notifications**: Bell icon visible when logged in, click opens /notifications
2. **Photo backs**: David Franco photo flip shows Front/Back label, browse has "Has back" filter
3. **Life events**: /events page loads, can create an event (admin)
4. **General**: Landing page, person page, compare page still work (regression)
5. **Postgres** (if time): Flip `DATA_SOURCE=postgres` on Railway, verify app loads correctly, flip back if issues

Save screenshots to `docs/screenshots/session-91/`

### 7d. Manual Postgres Flip Test (if time permits)

1. Set `DATA_SOURCE=postgres` on Railway
2. Verify app loads identities + photos from Supabase
3. Verify admin actions work (confirm an identity, check Supabase)
4. If any issues, flip back to `DATA_SOURCE=json`

### 7e. Assessment + Docs

Standard mandatory outputs:
1. Write `docs/assessments/session-91-assessment.md`
2. Update `docs/session_logs/session-91-log.md`
3. Update `CHANGELOG.md` — v0.94.0
4. Update `ROADMAP.md`:
   - Mark all completed items as done with dates
   - Move completed items to "Recently Completed"
5. Update `docs/BACKLOG.md` — update relevant items' status
6. Update `docs/roadmap/SESSION_HISTORY.md` — session 91 entry
7. Update PRD status fields to SHIPPED (for shipped PRDs)
8. Verify all breadcrumbs from Track F docs

---

## Acceptance Criteria

### Must Ship
- [ ] PRD-028: Notifications table + /notifications page + bell icon + identity confirmation trigger
- [ ] PRD-027 Phase A: R2 backup script with --dry-run + restore script with --list
- [ ] PRD-011: Life events table + CRUD routes + photo/person page integration
- [ ] PRD-029: Media group endpoint + Front/Back label + browse "Has back" filter + card badges
- [ ] PRD-027 Phases B/C: `DATA_SOURCE` feature flag works (`json` default, `postgres` reads from Supabase)
- [ ] IdentityRegistry + PhotoRegistry load from Postgres when `DATA_SOURCE=postgres`
- [ ] `communities` table exists with Rhodes community seeded
- [ ] `global_person_links` table exists (empty, schema ready)
- [ ] All existing identities + photos have `community_id` set
- [ ] `sentry-sdk` + `structlog` in requirements.txt, gated on env vars
- [ ] PostHog JS snippet gated on `POSTHOG_API_KEY` env var
- [ ] PRD-030 (Multi-Collection Architecture) written
- [ ] ROADMAP + BACKLOG + architecture docs updated with strategic items
- [ ] All tests pass (`make test-fast`)
- [ ] Browser verified via Claude Chrome with screenshots
- [ ] Assessment + session log + CHANGELOG + ROADMAP updated

### Should Ship
- [ ] PRD-028: Auto-clustering match trigger creates notification
- [ ] PRD-011: Timeline integration with event markers
- [ ] PRD-011: Seed data from rhodes_context_events.json
- [ ] PRD-029: Supabase columns for media group
- [ ] Date labels + photo locations read from Supabase when `DATA_SOURCE=postgres`
- [ ] AD entries for GlobalPersonID, Postgres migration, observability stack
- [ ] Architecture docs (OVERVIEW, DATA_MODEL updated; new MULTI_TENANT.md)

### Deferred (Session 92+)
- [ ] Embeddings migration to pgvector (keep as .npy for now)
- [ ] ML service extraction (separate FastAPI service)
- [ ] Second collection onboarding (Fox family photos)
- [ ] Postgres RLS policies (not needed until second community)
- [ ] Chatbot research interface
- [ ] Standalone tooling product
- [ ] `SentryAsgiMiddleware` (test FastHTML ASGI compatibility first)
- [ ] PRD-028 P1: Email notifications via Resend (needs RESEND_API_KEY)
- [ ] PRD-028 P2-P3: Digest emails, notification preferences page
- [ ] PRD-011: Community event submission (non-admin)

## Key Skills to Use

- `/simplify` — after implementation acts
- `/session-review` — at session end (mandatory)
- Claude Chrome — for ALL frontend verification
- Worktree subagents — for parallel tracks (6 tracks)

## Non-Goals

- Full multi-tenant runtime (just schema + seed)
- Removing JSON files from repo (keep as fallback)
- ML pipeline changes or running ML on photos
- Email notifications (PRD-028 P1+)
- UX redesign beyond what PRDs specify

## Risk Mitigation

**Biggest risk**: 6 parallel tracks is ambitious.
**Mitigation**: Each track is self-contained with minimal file overlap. Clear merge order. If a track is incomplete, merge what's done and BACKLOG the rest.

**Second risk**: Postgres read path serves stale or empty data.
**Mitigation**: `DATA_SOURCE` feature flag defaults to `json`. Only flip to `postgres` after manual verification. Can flip back instantly.

**Third risk**: PRD-011 scope is underspecified (stub PRD).
**Mitigation**: Track C starts by fleshing out PRD. If scope is larger than expected, ship data model + CRUD only, defer UI integration.

**Fourth risk**: main.py merge conflicts from multiple tracks touching it.
**Mitigation**: Only Track A (bell icon) and Track F (middleware) touch main.py. Merge F before A. Track E touches core/ not main.py.
