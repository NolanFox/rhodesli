# Session 91b: Finish What 91 Didn't + Fix Collection Name Overindexing

**Context**: `docs/session_context/session-91b-context.md`
**Predecessor**: Session 91 (claimed 6 tracks shipped; audit found tables never created, triggers never wired, location prompt overindexes)

## Problem Statement

Session 91 wrote code and SQL files but never executed the SQL against Supabase, never wired notification triggers, and introduced a location estimation regression (AD-204 overindexes to collection name). This session finishes the job.

## Session Protocol
- Set `.claude/current_session.txt` to `91b`
- Read `tasks/lessons.md` at start
- Commit after every act, `/clear` between acts
- Use Claude Chrome for ALL frontend verification
- Run `/session-review` at session end

---

## Act 0: Orient (5 min)

1. Read this prompt and context file
2. `git status`, `git log --oneline -5`, verify `make test-fast` passes
3. Set `.claude/current_session.txt` to `91b`
4. Create session log

Commit: `chore: session 91b orient`

**IMMEDIATELY /clear after this commit.**

---

## Act 1: Execute Supabase Migrations (15 min)

Use the Supabase MCP, CLI, or direct SQL execution to create all missing tables. The SQL files already exist — they just need to be run.

### 1a. Check What Tables Already Exist
Query Supabase to see which tables from Session 91 actually exist:
- `photos`, `identities`, `photo_faces` (from earlier sessions — likely exist)
- `date_labels`, `photo_locations` (from earlier sessions — likely exist)
- `gemini_api_calls`, `face_gemini_alignments` (from earlier sessions — likely exist)
- `communities`, `global_person_links` (Session 91 — likely DON'T exist)
- `life_events`, `event_participants`, `event_photos` (Session 91 — likely DON'T exist)
- `notifications`, `notification_preferences` (Session 91 — likely DON'T exist)

### 1b. Execute Missing Table SQL (in order)
1. `scripts/sql/create_communities.sql`
2. `scripts/sql/seed_rhodes_community.sql`
3. `scripts/sql/create_global_person_links.sql`
4. `scripts/sql/create_life_events.sql`
5. `scripts/sql/007_notifications.sql`
6. `scripts/sql/alter_photos_media_group.sql` (ALTER TABLE on photos)

For any table that already exists, skip it (all SQL uses `IF NOT EXISTS`).

### 1c. Verify
After execution, query each new table to confirm it exists:
```sql
SELECT count(*) FROM communities;
SELECT count(*) FROM life_events;
SELECT count(*) FROM notifications;
SELECT count(*) FROM global_person_links;
```

### 1d. Run Seed Scripts
```bash
python scripts/seed_life_events.py
```
Verify: `SELECT count(*) FROM life_events;` should return > 0.

Commit: `feat(data): execute Supabase migrations — communities, life_events, notifications, global_person_links`

**IMMEDIATELY /clear after this commit.**

---

## Act 2: Wire Notification Triggers (20 min)

### 2a. Wire into save_registry()

In `app/main.py`, find `save_registry()`. When an identity's state changes to `CONFIRMED`, call `create_identity_confirmed_notification()` from `app/notification_routes.py`.

Logic:
1. Before saving, check if the identity's previous state was != CONFIRMED and new state == CONFIRMED
2. If so, gather the identity's face IDs, look up which photos contain those faces
3. Call `create_identity_confirmed_notification(identity_id, identity_name, photo_ids)`

### 2b. Fix Placeholder User ID

In `notification_routes.py`, `create_identity_confirmed_notification()` uses a placeholder `"00000000-0000-0000-0000-000000000000"` user_id. Fix this:
- Check if photos have an `uploaded_by` field → notify that user
- If no uploaded_by, notify the admin (the person who confirmed it) — use the current session user
- The user_id should come from Supabase Auth (the `id` field on the `User` object in `app/auth.py`)

### 2c. Tests

Add tests that verify:
- Confirming an identity calls `create_identity_confirmed_notification()`
- The notification has the correct identity_id, title, and photo_ids
- Non-CONFIRMED state changes do NOT create notifications

### 2d. Browser Verify

Using Claude Chrome:
1. Navigate to the admin panel
2. Confirm an identity (change state to CONFIRMED)
3. Check that the bell icon badge updates
4. Click bell → /notifications → verify the notification appears

Commit: `feat(notifications): wire identity confirmation trigger into save_registry()`

**IMMEDIATELY /clear after this commit.**

---

## Act 3: Fix Collection Name Overindexing — AD-209 (30 min)

This is the most important act. The current prompt in `rhodesli_ml/gemini_extraction.py` lines 268-275 says:

```
IMPORTANT: The collection name often indicates the geographic origin of photos.
For example, "Tampa Collection" strongly suggests photos were taken in or near Tampa.
Use this as corroborating evidence alongside visual and biographical analysis.
```

This is wrong. Collection name indicates where photos were FOUND/STORED (provenance), not where they were taken.

### 3a. Fix the Prompt

Replace the Photo Metadata Context section (lines 257-276 of `rhodesli_ml/gemini_extraction.py`) with:

```python
if photo_metadata:
    meta_section = "## Photo Metadata Context\n"
    if photo_metadata.get("collection"):
        meta_section += f"Collection: {photo_metadata['collection']}\n"
    if photo_metadata.get("source"):
        meta_section += f"Source: {photo_metadata['source']}\n"
    if photo_metadata.get("filename"):
        meta_section += f"Original filename: {photo_metadata['filename']}\n"
    if photo_metadata.get("visible_text"):
        meta_section += f"Previously extracted text: {photo_metadata['visible_text']}\n"
    meta_section += (
        "\nNOTE ON COLLECTION NAMES: A collection name indicates WHO HAD these photos "
        "and WHERE THEY WERE STORED, not necessarily where the photos were taken. "
        "For example, a 'Tampa Collection' means the photos were found in Tampa — "
        "but the photos themselves may depict locations the family visited or lived in "
        "before moving to Tampa (e.g., Asheville, New York, Rhodes).\n"
        "Collection name is WEAK contextual evidence about the collector's later residence. "
        "Visual evidence (signage, architecture) and GEDCOM residence data at the time of "
        "the photo are MUCH STRONGER signals for actual photo location.\n"
        "Do NOT assume the collection city is the photo location."
    )
    sections.append(meta_section)
```

### 3b. Eval Framework

Create `rhodesli_ml/tests/test_collection_location_bias.py` with:

**Test 1 — Prompt content check**: Verify the prompt does NOT contain "strongly suggests photos were taken" or "geographic origin of photos".

**Test 2 — Prompt content check**: Verify the prompt DOES contain "WHO HAD these photos" and "WEAK contextual evidence".

**Test 3 — Leon's Restaurant eval** (requires Gemini API key, mark with `@pytest.mark.gemini`):
- Build prompt with: collection="Nace Capeluto Tampa Collection", GEDCOM showing Leon Capeluto residence in Asheville 1928-1940, visible text "LEON'S RESTAURANT"
- Send to Gemini with the Leon's Restaurant photo
- Assert location result contains "Asheville" (not "Tampa")
- This is the canonical regression test for collection name overindexing

**Test 4 — No over-correction**:
- Build a prompt for a photo that IS in Tampa (e.g., collection="Tampa Collection", GEDCOM shows person living in Tampa at the time, visual evidence consistent with Tampa)
- Verify Gemini still returns Tampa
- This prevents the fix from swinging too far the other way

**Test 5 — Collection absent**: Verify that when photo_metadata is None or has no collection, the metadata section is not added to the prompt (existing test, just verify it still passes).

### 3c. Re-analyze Leon's Restaurant Photo

After fixing the prompt, re-analyze photo 3192877a90a174e9 using the admin re-analyze button in Claude Chrome:
1. Navigate to https://rhodesli.nolanandrewfox.com/photo/3192877a90a174e9
2. Click "Re-analyze" (admin button)
3. Verify the location now says Asheville, NC (not Tampa)
4. Take screenshot as evidence

### 3d. Write AD-209

Add to `docs/ml/ALGORITHMIC_DECISIONS.md`:
```
## AD-209: Collection Name as Weak Provenance, Not Location Signal

**Date**: 2026-03-07
**Session**: 91b
**Supersedes**: Part of AD-204 (collection metadata section)

**Problem**: AD-204 introduced collection name as a strong location signal ("Tampa Collection strongly suggests photos were taken in or near Tampa"). This is incorrect — collection name indicates where photos were stored, not where they were taken. Leon's Restaurant photo (3192877a90a174e9) in "Nace Capeluto Tampa Collection" was incorrectly estimated as Tampa when it should be Asheville, NC (where Leon Capeluto lived and ran his restaurant 1928-1940).

**Decision**: Rewrite collection metadata prompt to explicitly state collection name is WEAK provenance context about the collector, not the photo location. Visual evidence and GEDCOM residence data at the time of the photo are stronger signals.

**Evidence**: GEDCOM shows Leon Capeluto residence at 33 Elizabeth St, Asheville, NC (1928-1940). Family moved to Tampa after 1940. Collection named after Nace Capeluto who grew up in Asheville but lived in Tampa as an adult.

**Eval**: Canonical test — Leon's Restaurant photo must return Asheville. Regression test — Tampa photos must still return Tampa.
```

Commit: `fix(ml): AD-209 — collection name is weak provenance, not location signal`

**IMMEDIATELY /clear after this commit.**

---

## Act 4: Browser Verification + Remaining Cleanup (20 min)

### 4a. Browser Verify All Session 91 Features

Using Claude Chrome, verify each feature end-to-end (not just "page loads"):

1. **Notifications**:
   - Bell icon visible when logged in
   - Create a test notification via `POST /api/notifications/create`
   - Bell badge shows unread count
   - /notifications page shows the notification
   - "Mark as read" works, badge updates

2. **Life Events**:
   - /events page shows seeded events (not empty)
   - "Create New Event" form works (admin)
   - Event detail page shows linked info

3. **Photo Backs**:
   - David Franco photo flip works (Front/Back labels)
   - Browse page "Has back" filter works

4. **General regression**: Landing page, person page, compare page still work

Save screenshots to `docs/screenshots/session-91b/`

### 4b. Write AD-206, AD-207, AD-208

These were promised in Session 91 but never written:

**AD-206**: GlobalPersonID schema design — communities table, global_person_links with 3 linking mechanisms (gedcom, ml_proposal, human_confirmed), community_id on identities and photos.

**AD-207**: Postgres as source of truth — DATA_SOURCE feature flag, load_from_postgres() on IdentityRegistry and PhotoRegistry, JSON files become fallback/export-only.

**AD-208**: Observability stack — Sentry (error tracking, env-gated), PostHog (client-side JS analytics, env-gated), structlog (structured logging alongside stdlib).

### 4c. Update tasks/todo.md

The current todo.md is from Session 50 (very stale). Update it to reflect current state.

Commit: `docs: session 91b browser verification + AD-206/207/208/209`

**IMMEDIATELY /clear after this commit.**

---

## Act 5: Assessment + Session Close

Standard mandatory outputs:
1. Write `docs/assessments/session-91b-assessment.md`
2. Update session log
3. Update CHANGELOG.md (v0.94.1)
4. Update ROADMAP.md — mark completed items
5. Run `/session-review`

---

## Acceptance Criteria

### Must Ship
- [ ] All Session 91 Supabase tables exist and are queryable
- [ ] Life events table seeded with historical events, /events shows them
- [ ] Notification trigger fires when identity is confirmed
- [ ] Bell icon shows actual unread count (not always 0)
- [ ] Collection name prompt rewritten as weak provenance (not strong location signal)
- [ ] Leon's Restaurant photo re-analyzed → returns Asheville, not Tampa
- [ ] Eval tests for collection name bias (prompt checks + Gemini API test)
- [ ] AD-206, AD-207, AD-208, AD-209 written
- [ ] Browser verified with screenshots (end-to-end, not just "page loads")

### Should Ship
- [ ] tasks/todo.md updated to current state
- [ ] Regression test: Tampa photo still returns Tampa after prompt fix

### Deferred (Session 92+)
- [ ] DATA_SOURCE=postgres tested on Railway (flip and verify against real Supabase)
- [ ] SENTRY_DSN + POSTHOG_API_KEY set on Railway (requires user to create accounts)
- [ ] Email notifications (PRD-028 P1+ — needs RESEND_API_KEY)
- [ ] Timeline integration for life events
- [ ] Community event submission (non-admin)

## Key Lesson

"SHIPPED" means the Feature Reality Contract passes — data exists in the database, the app loads it, the route works, the UI renders real data, and a browser test confirms it. Writing SQL files that sit unexecuted in git is not shipping.
