# Session 85: Fix Compare — End-to-End Functional Validation

## SESSION IDENTITY
- **Session**: 85
- **Predecessor**: Session 84 (unified face cards + Find Similar panel)
- **Goal**: Make Compare functional end-to-end. Three comparison modes must work: (1) any two faces in the archive, (2) upload a photo and compare its faces against any archive face, (3) upload two photos and compare faces across them. All uploads persist to the archive. All comparisons are shareable. Search-aided person selection throughout. Validate with the Isaac Cohen test case in production browser.
- **Context file**: `docs/session_context/session-85-context.md` (READ THIS FIRST)
- **Assessment file**: `docs/assessments/session-85-assessment.md` (MANDATORY)
- **Session log**: `docs/sessions/SESSION_085.md`
- **Test use case**: Upload `~/Downloads/claude_rhodesli_feedback/isaac_cohen_potential_4c9141db-13ec-4e7c-b9f9-ec65d6f63338.jpeg`, compare its faces against Isaac Cohen, share an interactive link showing those comparisons.

---

## PRODUCT VISION — Compare

Compare lets you answer: "Are these the same person?" Three modes:

### Mode A: Archive vs. Archive
Compare any two faces already in the platform. Search by name to find each person.
Example: "Compare Isaac Cohen to Unidentified Person 090"

### Mode B: Upload vs. Archive
Upload a photo (which persists to the archive, creating identities for each face).
Compare one or more faces from that photo against any archive face (found by search).
Example: "Upload this family photo. Compare each face against Isaac Cohen."

### Mode C: Upload vs. Upload
Upload two photos (both persist, identities created for all faces).
Compare any face from Photo A against any face from Photo B.
Example: "Upload these two wedding photos. Are any of the same people in both?"

### Shared Principles (ALL Modes)
- **Every upload persists**: Same pipeline as the Upload page — photos go to `raw_photos/`, faces get crops, INBOX identities created. Compare is a LENS, not a separate storage system.
- **Search-aided selection**: Person/face picker uses name search throughout.
- **Shareable results**: Every comparison produces a shareable URL showing an interactive view with the compared faces, scores, and context.
- **Match context**: Scores shown with calibrated confidence tiers AND context about how the score ranks against the person's existing top matches from Find Similar.

### Isaac Cohen Test Case (End-to-End Validation)
1. Go to `/compare`
2. Upload `isaac_cohen_potential_...jpeg` (5-person family photo)
3. Photo persists → 5 faces detected → 5 INBOX identities created
4. Search "Isaac Cohen" → select him
5. See per-face match scores: each of the 5 faces compared against Isaac Cohen
6. See context: Isaac Cohen's nearest existing archive match is distance ~1.22
7. Share a link with Claude Benatar → she sees the interactive comparison view

---

## CRITICAL EXECUTION RULES

### Context Management (Non-Negotiable — Lesson 89)
- **Run `/clear` after EVERY act commit.** No exceptions. No "context is fine."
- After `/clear`, re-read: `cat docs/prompts/session-85-prompt.md` (the specific act you're starting)
- After `/clear`, re-read session log to restore state
- If context exceeds 60%, STOP current work, commit, and `/clear` immediately
- Use subagents with worktrees for implementation touching >2 files

### Testing Strategy
- `make test-fast` before every commit (parallel via pytest-xdist, <30s)
- Run both suites: `pytest tests/ -x -q` AND `pytest rhodesli_ml/tests/ -x -q` (Lesson 80)
- Pre-existing xdist flaky failures: IGNORE if they pass in isolation
- If `make test-fast` fails on something NEW, fix it before continuing

### Browser Verification
- **Primary**: Claude Chrome browser plugin (admin is logged in)
- **Fallback**: Playwright with `mcp__playwright__browser_navigate` (if Chrome extension unavailable)
- Take screenshots for ALL visual changes to `docs/screenshots/session-85/`
- "Auth required" is NOT a valid reason to skip — admin is logged in on both
- Wait for Railway deploy to complete before verification (Lesson 94)

### Hook Compliance
- **Stop hook**: Assessment file MUST exist at `docs/assessments/session-85-assessment.md`
- **Stop hook**: Session log MUST exist at `docs/sessions/SESSION_085.md`
- **Stop hook**: `git status` must be clean (no uncommitted files)
- **PreToolUse (Bash)**: `make test-fast` runs before git commit
- **PostToolUse (Edit|Write)**: AD reminder for ML/core file edits

---

## Phase 0: Orient (5 min)

1. Set session number: `echo "85" > .claude/current_session.txt`
2. Read context: `cat docs/session_context/session-85-context.md`
3. Read lessons: `cat tasks/lessons.md`
4. Verify predecessor items from Session 84 assessment:
   - [ ] Help Identify expansion panel spans full width
   - [ ] Public Similar link still works
   - [ ] Merge/Not Same from inline panel update correctly
5. Check current compare state: `curl -s https://rhodesli.nolanandrewfox.com/compare | head -50`
6. Create session log at `docs/sessions/SESSION_085.md`

**Commit**: `docs: session 85 orient — session files created`

---

## Phase 1: Diagnose + Architecture Plan (20 min)

Before fixing anything, build a complete picture of what's broken and plan the architecture.

**Spec:**
- Test the upload flow end-to-end in browser (Claude Chrome or Playwright fallback)
- Navigate to `/compare`, upload the test image, document what happens (screenshot each step)
- Navigate to `/compare/result/28f18514d9d3` — document what it shows
- Navigate to Isaac Cohen's person page, click "Similar" — document Find Similar scores
- Review the Upload page pipeline (`/upload`, `/api/upload/`) — trace the FULL flow:
  file receipt → R2 storage → photo_index entry → face detection → crop generation → identity creation
- Review the Compare upload pipeline (`/api/compare/upload`) — identify where it diverges from Upload
- Plan the unified architecture: how to wire Compare uploads through the same pipeline

**Record findings in session log under "Phase 1: Diagnosis"**

**Key questions to answer:**
1. Does face detection run on uploaded photos in production? (InsightFace availability?)
2. What's the exact Upload page pipeline? Which functions handle each step?
3. Where does Compare's upload pipeline diverge from Upload's?
4. What data does a comparison result need to store to be shareable?
5. What API endpoints already exist for person search / face selection?

**Commit**: `docs: session 85 phase 1 — compare diagnosis + architecture plan`

---

## Phase 2: Unify Compare Upload with Main Upload Pipeline (45 min)

**This is the foundation phase — everything else depends on it.**

Every photo uploaded via Compare MUST go through the SAME pipeline as the Upload page.
No separate `uploads/compare/` silo.

**Problem**: Compare uploads use `_save_compare_upload()` which saves to a separate
`uploads/compare/` directory. Photos never appear in the Photos section. Face identities
are never created. This means compare uploads are invisible to the rest of the platform.

**Design principle**: Compare is a LENS on uploaded photos, not a separate storage system.
Upload is upload, regardless of which page you came from.

**Spec:**
1. Compare uploads MUST use the same storage path as Upload page uploads:
   - Photo saved to R2 `raw_photos/` (not `uploads/compare/`)
   - Entry created in photo_index (via Supabase or JSON)
   - Face crops generated and saved to R2 `crops/`
   - INBOX identity entries created for each detected face
   - Embeddings stored in embeddings cache
2. For admin users: this happens AUTOMATICALLY on upload (same as Upload page)
3. For non-admin users: photo queued to `pending_uploads.json` for admin review
   (same as Upload page behavior — Lesson 22: admin-only until moderation exists)
4. After upload + face detection, the compare results layer on top of the archived photo
5. Remove or refactor `_save_compare_upload()` to use the standard upload pipeline
6. The compare result page links to the photo's archive page (`/photo/{photo_id}`)

**Research first**: Study how the Upload page (`/upload`, `/api/upload/`) handles photos.
Identify the reusable functions. Wire Compare to call them.

**IMPORTANT**: Follow Lesson 51 (mock BOTH load AND save in tests).
Follow Lesson 19 (admin-only for data-modifying features).

**Files likely touched**: `app/main.py` (compare upload handler, upload pipeline functions)

**Acceptance criteria:**
- [ ] Compare upload uses same storage path as Upload page
- [ ] Photo appears in Photos section immediately (admin) or after approval (non-admin)
- [ ] Face crops generated and stored in standard location
- [ ] INBOX identities created for each detected face
- [ ] Compare result page links to the archived photo page
- [ ] Existing compare tests updated to reflect unified pipeline
- [ ] Non-admin uploads queued for review (same as Upload page)

**Commit**: `feat(compare): unify upload pipeline with main Upload page`

---

## Phase 3: Compare Against Specific Person (Search + Per-Face Scores) (45 min)

This is the core UX Claude Benatar needed: "Compare this photo against Isaac Cohen."

**Problem**: Currently, uploading a photo runs a blind comparison against ALL archive faces.
There's no way to say "I think this might be Isaac Cohen" and see per-face match scores
against that specific person.

**Spec — The "Upload vs. Archive" Flow:**
1. After uploading a photo and seeing initial results, show a search box:
   "Compare against a specific person" (reuse existing identity search component)
2. When user selects a person (e.g., Isaac Cohen):
   - Show the selected person's best crop prominently as reference
   - For EACH face detected in the uploaded photo, show:
     - Face crop thumbnail (from the uploaded photo)
     - Match score against the selected person (distance + calibrated confidence)
     - Confidence tier label with color (green/amber/red)
   - **Context section**: "Isaac Cohen's closest existing matches in the archive are
     at distance X-Y (Low/Moderate confidence). Your best uploaded face scores Z."
     This tells the user whether their match is better or worse than existing matches.
3. New API endpoint: `POST /api/compare/vs-person`
   - Params: `photo_id` (from the now-archived upload), `identity_id` (selected person)
   - Returns: per-face match scores + selected person's existing Find Similar context
4. Wire the person selector to this endpoint via HTMX partial swap
5. **Shareable**: This comparison is saved with a result_id and shareable URL.
   The shared link shows the interactive view: the person, all faces from the photo,
   all scores. The recipient can see the comparison without uploading anything.

**Files likely touched**: `app/main.py` (new API endpoint, compare page UI)

**Acceptance criteria:**
- [ ] After uploading, user can search for a specific person
- [ ] Per-face match scores shown against selected person
- [ ] Context shows the person's existing top archive matches for comparison
- [ ] Result is shareable via URL
- [ ] Works with the Isaac Cohen test case (5 faces scored against Isaac Cohen)
- [ ] Tests cover the vs-person endpoint and shareable result

**Commit**: `feat(compare): compare-against-specific-person with search + shareable results`

---

## Phase 4: Fix Compare Result Page — Interactive Shareable View (30 min)

The result page (`/compare/result/{result_id}`) needs to become the interactive
shareable view that Claude Benatar (or any community member) receives.

**Problem**: Current result page is a flat list of "Unlikely match" entries without
the uploaded photo, without face context, and without interactivity.

**Spec:**
1. Show the uploaded photo at the top with face bounding box overlays
2. If comparing against a specific person: show that person's crop as the reference
3. For each detected face in the uploaded photo:
   - Face crop thumbnail (clickable to select)
   - Match score against the reference person (if vs-person mode)
   - OR top archive match (if general mode)
   - Confidence tier label with color
4. If multi-face photo: allow selecting different faces to see their matches
5. For admin: show raw distance scores
6. Match context: how this score ranks vs. the person's existing top matches
7. Share button (already exists) + "Do you recognize anyone?" form (already exists)
8. Link to the archived photo page (`/photo/{photo_id}`)
9. Mobile responsive (already partially exists, verify at 375px)

**Files likely touched**: `app/main.py` (compare result route at line 17846)

**Acceptance criteria:**
- [ ] Uploaded photo visible on result page with face overlays
- [ ] Reference person shown when in vs-person mode
- [ ] Per-face match scores visible and clear
- [ ] Multi-face selector works
- [ ] Admin sees raw distance scores
- [ ] Mobile responsive at 375px
- [ ] Shared link renders complete interactive view for recipients

**Commit**: `feat(compare): interactive shareable result page`

---

## Phase 5: Tests + Regression Check (20 min)

**Spec:**
1. Run full test suite: `make test-fast` (both app + ML)
2. Verify existing compare tests still pass: `pytest tests/test_compare.py -v`
3. Add/update tests for:
   - [ ] Upload via compare creates photo_index entry (mocked)
   - [ ] Upload via compare creates INBOX identities (mocked)
   - [ ] vs-person endpoint returns per-face scores
   - [ ] vs-person endpoint includes Find Similar context
   - [ ] Result page shows uploaded photo element
   - [ ] Result page shows face bounding box data
   - [ ] Non-admin upload queued for review (403 on direct save)
   - [ ] Multi-face upload shows face selector on result page
   - [ ] Shareable result URL loads with full comparison data
4. Verify no regressions in pair compare or multi-upload flows

**Commit**: `test(compare): session 85 — comprehensive compare tests`

---

## Phase 6: Deploy + Browser Verification (20 min)

1. Run `make test-fast` — all pass
2. Run full suite: `source venv/bin/activate && pytest tests/ -x -q && pytest rhodesli_ml/tests/ -x -q`
3. `git push origin main` (triggers Railway deploy)
4. Wait for deploy — check health: `curl -s https://rhodesli.nolanandrewfox.com/api/health | python3 -m json.tool`
5. **Browser verification** (Claude Chrome primary, Playwright fallback):

   **Test the Isaac Cohen use case end-to-end:**
   - [ ] Navigate to `/compare`
   - [ ] Upload `~/Downloads/claude_rhodesli_feedback/isaac_cohen_potential_4c9141db-13ec-4e7c-b9f9-ec65d6f63338.jpeg`
   - [ ] Verify face detection completes (5 faces expected) (screenshot)
   - [ ] Verify photo was saved to archive (navigate to Photos, find it) (screenshot)
   - [ ] Verify 5 INBOX identities created
   - [ ] Search for "Isaac Cohen" in the compare person selector
   - [ ] Verify per-face match scores against Isaac Cohen (screenshot)
   - [ ] Verify context shows Isaac Cohen's existing match distances
   - [ ] Copy the shareable link
   - [ ] Open the shareable link in a new tab (or incognito)
   - [ ] Verify the shared view shows the full interactive comparison (screenshot)
   - [ ] Check mobile viewport (375px) (screenshot)

6. Take all screenshots to `docs/screenshots/session-85/`

**Commit**: `test: session 85 — browser verification screenshots`

---

## Phase 7: Session Docs (15 min)

1. Write `docs/assessments/session-85-assessment.md`
2. Update `CHANGELOG.md` with version entry
3. Update `ROADMAP.md` — check boxes, move to Recently Completed
4. Update `docs/BACKLOG.md` — Status column updates
5. Update `docs/ml/ALGORITHMIC_DECISIONS.md` if any ML decisions made
6. Update `docs/DESIGN_DECISIONS.md` — Compare redesign decisions
7. Create/update `docs/sessions/SESSION_085.md` session log

**Commit**: `docs: session 85 — assessment, changelog, roadmap`

---

## PARALLELIZATION PLAN

**Phases 2, 3, 4 all touch `app/main.py`.** Per Lesson 88, these MUST be sequential
(monolithic app file prevents parallel worktree execution).

However, within Phase 1 (diagnosis), research can be parallelized:
- **Agent A**: Read compare code in app/main.py (routes, handlers)
- **Agent B**: Read Upload page pipeline code in app/main.py
- **Agent C**: Check production state (curl endpoints, browser test)

Phase 5 (tests) can partially overlap with Phase 6 (deploy) since tests run locally
while deploy goes to Railway.

**Recommended execution order**: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7
(Sequential due to app/main.py constraint, but use subagents for research within phases)

---

## SCOPE CONTROL

**In scope:**
- Unify compare upload with main Upload pipeline (photo persistence + identity creation)
- Compare-against-specific-person flow with search and per-face scores
- Interactive shareable result page showing uploaded photo + face context
- End-to-end validation with Isaac Cohen test case
- Tests for all new functionality

**Out of scope (do NOT touch):**
- ML pipeline changes (face detection model, embeddings)
- Gemini API calls or enrichment
- Compare Tier 2 standalone product (AD-117)
- Real-time GPU inference on Railway (AD-187)
- Mode A (Archive vs. Archive) — this mostly works already via Find Similar
- Mode C (Upload vs. Upload pair compare) — `/compare/pair` already exists, polish later
- Data migrations or schema changes
- GEDCOM, Tree, Map, or other feature areas

**Priority order if time is short:**
1. Phase 2 (unified upload) — foundation, nothing works without this
2. Phase 3 (vs-person + search) — the core Claude Benatar use case
3. Phase 4 (result page) — makes it shareable
4. Phases 5-7 (tests, deploy, docs) — mandatory but last

**If something in scope turns out to be >45 min for a single phase:**
Split it. Ship what works, defer the rest with a BACKLOG entry.
A partial fix that's validated > a complete fix that's untested.

---

## Key References

| File | Purpose |
|------|---------|
| `docs/prompts/session-85-prompt.md` | This file — re-read after every `/clear` |
| `docs/session_context/session-85-context.md` | Research, screenshots, design direction |
| `docs/sessions/SESSION_085.md` | Session progress log |
| `docs/assessments/session-85-assessment.md` | Self-evaluation (MANDATORY) |
| `docs/feedback/2026-03-02-claude-benatar.md` | Original user feedback |
| `tests/test_compare.py` | Compare test suite (25 tests) |
| `app/main.py:16161` | Compare page route |
| `app/main.py:17009` | Compare upload handler |
| `app/main.py:17846` | Compare result page route |
| `app/main.py:18246` | Pair compare page route |
| `CLAUDE.md` | Project rules |
| `tasks/lessons.md` | 99 lessons — read at session start |
| `docs/BACKLOG.md` | Feature status and priorities |
| `docs/ml/ALGORITHMIC_DECISIONS.md` | ML decisions (AD-117, AD-182, AD-187, AD-198) |

## Test Image for Validation
```
~/Downloads/claude_rhodesli_feedback/isaac_cohen_potential_4c9141db-13ec-4e7c-b9f9-ec65d6f63338.jpeg
```
- Group family photo, 5 people (2 men standing, 3 women seated)
- Should detect 5 faces
- Compare each face against Isaac Cohen (confirmed identity in archive)
- Isaac Cohen's existing nearest archive matches are at distance ~1.22 (Low confidence)
- The shareable link should show: Isaac Cohen's crop, all 5 face crops, per-face scores
