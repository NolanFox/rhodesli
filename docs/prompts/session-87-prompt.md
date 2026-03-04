# Session 87: Compare & Discoveries UX Overhaul

## Context

Nolan uploaded a Purim 1922 group photo shared by Claude Benatar on Facebook. Community members are identifying people. Using Rhodesli's Compare tool to find Netanel Menashe took 10+ clicks through 8 face accordions, with tiny images, confusing scores (62% vs 48% for the same match), and a sparse shareable result page that says "Unlikely match." The Discoveries page (184 items) buries the same match with no filter/sort. Identity cards are missing unmerge/detach actions and face galleries.

**Full research**: `docs/session_context/session-87-context.md`
**Netanel Menashe**: Distance 1.225 (UP 531) and 1.13 (UP 851) — both Tier 2, system working correctly. UX makes it invisible.

---

## Act 1: Orient & Setup (5 min)

- Set `.claude/current_session.txt` to "87"
- Save prompt to `docs/prompts/session-87-prompt.md`
- Create `docs/session_logs/session-87-log.md` with act checklist (mirror this plan)
- Read `tasks/lessons.md` + `tasks/todo.md`
- Confirm `docs/session_context/session-87-context.md` exists with breadcrumbs
- Add Lesson 100: "Planning sessions must create context file, prompt file, and session log BEFORE implementation. Breadcrumbs (predecessor link, deferred work, decision IDs) are mandatory. This was missed in Session 87 planning until user corrected it."
- Use `TaskCreate` to create tasks for each act
- **Commit**: `chore(session): session 87 setup + lesson 100`

> **CLEAR CONTEXT** — use /clear, then re-read Act 2 from `docs/prompts/session-87-prompt.md`

---

## Act 2: Unify Confidence Scoring (Critical Bug)

**Problem**: 4+ different confidence paths → same distance produces 62% or 48%.

**Act 2a**: Create `core/confidence.py` with canonical function + tests
- Single `compute_face_confidence(distance)` → `{confidence_pct, tier, label, tier_color}`
- Priority: calibrator → sigmoid CDF → linear fallback
- Create `tests/test_confidence.py`
- **Commit**: `fix(scoring): create unified confidence scoring module (AD-200)`

**Act 2b**: Wire into `core/neighbors.py`
- Replace `find_similar_faces()` tier assignment (lines ~363-395)
- Run tests
- **Commit**: `refactor(scoring): wire neighbors.py to core.confidence`

**Act 2c**: Wire into `app/compare_routes.py`
- Replace inline scoring at lines ~1748, ~2152, ~3439, ~3677
- Run tests
- **Commit**: `refactor(scoring): wire compare_routes to core.confidence`

**Act 2d**: Wire into `app/main.py`
- Replace 3 local `_confidence_tier()` defs (lines ~5065, ~14547, ~19316)
- Run tests
- **Commit**: `refactor(scoring): wire main.py to core.confidence`

**AD entry**: AD-200 "Unified Confidence Scoring"

> **CLEAR CONTEXT** — use /clear, then re-read Act 3 from `docs/prompts/session-87-prompt.md`. Update task status.

---

## Act 3: Compare "Best Matches" Summary View

**Problem**: 8 face accordions, tiny 80px images, good matches buried.

**Act 3a**: New `_compare_summary_section()` function
- Collect matches across all faces where confidence >= 40%
- Sort by confidence descending, CONFIRMED identities first
- Each card: source crop 150px + matched crop 150px, large confidence badge, name, share button
- Admin: Confirm / Not Same buttons
- **Commit**: `feat(compare): add best-matches summary section`

**Act 3b**: Collapse per-face accordions when summary exists + increase image sizes
- Per-face accordions collapsed by default
- Images: result cards 80→112px, per-face header 56→80px, target rows 40→64px
- `rounded-lg` instead of `rounded-full`
- **Commit**: `feat(compare): larger images and collapsed detail sections`

> **CLEAR CONTEXT** — use /clear. If parallelizing: spawn Track A + Track B subagents here. Otherwise re-read Act 4.

---

## Act 4: Shareable Result Page Overhaul

**Problem**: Tiny face, "Unlikely match", sparse layout. Not compelling for Facebook sharing.

**Act 4a**: Hero redesign + better framing
- Large side-by-side (200px each), source photo with face highlighted
- "Could this be [Name]?" framing instead of "Unlikely match"
- Remove raw distance from community-facing page
- Better empty state: "We haven't found a strong match yet — can you help?"
- **Commit**: `feat(compare): redesign shareable result page`

**Act 4b**: OG tags + verification
- `og:title` = "Could this be Netanel Menashe? 62% match in Rhodes Archive"
- Browser verify shareable page in Claude Chrome → screenshot → /ux-review
- **Commit**: `feat(compare): improve OG tags for social sharing`

> **CLEAR CONTEXT** — use /clear, then re-read Act 5 from prompt. Update task status.

---

## Act 5: Discoveries Page Improvements

**Problem**: 184 entries, no filter/sort, small faces, no comparison.

**Act 5a**: Sort by confidence + add filter controls
- Sort by confidence_pct descending using unified scoring
- Filter controls: "by photo" dropdown, "by confidence" buttons (Strong/Possible/All)
- HTMX query params: `/api/discoveries?photo_id=X&min_confidence=50`
- **Commit**: `feat(discoveries): sort by confidence and add filter controls`

**Act 5b**: Inline compare link + larger faces + confidence percentage
- Add "Compare side-by-side" link → pre-fills compare workspace
- Switch `rounded-full` to `rounded-lg`
- Show confidence_pct numerically alongside tier label
- Browser verify in Claude Chrome → screenshot → /ux-review
- **Commit**: `feat(discoveries): inline compare links and larger face images`

> **CLEAR CONTEXT** — use /clear, then re-read Act 6 from prompt. Update task status.

---

## Act 6: Fix Identity Card Navigation & Actions

**Problem**: No visible unmerge/detach, no face gallery access, "Photos" button misleading.

**Act 6a**: Add "Faces" button + make detach visible
- On identity cards with >1 face: add "Faces" button → loads face gallery
- Make detach button always visible (not hover-only) for admin
- **Commit**: `fix(cards): add faces button and visible detach for multi-face identities`

**Act 6b**: Verify Netanel Menashe specifically
- Browser verify: identity card → Faces → see 2 crops → Detach works
- Screenshot → /ux-review
- **Commit**: `test(cards): verify multi-face identity navigation`

> **CLEAR CONTEXT** — use /clear, then re-read Act 7 from prompt. Update task status.

---

## Act 7: Verification & Session Close

- Re-read original prompt from `docs/prompts/session-87-prompt.md`
- Run Feature Reality Contract verification for each act
- Run `make test-fast` (both test suites)
- Browser verify ALL UI changes in Claude Chrome:
  - Compare: Purim photo → summary shows Netanel first
  - Shareable: "Could this be..." framing, large faces
  - Discoveries: sorted, Netanel near top, filter works
  - Identity card: Netanel → Faces → 2 crops → Detach visible
- Take screenshots → save to `docs/screenshots/session-87/`
- Run `/ux-review` on all screenshots
- Write `docs/assessments/session-87-assessment.md`
- Update `SESSION_LOG.md`, `ALGORITHMIC_DECISIONS.md`, `CHANGELOG.md`, `ROADMAP.md`
- Archive session log to `docs/session_logs/`
- Run `/session-review`
- **Commit**: `docs(session): session 87 assessment and docs`

---

## Execution Strategy

### Parallelization Plan

After Act 2 (scoring unification, must be sequential):

```
TRACK A (worktree: session-87/compare)     TRACK B (worktree: session-87/main-fixes)
├── Act 3: Compare summary view             ├── Act 5: Discoveries improvements
├── Act 4: Shareable result page             └── Act 6: Identity card fixes
└── merge back to main                       └── merge back to main
```

**Track A** touches `app/compare_routes.py` + `tests/test_compare.py`
**Track B** touches `app/main.py` + `tests/test_discoveries.py`
No file overlap → safe to parallelize via worktree-isolated subagents.

### Merge Order
1. Track A (docs changes) first
2. Track B second
3. `./scripts/merge.sh session-87/compare session-87/main-fixes`
4. Run `make test-fast` after merge

### /clear Discipline
- /clear after EVERY act (Acts 1-7)
- Re-read act-specific section of prompt after each /clear
- Never rationalize skipping /clear (Lesson 89)

### Skills to Use
- `/ux-review` after each screenshot batch (Acts 4b, 5b, 6b, 7)
- `/session-review` at session end (Act 7)
- TaskCreate for tracking progress across acts

---

## Key Files

| File | Acts | Lines |
|------|------|-------|
| `core/confidence.py` (NEW) | 2a | ~80 |
| `core/neighbors.py` | 2b | ~416 |
| `app/compare_routes.py` | 2c, 3, 4 | ~4,642 |
| `app/main.py` | 2d, 5, 6 | ~23,000 |
| `tests/test_confidence.py` (NEW) | 2a | ~60 |
| `tests/test_compare.py` | 3, 4 | ~650 |
| `tests/test_discoveries.py` | 5 | ~200 |
| `docs/session_context/session-87-context.md` | ref | created |
| `docs/prompts/session-87-prompt.md` | 1 | to create |
| `docs/session_logs/session-87-log.md` | 1-7 | to create |
| `docs/assessments/session-87-assessment.md` | 7 | to create |

## Verification Checklist

- [ ] `make test-fast` passes after each act
- [ ] Distance 1.13 produces identical confidence_pct everywhere
- [ ] Compare: summary shows Netanel FIRST for Purim photo
- [ ] Shareable: "Could this be..." framing, 200px faces
- [ ] Discoveries: sorted by confidence, filter by photo works
- [ ] Identity card: "Faces" button → gallery with 2 crops → Detach visible
- [ ] All UI verified in Claude Chrome with screenshots
- [ ] `/ux-review` run on all screenshots
- [ ] `/session-review` run at session end
- [ ] OG tags verified via view-source

## Harness Gap: Why Session Artifacts Were Missed in Planning

**Root cause**: No rule or lesson explicitly states that planning sessions must create context/prompt/log files BEFORE implementation begins. The existing rules (prompt-decomposition.md, session-context-integration.md) describe WHAT to create but don't enforce WHEN — and the planning phase felt like "pre-work" rather than "the session." The /clear discipline, subagent strategy, and skill usage (ux-review, session-review) were also not mentioned in the initial plan draft because there's no checklist that forces their inclusion.

**Fix (Lesson 100)**: Add to `tasks/lessons/harness-lessons.md`:
- Every session plan MUST include: context file, prompt file, session log, /clear points, verification strategy, skills to invoke (ux-review, session-review), and subagent/worktree strategy
- This checklist should be validated before exiting plan mode

**Fix (Rule update)**: Consider adding a planning-checklist rule to `.claude/rules/` that triggers during plan mode. Candidate: `.claude/rules/planning-checklist.md`.

## Mandatory Session Outputs
- `docs/session_context/session-87-context.md` (created during planning, with breadcrumbs)
- `docs/prompts/session-87-prompt.md` (Act 1)
- `docs/session_logs/session-87-log.md` (Act 1, updated throughout)
- `docs/assessments/session-87-assessment.md` (Act 7)
- `docs/screenshots/session-87/` (browser verification evidence, Acts 4b/5b/6b/7)
- Updated `SESSION_LOG.md`, `ALGORITHMIC_DECISIONS.md`, `CHANGELOG.md`, `ROADMAP.md`
- Updated `tasks/lessons.md` + `tasks/lessons/harness-lessons.md` (Lesson 100)
- `/ux-review` results from each screenshot batch
- `/session-review` final evaluation
