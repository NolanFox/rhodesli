# Session 91: Ship the PRD Backlog — Notifications + Data Safety + Life Events + Photo Backs

**Context**: `docs/session_context/session-91-context.md`
**Predecessor**: Session 90c (Gemini prompt fix, face alignment timestamp, flaky test cleanup)

## Problem Statement

We have 4 PRDs that were written but never fully implemented. This session ships all of them. The growth loop is broken because contributors get no feedback (PRD-028). Core data has no backup (PRD-027). Life events aren't captured (PRD-011). Photo backs are half-built (PRD-029). Fix all of it.

**PRDs to ship:**
1. **PRD-028**: Contributor Notifications (P0 — in-app center + event triggers)
2. **PRD-027**: Data Safety — R2 nightly backup (Phase A)
3. **PRD-011**: Life Events & Context Graph (event model + tagging + timeline integration)
4. **PRD-029**: Photo Back & Media Groups (complete remaining work)

## Session Protocol
- Set `.claude/current_session.txt` to `91`
- Read `tasks/lessons.md` and `tasks/todo.md` at start
- Commit after every act, `/clear` between acts
- Use Claude Chrome for ALL frontend verification
- Run `/session-review` at session end
- Screenshots to `docs/screenshots/session-91/`

---

## Dependencies on Prior Sessions

Session 90b shipped shadow writes (`save_registry()` and `save_photo_registry()` fire-and-forget to Supabase). Session 90c shipped Gemini prompt improvements. This session builds on both.

**Verify before starting:**
- [ ] Shadow writes work (check `app/supabase_data.py` has `shadow_write_identity` and `shadow_write_photo`)
- [ ] Back image upload route exists (`POST /api/photo/{photo_id}/back-image` in `app/photo_routes.py`)
- [ ] Timeline route exists (`/timeline` — from timeline-story-engine PRD, Session 30+)

---

## Parallelization Plan

**Phase 1** (Act 0): Sequential on main — orient, verify state
**Phase 2** (Acts 1-4): Parallel worktree subagents:
- **Track A**: PRD-028 — Notifications (worktree: `session-91/notifications`)
- **Track B**: PRD-027 Phase A — R2 Backup (worktree: `session-91/r2-backup`)
- **Track C**: PRD-011 — Life Events (worktree: `session-91/life-events`)
- **Track D**: PRD-029 — Photo Backs Completion (worktree: `session-91/photo-backs`)
**Phase 3** (Act 5): Merge all tracks, browser verify, assessment

**File conflict analysis**:
- Track A touches: new Supabase tables, new `app/notification_routes.py`, header in `app/main.py` (bell icon)
- Track B touches: new `scripts/backup_to_r2.py`, new `scripts/restore_from_r2.py` — fully independent
- Track C touches: new Supabase tables, new `app/event_routes.py`, timeline UI modifications
- Track D touches: `app/photo_routes.py`, `app/browse_routes.py`, Supabase photo table columns
- **Merge order**: B first (scripts only), then D (photo routes), then C (events), then A (notifications + header)
- **Conflict risk**: LOW — each track touches different files. Only risk is `app/main.py` header (Track A) vs timeline nav (Track C). Merge A last.

---

## Act 0: Orient (5 min)

1. Read this prompt, context file, `tasks/lessons.md`
2. `git log --oneline -5`, `git status`, verify tests pass
3. Set `.claude/current_session.txt` to `91`
4. Create `docs/session_logs/session-91-log.md` with phase checklist
5. Verify dependencies listed above
6. Check timeline route exists — if not, note for Track C

---

## Act 1 (Track A): PRD-028 — Contributor Notifications P0

**Worktree**: `session-91/notifications`
**PRD**: `docs/prds/028_contributor_notifications.md`
**Goal**: In-app notification center with event triggers for identity confirmation and auto-clustering matches.

### 1a. Supabase Tables

Create via SQL (run in Supabase dashboard or migration script):

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

1. `GET /notifications` — Page with chronological list of notifications for logged-in user
   - HTMX-powered, paginated (20 per page)
   - Unread items highlighted
   - Each item: icon (by type), title, body preview, timestamp, link to photo/person
   - "Mark all as read" button
2. `POST /api/notifications/{id}/read` — Mark single notification as read
3. `POST /api/notifications/mark-all-read` — Mark all as read
4. `GET /api/notifications/count` — Returns unread count (for bell icon polling)

### 1c. Bell Icon in Header

Add to the site header (in `app/main.py` or wherever the nav is built):
- Bell icon visible to all logged-in users
- Red badge with unread count (hidden when 0)
- Use `hx-get="/api/notifications/count" hx-trigger="every 30s"` for polling
- Click navigates to `/notifications`

### 1d. Event Triggers

Hook into existing flows to create notifications:

1. **Identity confirmation** — In `save_registry()` path, when state changes to CONFIRMED:
   - Find the photo(s) containing that identity's faces
   - Find the uploader of those photos (if `uploaded_by` exists in photo metadata)
   - Create notification: "Isaac Cohen identified in your photo"
2. **Auto-clustering match** — In auto-clustering pipeline, when Tier 1 match auto-added:
   - Create notification for photo uploader: "New face match found in your photo"
3. **Manual creation** — Admin endpoint `POST /api/notifications/create` for testing

### 1e. Photo Uploader Tracking

If `uploaded_by` field doesn't exist in photo metadata:
- Add it to photo upload flow (store current user's email/ID when uploading)
- Backfill: set existing Benatar photos to `uploaded_by: "claude.benatar@..."` if known

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

- Test backup script generates correct R2 keys
- Test restore script lists backups correctly
- Test pruning logic (keep 30 days)
- Test dry-run doesn't upload

**Acceptance**: `python scripts/backup_to_r2.py --dry-run` shows correct files and R2 paths. Restore script lists available backups.

Commit: `feat(ops): PRD-027 Phase A — R2 nightly backup for critical data files`

---

## Act 3 (Track C): PRD-011 — Life Events & Context Graph

**Worktree**: `session-91/life-events`
**PRD**: `docs/prds/011_life_events_context_graph.md`
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

Import key Rhodes community events from `data/rhodes_context_events.json` into the life_events table. These are historical context events (deportation, immigration waves, etc.) that already exist as JSON.

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
**Goal**: Complete the remaining work from PRD-029 that wasn't finished in Session 90b.

### What's already built (Session 90b):
- `POST /api/photo/{photo_id}/back-image` — Upload back image (saves to raw_photos + R2)
- `POST /api/photo/{photo_id}/back-transcription` — Update transcription
- 3D flip CSS animation with `rotateY(180deg)`
- Photo metadata update with `back_image`, `media_group_id`, `related_media` fields
- Tests in `test_back_image.py` and `test_photo_flip.py`

### What's remaining:

### 4a. Supabase Photo Table Columns

Add media group columns to the photos Supabase table (if exists) or photo_index.json:
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

## Act 5: Merge + Browser Verify + Assessment (20 min)

### 5a. Merge All Tracks

1. Check all subagent branches for completion
2. **Merge order**: B (scripts), D (photo routes), C (events), A (notifications + header)
3. Use `./scripts/merge.sh session-91/r2-backup session-91/photo-backs session-91/life-events session-91/notifications`
4. Run `make test-fast` after each merge
5. Resolve any conflicts

### 5b. Browser Verification (Claude Chrome)

ALL must be verified with Claude Chrome:
1. **Notifications**: Bell icon visible when logged in, click opens /notifications
2. **Photo backs**: David Franco photo flip shows Front/Back label, browse has "Has back" filter
3. **Life events**: /events page loads, can create an event (admin)
4. **General**: Landing page, person page, compare page still work (regression)

Save screenshots to `docs/screenshots/session-91/`

### 5c. Assessment + Docs

Standard mandatory outputs:
1. Write `docs/assessments/session-91-assessment.md`
2. Update `docs/session_logs/session-91-log.md`
3. Update `CHANGELOG.md` — v0.94.0
4. Update `ROADMAP.md`:
   - Mark PRD-028 P0 as done
   - Mark PRD-027 Phase A as done
   - Mark PRD-011 as done
   - Mark PRD-029 as done
5. Update `docs/BACKLOG.md` — update relevant items
6. Update `docs/roadmap/SESSION_HISTORY.md` — session 91 entry
7. Update PRD status fields to SHIPPED

---

## Acceptance Criteria

### Must Ship
- [ ] PRD-028: Notifications table + /notifications page + bell icon + identity confirmation trigger
- [ ] PRD-027: R2 backup script with --dry-run + restore script with --list
- [ ] PRD-011: Life events table + CRUD routes + photo/person page integration
- [ ] PRD-029: Media group endpoint + Front/Back label + browse "Has back" filter + card badges
- [ ] All tests pass (`make test-fast`)
- [ ] Browser verified via Claude Chrome with screenshots
- [ ] Assessment + session log + CHANGELOG + ROADMAP updated
- [ ] All 4 PRD status fields updated to SHIPPED

### Should Ship
- [ ] PRD-028: Auto-clustering match trigger creates notification
- [ ] PRD-011: Timeline integration with event markers
- [ ] PRD-011: Seed data from rhodes_context_events.json
- [ ] PRD-029: Supabase columns for media group

### Deferred (Session 92+)
- [ ] PRD-028 P1: Email notifications via Resend (needs RESEND_API_KEY)
- [ ] PRD-028 P2-P3: Digest emails, notification preferences page
- [ ] PRD-027 Phase B: Shadow writes completion + Postgres read flip
- [ ] PRD-027 Phase C: Full Postgres migration (triggered)
- [ ] PRD-011: Community event submission (non-admin)
- [ ] GlobalPersonID schema (from original session 91 plan — moved to session 92)
- [ ] Sentry + PostHog + structlog (from original session 91 plan — moved to session 92)

## Key Skills to Use

- `/simplify` — after implementation acts
- `/session-review` — at session end (mandatory)
- Claude Chrome — for ALL frontend verification
- Worktree subagents — for parallel tracks

## Non-Goals

- Full Postgres migration (PRD-027 Phases B/C)
- Email notifications (PRD-028 P1+)
- GlobalPersonID / multi-tenant schema (deferred to session 92)
- Sentry / PostHog / observability (deferred to session 92)
- ML pipeline changes

## Risk Mitigation

**Biggest risk**: 4 parallel tracks is ambitious. Each track is self-contained with minimal file overlap.
**Mitigation**: Each track has clear acceptance criteria. If a track is incomplete, it can be merged partially and the remainder goes to BACKLOG with a specific TODO.

**Second risk**: PRD-011 is the least defined (currently a stub).
**Mitigation**: Track C starts by fleshing out the PRD before implementation. If the scope is larger than expected, ship the data model + CRUD only, defer UI integration.
