# Session 150 — Mobile Polish + Quick Wins + Tool Foundations

**Mode:** Implementation (autonomous)
**Predecessor:** Session 148d (Codex fixes, Gemini structured output, deploy)
**Context:** `docs/session_context/session-150-context.md`

## Orientation

Read at session start:
- `tasks/lessons.md` + `tasks/todo.md`
- `docs/session_context/session-150-context.md`
- `ROADMAP.md` current state

Set session: `echo "150" > .claude/current_session.txt && echo "implementation" > .claude/session_mode.txt`
Baseline: `source venv/bin/activate && make test-fast`

---

## Phase 1: Quick Wins — ENV-001 + Browser Verify (~20 min)

### 1a: ENV-001 — Stop Sentry in local dev
- `app/main.py:170-179`: Guard Sentry init — skip when `SENTRY_ENVIRONMENT=development`
- Add `SENTRY_ENVIRONMENT=development` to `.env`
- Add `SENTRY_ENVIRONMENT` to `.env.example` with comment
- Test: Sentry not initialized when env=development, still works when env=production

### 1b: Browser-verify PRD-059 Phase 4 (identity inference)
- 18 PENDING suggestions in Supabase — find person pages that have them
- Navigate in Chrome, screenshot the evidence panel UI
- Verify: signal bars, accept/reject/needmore buttons, admin-only visibility
- Save screenshots to `docs/screenshots/session-150/`
- Log any bugs found as FB-NNN items

**Commit after Phase 1. /clear.**

---

## Phase 2: Mobile Responsive Sprint (~90 min)

Focus on the 4 pages people share in family group chats. Admin pages stay desktop-only.

### 2a: Landing page (UX-134 — P1)
- Fix horizontal overflow at 375px (scrollWidth=780 vs clientWidth=375)
- Root cause: likely a grid or flex container missing `max-w-full` or `overflow-hidden`
- Test at 375px viewport with Playwright

### 2b: Person page
- Face strip: horizontal scroll with `overflow-x-auto` instead of wrapping/overflowing
- Identity card: stack vertically on mobile (badges below name, not beside)
- Action buttons: minimum 44px tap targets (WCAG AA)
- Evidence panel (new from PRD-059): verify it doesn't overflow on mobile

### 2c: Photo page
- Face overlay labels: ensure they don't overlap at mobile widths (UX-123)
- Photo scales to viewport width with `max-w-full`
- Face cards below photo: 1-column on mobile, 2-column on sm+

### 2d: Compare modal
- Side-by-side → stacked on mobile (COMPARE-001)
- Swap button: make it a clear toggle, not a tiny icon
- Result text: readable without horizontal scroll

### 2e: Global mobile fixes
- All clickable elements: min 44px height (UX-075)
- Sidebar: verify hamburger menu works, close on outside tap
- Toast notifications: visible above mobile nav, not hidden behind it

### Parallelization: 2a-2d are independent files — use 3-4 WORKTREE subagents.
- Track A: Landing page (page_routes.py + main.py styles section)
- Track B: Person page (person_routes.py, identity_routes.py)
- Track C: Photo page (photo_routes.py)
- Track D: Compare modal (compare_routes.py)
- Track E (same agent): Global fixes (main.py CSS section, tested after merge)

### Testing
- Playwright tests at 375px viewport for each page
- Structural test: no element wider than viewport at 375px on key pages
- `make test-fast` after merge

### Codex audit after merge — scope: all changed route files, focus on responsive regressions.

**Commit after Phase 2. /clear.**

---

## Phase 3: TOOLS-005 Flow 2 — Text Hints (~45 min)

The smallest, most impactful Estimate v2 feature. One textarea, maximum user value.

### 3a: Add text hints textarea to /tools/estimate
- Below the photo upload field, add: "Optional: Tell us what you know about this photo"
- Placeholder: "e.g., This is my grandmother in the 1940s, taken in Rhodes before the war"
- Form field name: `text_hints`

### 3b: Wire hints into Gemini prompt
- In `app/estimate_routes.py` upload handler (~line 682):
  - Accept `text_hints: str = ""` form parameter
  - Pass to `build_extraction_prompt()` as `verified_facts={"notes": text_hints}` if non-empty
- Add `user_context` column to `gemini_api_calls` table (SQL migration)
- Store the user's text hints in the API call log

### 3c: Show hints in results
- Display "Your context: {text_hints}" above the Gemini results so user sees it was used

### 3d: Tests
- Make the 4 xfail tests in `tests/test_estimate_v2_text_hints.py` pass
- Add: hints text appears in Gemini prompt when provided
- Add: hints text stored in gemini_api_calls.user_context
- Add: empty hints doesn't break existing flow

### Parallelization: WORKTREE — only touches estimate_routes.py and tests.

### Codex audit — scope: estimate_routes.py changes, prompt injection risk from user text.

**Commit after Phase 3. /clear.**

---

## Phase 4: Batch Fader Event Context (~30 min)

### 4a: Write batch script
- `scripts/batch_event_context.py`
- Query Fader photo_ids from `photo_communities` where `community_id = '1a2c23d6-fc5e-4d0e-b020-1721579485bf'`
- For each photo: load image bytes from R2, call Gemini with identification preset + response_schema
- Store results: upsert to `date_labels` table with event_context and relationship_inference in the JSONB `data` column
- Rate limit: 4 calls/minute (Gemini free tier) or 15/minute (paid)
- Resume support: skip photos that already have event_context in date_labels
- Log every call to `gemini_api_calls`

### 4b: Dry run on 5 photos
- Run with `--limit 5 --dry-run` to verify prompt + schema
- Then run with `--limit 5` to verify real API calls + Supabase writes
- Verify results in Supabase

### 4c: Full run (if dry run passes)
- Run on all 147 Fader photos
- Cost estimate: ~$1.50
- Expected: ~30 min at 4/min rate limit

### Parallelization: Sequential — needs Gemini API key, rate limiting, Supabase writes.

**Commit after Phase 4. /clear.**

---

## Phase 5: TOOLS-006 PRD (~20 min)

### 5a: Write PRD
- `docs/prds/060_self_service_archive.md`
- Problem: Communities other than Rhodes want to use the platform
- User flows: Create archive → Upload photos → ML processing → Share with family
- Build on WORKSPACE-001 (personal archive auto-creation on signup)
- Scope: what's in v1 vs deferred
- Data model: reuse existing community + photo_communities tables

### 5b: Update BACKLOG
- Link TOOLS-006 to the new PRD
- Add work items with estimates

### Parallelization: Can run as background WORKTREE subagent during Phase 4.

**Commit after Phase 5.**

---

## Phase 6: Session Close

1. Assessment: `docs/assessments/session-150-assessment.md`
2. Update CHANGELOG (increment version)
3. Update ROADMAP + BACKLOG (close done items, add new)
4. Deploy: `git push origin main`, verify health 200
5. Browser verify: landing (mobile), person page (mobile), compare (mobile), estimate (text hints)
6. `git log origin/main..HEAD` must be empty
7. Memory backup: `./scripts/backup-memory.sh`
8. Run /session-review skill

---

## Parallelization Plan

```
Phase 1 (sequential — ENV-001 small + browser verify needs Chrome)
  ↓
Phase 2 (PARALLEL worktrees: Track A/B/C/D mobile fixes → merge → Track E global)
  ↓                    ↓
Phase 3 (WORKTREE)   Phase 4 (sequential — Gemini API)
  ↓                    ↓ (Phase 5 background during Phase 4)
  merge all
  ↓
Phase 6 (sequential — session close)
```

## Codex Audit Plan
- After Phase 2 merge: audit all changed route files for responsive regressions
- After Phase 3: audit estimate_routes.py for prompt injection from user text
- After Phase 4: audit batch script for API key handling, error recovery
- Session-end: full audit of all changed files

## Success Criteria
- [ ] Sentry silent in local dev (ENV-001)
- [ ] Evidence panel browser-verified with screenshots (PRD-059 Phase 4)
- [ ] Landing page no horizontal overflow at 375px (UX-134)
- [ ] Person, photo, compare pages usable at 375px
- [ ] All tap targets >= 44px on mobile pages
- [ ] Text hints field on /tools/estimate, wired to Gemini prompt
- [ ] 4 xfail estimate_v2_text_hints tests passing
- [ ] Fader event context data in Supabase (5+ photos minimum, 147 target)
- [ ] TOOLS-006 PRD written
- [ ] All tests pass, deployed, browser verified (mobile + desktop)
