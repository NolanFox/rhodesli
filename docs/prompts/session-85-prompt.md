# Session 85: Fix Compare — End-to-End Functional Validation

## SESSION IDENTITY
- **Session**: 85
- **Predecessor**: Session 84 (unified face cards + Find Similar panel)
- **Goal**: Make Compare functional end-to-end. A community member should be able to upload a family photo, compare faces against a specific known person (Isaac Cohen), see meaningful match scores with context, and have the photo saved to the archive. Validate with real photo in production browser.
- **Context file**: `docs/session_context/session-85-context.md` (READ THIS FIRST)
- **Assessment file**: `docs/assessments/session-85-assessment.md` (MANDATORY)
- **Session log**: `docs/sessions/SESSION_085.md`
- **Test use case**: Upload `~/Downloads/claude_rhodesli_feedback/isaac_cohen_potential_4c9141db-13ec-4e7c-b9f9-ec65d6f63338.jpeg`, compare against Isaac Cohen

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
- **Fallback**: Playwright with `mcp__playwright__browser_navigate` (if Chrome extension unavailable due to claude.ai outage)
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

## Phase 1: Diagnose — What's Actually Broken (15 min)

Before fixing anything, build a complete picture of what's broken vs. what's working.

**Spec:**
- Test the upload flow end-to-end in browser (Claude Chrome or Playwright fallback)
- Navigate to `/compare`, upload the test image
- Document what happens at each step (screenshot each)
- Navigate to `/compare/result/28f18514d9d3` — document what it shows
- Navigate to Isaac Cohen's person page, click "Similar" — document what it shows
- Check Railway deploy logs for any compare-related errors
- Check `comparison_results.json` on production — does it have results?
- Review the compare upload handler code (`app/main.py:17009`) — trace the full flow

**Record findings in session log under "Phase 1: Diagnosis"**

**Key questions to answer:**
1. Does face detection actually run on the uploaded photo? (or does production lack InsightFace?)
2. Are results saved to `comparison_results.json`?
3. Does the result page render the uploaded photo?
4. Can the user select a specific person to compare against?
5. Does the uploaded photo get added to the main photo archive?

**Commit**: `docs: session 85 phase 1 — compare diagnosis`

---

## Phase 2: Fix Compare Result Page UX (30 min)

The result page (`/compare/result/{result_id}`) is missing critical context.

**Problem**: Result page shows a flat list of "Unlikely match" entries without:
- The uploaded photo itself
- Which face in the photo was compared
- Face bounding box overlays on the uploaded photo
- Distance/score context (how does this score compare to known matches?)
- The ability to select a different face from a multi-face upload

**Spec:**
1. Show the uploaded photo at the top of the result page with face bounding box overlay
2. If multi-face photo: show face selector thumbnails (which face was compared)
3. Show the compared face crop prominently next to the uploaded photo
4. For each match card, show:
   - Match face crop (already exists)
   - Identity name with link to person page (already exists)
   - Confidence percentage with tier label (already exists)
   - **NEW**: Raw distance score (for admin users only)
   - **NEW**: Context line: "This person's top archive match is X at Y distance" (helps user understand if this is a good or bad score)
5. Sort matches by confidence (highest first) — verify this is happening
6. Limit to top 10 matches (already exists) but make the threshold meaningful
7. Add "Compare against a specific person" link that opens the person search

**Files likely touched**: `app/main.py` (compare result route at line 17846)

**Acceptance criteria:**
- [ ] Uploaded photo visible on result page
- [ ] Face bounding box overlay on uploaded photo
- [ ] Multi-face selector works if photo has >1 face
- [ ] Admin users see raw distance scores
- [ ] Context line shows how score compares to existing matches
- [ ] Tests updated for new result page elements

**Commit**: `feat(compare): show uploaded photo + face context on result page`

---

## Phase 3: Add "Compare Against Specific Person" Flow (45 min)

This is the flow Claude Benatar actually wanted: "Compare this uploaded photo against Isaac Cohen."

**Problem**: Currently, uploading a photo compares against ALL archive faces. There's no way to say "I think this might be Isaac Cohen — show me how each face in this photo matches him."

**Spec:**
1. On the `/compare` page, AFTER uploading a photo and seeing results, add a section:
   "Compare against a specific person" with a search box (reuse existing identity search)
2. When user selects a person (e.g., Isaac Cohen):
   - Show the selected person's best crop prominently
   - For EACH face detected in the uploaded photo, show:
     - Face crop thumbnail
     - Match score against the selected person
     - Confidence tier label
     - Visual indicator (green/amber/red) based on match strength
   - Show context: "Isaac Cohen's closest archive matches are at distance X-Y"
   - This helps the user understand: is 1.15 a good score or bad score for Isaac Cohen?
3. Add a new API endpoint: `POST /api/compare/upload/vs-person`
   - Params: `upload_id` (from previous upload), `identity_id` (selected person)
   - Returns: per-face match scores against that person + Find Similar context
4. Wire the person selector to this endpoint via HTMX
5. The "Or search by person in the archive" section on `/compare` already exists —
   wire it to work WITH an uploaded photo (not just as standalone archive search)

**Files likely touched**: `app/main.py` (compare routes)

**Acceptance criteria:**
- [ ] After uploading, user can search for a specific person
- [ ] Per-face match scores shown against selected person
- [ ] Context shows the person's existing top matches for comparison
- [ ] Works with the Isaac Cohen test case
- [ ] Tests cover the new vs-person endpoint

**Commit**: `feat(compare): add compare-against-specific-person flow`

---

## Phase 4: Fix Photo Persistence to Archive (30 min)

Uploaded compare photos must be saveable to the Rhodesli archive, not just `uploads/compare/`.

**Problem**: Photos uploaded via Compare live in a separate `uploads/compare/` directory. They never appear in the Photos section. For admin users, there should be a clear path: Upload → Compare → "Add to Archive" → Photo appears in Photos section with detected faces.

**Spec:**
1. For admin users: add "Save to Archive" button on the compare result page
2. When clicked:
   - Copy photo from `uploads/compare/` to main photo storage (R2 `raw_photos/`)
   - Create entry in `photo_index.json` (via Supabase if available, or JSON fallback)
   - Create face entries for each detected face
   - Add face crops to R2 `crops/`
   - Create INBOX identity entries for each detected face
   - Show success message with link to the new photo page
3. This follows the Gatekeeper pattern: admin explicitly approves adding to archive
4. Non-admin users see "Contribute to Archive" which queues for admin review (existing flow)
5. The auto-queue to `pending_uploads.json` (AD-182) continues to work as before

**IMPORTANT**: This phase requires careful data handling. Mock all data writes in tests.
Follow Lesson 51: Tests that POST to data-modifying routes MUST mock BOTH load AND save.

**Files likely touched**: `app/main.py` (new route + button), `core/photo_registry.py`

**Acceptance criteria:**
- [ ] Admin sees "Save to Archive" button on result page
- [ ] Clicking it adds photo to main archive (photo_index, R2, crops)
- [ ] New INBOX identities created for detected faces
- [ ] Photo appears in Photos section after save
- [ ] Non-admin users see "Contribute" (existing behavior)
- [ ] Tests mock all data writes properly

**Commit**: `feat(compare): admin save-to-archive for uploaded photos`

---

## Phase 5: Tests + Regression Check (20 min)

**Spec:**
1. Run full test suite: `make test-fast` (both app + ML)
2. Verify existing compare tests still pass: `pytest tests/test_compare.py -v`
3. Add/update tests for:
   - [ ] Result page shows uploaded photo element
   - [ ] Result page shows face bounding box data
   - [ ] vs-person endpoint returns per-face scores
   - [ ] vs-person endpoint includes Find Similar context
   - [ ] Save-to-archive creates photo_index entry (mocked)
   - [ ] Save-to-archive creates INBOX identities (mocked)
   - [ ] Non-admin cannot trigger save-to-archive (403)
   - [ ] Multi-face upload shows face selector on result page
4. Verify no regressions in other compare flows (pair compare, multi-upload)

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
   - [ ] Verify face detection completes (5 faces expected)
   - [ ] Verify uploaded photo visible on result page (screenshot)
   - [ ] Verify face bounding boxes visible on uploaded photo
   - [ ] Search for "Isaac Cohen" in the person selector
   - [ ] Verify per-face match scores against Isaac Cohen (screenshot)
   - [ ] Verify context shows Isaac Cohen's existing match distances
   - [ ] Click "Save to Archive" (admin)
   - [ ] Verify photo appears in Photos section (screenshot)
   - [ ] Navigate to `/compare/result/{id}` — verify shareable link works
   - [ ] Check the result page on mobile viewport (375px) — responsive? (screenshot)

6. Take all screenshots to `docs/screenshots/session-85/`

**Commit**: `test: session 85 — browser verification screenshots`

---

## Phase 7: Session Docs (15 min)

1. Write `docs/assessments/session-85-assessment.md`:
   ```
   # Session 85 Assessment
   ## Shipped
   - [x] Phase N: [feature] — Evidence: [test/screenshot]
   ## Deferred
   - Phase M: [feature] — Reason: [why] — BACKLOG: [ID]
   ## Red Flags
   - [Severity] [description] — Fix: [action]
   ## Next Session Should Verify
   1. [highest priority]
   ```
2. Update `CHANGELOG.md` with version entry
3. Update `ROADMAP.md` — check boxes, move to Recently Completed
4. Update `docs/BACKLOG.md` — Status column updates
5. Update `docs/ml/ALGORITHMIC_DECISIONS.md` if any ML decisions made
6. Update `docs/DESIGN_DECISIONS.md` if any design decisions made
7. Create/update `docs/sessions/SESSION_085.md` session log

**Commit**: `docs: session 85 — assessment, changelog, roadmap`

---

## PARALLELIZATION PLAN

**Phases 2, 3, 4 all touch `app/main.py`.** Per Lesson 88, these MUST be sequential
(monolithic app file prevents parallel worktree execution).

However, within Phase 1 (diagnosis), research can be parallelized:
- **Agent A**: Read compare code in app/main.py (routes, handlers)
- **Agent B**: Check production state (curl endpoints, read logs)
- **Agent C**: Read test file + existing PRDs

Phase 5 (tests) can partially overlap with Phase 6 (deploy) since tests run locally
while deploy goes to Railway.

**Recommended execution order**: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7
(Sequential due to app/main.py constraint, but use subagents for research within phases)

---

## SCOPE CONTROL

**In scope:**
- Fix compare result page to show uploaded photo + face context
- Add compare-against-specific-person flow
- Fix photo persistence (admin save-to-archive)
- End-to-end validation with Isaac Cohen test case
- Tests for all new functionality

**Out of scope (do NOT touch):**
- ML pipeline changes (face detection model, embeddings)
- Gemini API calls
- Compare Tier 2 standalone product (AD-117)
- Real-time GPU inference on Railway (AD-187)
- Multi-photo compare improvements (PRD-021 — already working)
- Pair compare (/compare/pair) changes
- Data migrations or schema changes
- GEDCOM, Tree, Map, or other feature areas

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
| `app/main.py:17009` | Upload handler |
| `app/main.py:17846` | Result page route |
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
