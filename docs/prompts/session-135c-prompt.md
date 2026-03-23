# Session 135c — Override Preview + Compare Active Side + UX Analysis

## Mode
Interactive — user is triaging Fox Family archive on mobile during train commute. Expect real-time feedback throughout.

## Predecessor
- Assessment: `docs/assessments/session-135b-assessment.md`
- Context: `docs/session_context/session-135-research.md`
- Feedback: `docs/feedback/session-135-feedback.md`
- Plan: `.claude/plans/robust-chasing-globe.md`

## Goal
Ship the 3 deferred UX items from Session 135b: co-occurrence photo preview for Override button (FB-008), active side indicator in Compare modal (FB-009), and design analysis of Speed-Run vs Focus mode overlap (DD-018). Handle real-time user feedback in parallel.

## Read First
- `tasks/lessons.md` — especially Lessons 149 (browser READ-ONLY), 39 (event delegation), 84 (museum-quality design)
- `docs/prds/048_same_photo_merge_override.md` — existing PRD to extend
- `docs/feedback/session-135-feedback.md` — FB-008, FB-009 entries

---

## Phase 0: Session Init (~3 min)

```bash
echo "135c" > .claude/current_session.txt
echo "interactive" > .claude/session_mode.txt
source venv/bin/activate && make test-fast
```

- Create `docs/session_logs/session-135c-log.md`
- Create `docs/feedback/session-135c-feedback.md` (FB-013+ continuing from Session 135)
- Baseline test count: record in session log

---

## Phase 1: Design Documents (~15 min, orchestrator)

Three design artifacts BEFORE any code. All sequential on main branch.

### 1A: Extend PRD-048 — Co-Occurrence Preview Visualization

Add a new section to `docs/prds/048_same_photo_merge_override.md`:

**New endpoint**: `GET /api/identity/{target_id}/co-occurrence-preview/{neighbor_id}`
- Returns HTML partial: shared photo with both face bounding boxes highlighted
- Reuse face overlay rendering pattern from `_compare_photo_with_overlays` in compare_routes.py
- Amber highlight = target face, indigo highlight = neighbor face

**Override button change**: Replace `hx_confirm` browser dialog with HTMX two-step:
1. First click → `hx_get` loads preview panel (slide-down above merge button)
2. Preview shows: photo thumbnail (400px max), both faces highlighted, filename
3. Buttons: "Cancel" (dismiss) + "Confirm Override & Merge" (execute)

### 1B: Brief Spec — FB-009 Compare Active Side

No PRD needed (under 30 min). Spec:
- Add `data-compare-side="target"` / `data-compare-side="neighbor"` to panel divs
- Default: target (left) panel has `ring-2 ring-amber-400/50` active indicator
- Arrow button clicks toggle active ring via hyperscript
- Labels: "Source" subtitle (left), "Match" subtitle (right)

### 1C: DD-018 — Speed-Run vs Focus Mode Distinct Purposes

Add entry to `docs/DESIGN_DECISIONS.md`:
- Speed-Run = Cluster quality triage ("Is this ML cluster correct?")
- Focus Mode = Identity knowledge elicitation ("Who is this person?")
- They serve different intents — keep separate, don't merge
- Recommendations (as BACKLOG items):
  - Rename "Speed-Run" → "Cluster Review" in sidebar
  - Add subtitle text distinguishing the two
  - Cross-links between surfaces

**Phase 1 exit**: Commit docs. /clear.

---

## Phase 2: Parallel Implementation (~30 min wall time)

### Parallelization Table

| Track | Branch | Files Touched | Start After |
|-------|--------|---------------|-------------|
| A: FB-008 | `session-135c/fb-008-override-preview` | `app/main.py` (9631-9656), `app/identity_routes.py`, `tests/` | Phase 1 |
| B: FB-009 | `session-135c/fb-009-compare-active` | `app/compare_routes.py` (5700-5937), `tests/` | Phase 1 |
| Codex | Background subagent | Read-only audit | Phase 2 start |

**Zero file overlap between Track A and B** — safe for parallel worktrees.

### Track A: FB-008 Override Preview (Subagent)

Delegation brief for worktree subagent:

> Working in worktree branch `session-135c/fb-008-override-preview`.
>
> **Task**: Add co-occurrence photo preview to the Override button in neighbor_card.
>
> **Files to modify**:
> - `app/main.py` — `neighbor_card()` function (~line 9631-9656). Replace `hx_confirm` with `hx_get` that loads a preview panel.
> - `app/identity_routes.py` — Add endpoint `GET /api/identity/{target_id}/co-occurrence-preview/{neighbor_id}`. Returns HTML partial with shared photo + face bounding box overlays. Use `find_shared_photo_filename()` to get the photo, then render with face overlays (see `_compare_photo_with_overlays` pattern in compare_routes.py).
>
> **Spec**: See extended PRD-048 section "Co-Occurrence Preview Visualization".
>
> **Tests** (in new file `tests/test_session_135c_override_preview.py`):
> 1. Preview endpoint returns photo HTML for co-occurring identities
> 2. Preview endpoint returns 404 for non-co-occurring identities
> 3. Non-admin cannot access preview endpoint
> 4. Override button has `hx_get` (not `hx_confirm`) when merge is blocked
> 5. Merged result preserves override reason
>
> **Rules**: `make test-fast` before commit. Event delegation for any JS. Aria labels on new buttons. Community nav_prefix on all URLs.
>
> **Commit message format**: `feat(ux): co-occurrence photo preview on Override button (FB-008)`

### Track B: FB-009 Compare Active Side (Subagent)

Delegation brief for worktree subagent:

> Working in worktree branch `session-135c/fb-009-compare-active`.
>
> **Task**: Add visual active-side indicator to the Compare Faces modal.
>
> **Files to modify**:
> - `app/compare_routes.py` — In the two-panel compare content (~lines 5901-5937):
>   - Add `data-compare-side="target"` / `data-compare-side="neighbor"` to panel divs
>   - Add "Source" / "Match" subtitle labels above each panel
>   - Add `ring-2 ring-amber-400/50 rounded-xl` to target panel by default
>   - On arrow button clicks, use hyperscript: `on click add .ring-2 .ring-amber-400/50 to closest <div[data-compare-side]/> then remove .ring-2 .ring-amber-400/50 from <div[data-compare-side]:not(:has(me))/>`
>
> **Tests** (in new file `tests/test_session_135c_compare_active.py`):
> 1. Compare content includes `data-compare-side` attributes
> 2. Target panel has default active ring class
> 3. "Source" and "Match" labels present
>
> **Rules**: `make test-fast` before commit. No direct DOM bindings (event delegation only). Aria labels on labels.
>
> **Commit message format**: `feat(ux): active side indicator in Compare modal (FB-009)`

### Codex Audit (Background Subagent)

> Audit scope: Review the new code from Track A and Track B after merge.
> Focus areas:
> 1. Event delegation correctness — no direct DOM bindings on HTMX-swapped elements
> 2. Accessibility — new buttons have aria-labels, focus management in preview panel
> 3. HTMX target/swap correctness — no orphaned hx-target references
> 4. Compare modal keyboard navigation gaps
> 5. Security — new endpoint auth guards
>
> Write findings to `docs/session_context/session-135c-codex-audit.md`
> Triage: P0/P1 → fix immediately, P2 → BACKLOG, P3 → discard

### Interactive Feedback Handling

Throughout Phase 2, the orchestrator handles incoming user feedback:
- Assign FB-013+ IDs (continuing from Session 135's FB-012)
- Background subagent writes to `docs/feedback/session-135c-feedback.md`
- P0 → interrupt and fix immediately (new worktree if needed)
- P1 < 15 min → fix in current phase
- P1 > 15 min or P2/P3 → BACKLOG with breadcrumb

**Phase 2 exit**: Both subagents complete. Do NOT merge yet.

---

## Phase 3: Merge + Test (~10 min)

```bash
# Create parallel session flag
touch .claude/parallel_session_active

# Merge tracks (docs first, then code)
./scripts/merge.sh session-135c/fb-008-override-preview session-135c/fb-009-compare-active

# Remove flag
rm .claude/parallel_session_active

# Full test
make test-fast
```

Fix any merge conflicts or test failures. Commit fixes.

**Phase 3 exit**: All tests pass on main. /clear.

---

## Phase 4: Browser Verification (~10 min, READ-ONLY)

### Verify FB-008
- Navigate to a person page that has a co-occurrence-blocked neighbor
- Verify Override button shows preview panel (not browser confirm dialog)
- Verify preview shows photo with highlighted face bounding boxes
- Screenshot saved to `docs/screenshots/session-135c/`

### Verify FB-009
- Open Compare Faces modal from any person page
- Verify target (left) panel has amber ring indicator
- Click arrows on right side — verify ring moves to right panel
- Verify "Source" / "Match" labels visible
- Screenshot

### UX Review
Run `/ux-review` skill on all screenshots taken.

### Codex Triage
- Read `docs/session_context/session-135c-codex-audit.md`
- Fix P0/P1 findings immediately
- Add P2 to BACKLOG
- Log value assessment in session assessment

**Phase 4 exit**: All verifications pass. Commit any fixes. /clear.

---

## Phase 5: Session End (~10 min)

### Mandatory Outputs
1. Assessment: `docs/assessments/session-135c-assessment.md`
2. CHANGELOG: increment to v0.99.46
3. ROADMAP: update FB-008, FB-009 status in Recently Completed
4. BACKLOG: close FB-008, FB-009. Add DD-018 recommendations as new items.
5. SESSION_HISTORY: add Session 135c entry

### Deploy
```bash
git push origin main
# Verify health 200
# Verify builder=DOCKERFILE
```

### Final Checks
- `git log origin/main..HEAD` must be empty
- Run `/session-review` skill
- All FB items from 135c feedback file have disposition

---

## Reference Documents
- Plan: `.claude/plans/robust-chasing-globe.md`
- PRD-048: `docs/prds/048_same_photo_merge_override.md`
- Session 135 feedback: `docs/feedback/session-135-feedback.md`
- Session 135 research: `docs/session_context/session-135-research.md`
- Parallel agent strategy: `docs/architecture/PARALLEL_AGENT_STRATEGY.md`
- Lessons 39 (event delegation), 84 (museum-quality), 149 (browser READ-ONLY)
