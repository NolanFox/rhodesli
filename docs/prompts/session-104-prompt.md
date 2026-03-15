# Session 104 — Fix Contributor UX + Claude Benatar Photos

**Run with:** `./scripts/run_session.sh docs/prompts/session-104-prompt.md`

Each phase below runs as a SEPARATE `claude -p` invocation with fresh context.
Do NOT try to remember what happened in prior phases — read the checkpoint file instead.

- Context: `docs/session_context/session-104-context.md`
- Current: v0.99.6, ~4357 tests, 941 photos, 1922 active identities, 95 confirmed
- Goal: Fix upload pipeline, fix Compare UX, ingest Robert Mattatia photos, produce shareable link

---

## Phase 0: Orient + Reproduce

1. Set `.claude/current_session.txt` to `104`
2. Read `tasks/lessons.md` (index only)
3. Read `docs/session_context/session-104-context.md`
4. Read `docs/user_feedback/FB-170_claude_benatar_compare_failure.md`
5. Verify deploy: `curl -s https://rhodesli.nolanandrewfox.com/health | head -5`
6. Create `docs/session_logs/session-104-log.md` with phase checklist

**Reproduce Claude Benatar's experience:**

7. Open Chrome browser to `https://rhodesli.nolanandrewfox.com/tools/compare`
   - Document: What does a contributor see? Is it obvious how to upload two photos?
   - Screenshot the page state
8. Check `/admin/pending` — document what's there (2 anonymous, 1 with email per context)
   - Screenshot the pending uploads
9. Try clicking "View photo" on the approved upload — confirm 404
   - Screenshot the 404
10. Document: What SHOULD have happened vs what DID happen

**Commit:** `chore: session 104 orient + reproduce contributor failure`

---

## Phase 1: Diagnose Upload Pipeline

**Goal:** Find root cause of 3 bugs: 404 after approval, anonymous attribution, missing thumbnails.

1. Read `app/upload_routes.py` — trace the upload flow for Compare uploads
2. Read `app/admin_routes.py` — trace the approve flow
3. Read the staging directory and Supabase `staged_uploads` table for the broken uploads
4. Check R2 for the uploaded file — does `inbox_efea638c_0_unknown_1` exist in R2?
5. Check Postgres `photos` and `photo_faces` tables for this photo ID

**For each bug, document:**
- Root cause (which function, which line)
- Why it broke (what changed since it last worked)
- Fix approach

**Key questions:**
- Does Compare Upload use the same pipeline as main Upload? If not, where do they diverge?
- Why is user attribution lost on Compare uploads?
- Why does the approved photo have no backing file?

6. Write diagnosis to session log

**Commit:** `docs: session 104 upload pipeline diagnosis`

---

## Phase 2: Fix Upload Pipeline

**Goal:** All 3 upload bugs fixed with tests.

1. Fix BUG-1: 404 after approval — photo must be registered in Postgres AND have backing file in R2
2. Fix BUG-2: Compare Upload attribution — pass user session to staging pipeline
3. Fix BUG-3: Missing thumbnails — ensure staging thumbnails are generated for all upload sources

4. **Evaluate approval gate removal:**
   - For logged-in contributors (non-admin), should uploads auto-approve?
   - Nolan's preference: yes, since the approval pipeline keeps breaking
   - If implementing auto-approve: add `auto_approved=True` flag, log the decision, keep manual review available for admin

5. Tests:
   - `test_compare_upload_preserves_user_attribution` — verify uploader email is saved
   - `test_approved_photo_has_backing_file` — verify photo page returns 200 after approval
   - `test_staging_thumbnail_generated_for_compare_upload` — verify thumbnail exists
   - `test_contributor_upload_auto_approved` — if implementing auto-approve

**Commit:** `fix(upload): P0 pipeline fixes — 404, attribution, thumbnails (UPLOAD-003)`

---

## Phase 3: Ingest Robert Mattatia Photos + Full ML Analysis

**Goal:** Both photos ingested, all faces detected, compared against entire archive. Broad analysis, not just the two target faces.

1. Copy photos from `~/Downloads/rhodesli_claude_benatar_compare/` to `raw_photos/` with descriptive names:
   - `robert_mattatia_congo_group.jpeg` (1600x1200 — group of men in colonial Africa, Congo/Bukavu)
   - `robert_mattatia_family_group.jpeg` (557x399 — family group photo)

2. Run face detection on BOTH photos:
   ```bash
   source venv/bin/activate
   python -m core.ingest_inbox --file raw_photos/robert_mattatia_congo_group.jpeg \
     --job-id claude-benatar-104 --source "Claude Benatar" --collection "Jews of Rhodes"
   python -m core.ingest_inbox --file raw_photos/robert_mattatia_family_group.jpeg \
     --job-id claude-benatar-104 --source "Claude Benatar" --collection "Jews of Rhodes"
   ```

3. **Broad analysis** — for ALL detected faces in both photos:
   - How many faces in each photo?
   - For each face: top 3 nearest neighbors in the archive with distances
   - Do any faces match CONFIRMED identities? (This is the "context from other people in the photo" signal)
   - Specifically: which face is Robert Mattatia (man with glasses) in each photo? What's the distance between them?

4. Upload new photos + crops to R2

5. Run clustering: `python scripts/cluster_new_faces.py --dry-run`

6. Push to production: `python scripts/push_to_production.py`

7. Verify both photos load on production

8. Save full analysis to `docs/user_feedback/robert_mattatia_analysis_104.md`:
   - Per-face breakdown for both photos
   - Archive matches found
   - Robert Mattatia cross-photo similarity score + interpretation
   - Any other faces that match between the two photos (same event? same family?)

**Commit:** `feat(data): ingest + analyze Robert Mattatia photos from Claude Benatar`

---

## Phase 4: Generate Compare Result + Shareable Link

**Goal:** Produce a single URL that Nolan can send to Claude Benatar showing the face comparison.

1. Identify Robert Mattatia's face in each photo (the man with glasses in one, identify in the other)
2. Use the Compare tool to create a comparison between these two faces
3. Generate a shareable result URL

If the Compare tool doesn't support server-side comparison initiation:
- Use the `/compare/pair` endpoint directly
- Or create the comparison via the admin interface

4. Test the shareable link works for non-logged-in users (Claude Benatar may not be logged in)
5. Record the URL in the session log

**Commit:** `feat: Robert Mattatia face comparison result for Claude Benatar`

---

## Phase 5: Compare UX Audit + Community Scoping Design

**Goal:** Design the contributor workflow and document a community-scoping decision.

### Part A: Walk the contributor path

1. Open Chrome to `/tools/compare`
2. Walk through as a logged-in contributor (Claude Benatar's perspective):
   - Upload photo 1 → Upload photo 2 → See results
   - Are photos auto-saved to archive? (They MUST be — **never lose photos**)
   - Is attribution preserved? (uploader email must be recorded)
   - Is there a shareable link?
3. Screenshot each step
4. Document gaps between current UX and the ideal:
   - Upload two photos → see per-face comparison → photos saved → shareable link

### Part B: Community-scoped Compare design decision

Think through these scenarios (document as AD-225, don't need to solve all now):

1. **Short-term (this session):** When a logged-in Rhodes contributor uses Compare, uploaded photos should auto-save to the Rhodes community archive. This is the Claude Benatar case.

2. **Medium-term questions (BACKLOG for future):**
   - Should `/c/rhodes/compare` exist as a community-scoped version?
   - What if a photo doesn't belong to any community? (Save anyway, let admin assign later)
   - What about cross-community matches?

3. **Core principle:** Photos uploaded through ANY surface (Upload, Compare, Help Identify) must NEVER be lost. Every photo that touches the server gets saved permanently with attribution. This is a heritage archive — data loss is unacceptable.

### Part C: Implement the short-term fix

If not already handled in Phase 2:
- Compare uploads by logged-in users → auto-save to user's active community
- Compare uploads by anonymous users → save to staging, require admin approval
- All photos saved to R2 immediately on upload (not just after approval)

**Commit:** `feat(ux): Compare auto-save + community scoping design (AD-225)`

---

## Phase 6: Deploy + Browser Verify

1. Push: `git push origin main` (or `railway deploy` if needed)
2. Wait for deploy
3. Browser verify:
   - [ ] Both Robert Mattatia photos load on production
   - [ ] Compare result link works (the one for Claude Benatar)
   - [ ] New uploads by logged-in users have correct attribution
   - [ ] Approved photos don't 404
   - [ ] Compare tool flow works end-to-end
4. Screenshots to `docs/screenshots/session-104/`

**Commit:** `docs: session 104 browser verification`

---

## Phase 7: Session Closeout

1. Re-read prompt: `docs/prompts/session-104-prompt.md`
2. Write `docs/assessments/session-104-assessment.md`
3. Update CHANGELOG.md, ROADMAP.md, BACKLOG.md, SESSION_HISTORY.md
4. Write the message Nolan should send to Claude Benatar:
   - Include the shareable Compare link
   - Brief explanation of what the tool found
   - Instructions for how to use Compare in the future
   - Save this message to `docs/user_feedback/claude_benatar_response_104.md`

**Commit:** `docs: session 104 closeout`
