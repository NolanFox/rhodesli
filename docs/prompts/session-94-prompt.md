# Session 94: Housekeeping + Fox Family Collection Planning

**Context**: `docs/session_context/session-94-context.md`
**Predecessor**: Session 93 (`docs/assessments/session-93-assessment.md`)

## Problem Statement

Rhodesli is at v0.96.0 with 4283 tests, solid infrastructure (Postgres, Sentry,
PostHog, Resend), and a clear standalone tools roadmap (PRD-034). But housekeeping
gaps remain (stale docs, P1 UX bugs, stranded branch, unverified CI), and the
second collection (Fox family photos) needs proper planning before implementation.

This session has two modes:
1. **Interactive** (main thread): Deep planning for Fox family collection with Nolan
2. **Background** (worktree subagents): Housekeeping fixes

## Session Protocol
- Set `.claude/current_session.txt` to `94`
- Read `tasks/lessons.md` at start
- Commit after every act, `/clear` between acts (NON-NEGOTIABLE)
- Use subagents in worktrees for parallel tracks
- Run `make test-fast` before every commit
- Run `/session-review` at session end

---

## Act 0: Orient (5 min) — sequential on main

1. Read this prompt, `docs/session_context/session-94-context.md`, `tasks/lessons.md`
2. `git status`, `git log --oneline -10`, verify `make test-fast` passes
3. Set `.claude/current_session.txt` to `94`
4. Create `docs/session_logs/session-94-log.md` with phase checklist

Commit: `chore: session 94 orient`

**IMMEDIATELY /clear after this commit.**

---

## Act 1: Launch Background Tracks + Start Planning (main thread)

### Background: Launch 4 Parallel Worktree Subagents

Launch all 4 as background subagents. They work independently while the
main thread does interactive planning with Nolan.

#### Track A: P1 UX Fixes (`session-94/ux-fixes`)
**Files:** `app/page_routes.py`, `tests/test_page_routes.py`

Fix two P1 UX bugs:

**UX-042: Shareable identity page missing source photo link**
- `/identify/{id}` pages have no link to the source photo
- Add source photo thumbnail + link for each face on the identity page
- Use `face_to_photo` mapping to find the parent photo
- Add test: identity page includes photo link

**UX-134: Mobile landing page horizontal overflow**
- Landing page at 375px: scrollWidth=780 vs clientWidth=375
- Find the overflowing element (likely a wide table, grid, or image)
- Add `max-width: 100%; overflow-x: hidden` or responsive breakpoints
- Add test: no element exceeds viewport width at 375px

Run `make test-fast` before commit. Conventional commit.

#### Track B: Branch Cleanup (`session-94/branch-cleanup`)
**Scope:** Evaluate and close `session-82c/gemini-rerun` branch

1. `git log session-82c/gemini-rerun --oneline` — list all 14 commits
2. Compare each commit against what's on main now (sessions 89, 92, 93 re-did most of this work)
3. Cherry-pick anything valuable that's NOT already on main
4. If nothing new: close the branch with a commit message explaining why
5. Document decision in session log

#### Track C: CI Verification (`session-94/ci-verify`)
**Scope:** Verify GitHub Actions is running

1. `gh run list --limit 5` — check if any runs exist
2. If no runs: check `.github/workflows/test.yml` trigger configuration
3. If runs exist: check pass/fail status
4. Document findings in session log
5. If CI is broken: fix the workflow file

#### Track D: Doc Sync (`session-94/doc-sync`)
**Scope:** Update stale document headers

1. BACKLOG.md header: update version to v0.96.0, test count to ~4283
2. BACKLOG.md "Current State Summary": update all stats
3. Verify CHANGELOG.md has Session 93 entry
4. Verify SESSION_HISTORY.md has Session 93 entry
5. If any are missing: add them

Run no tests (docs-only). Conventional commit.

### Interactive: Fox Family Deep Planning (main thread)

**This is the core of the session.** Nolan will provide a brain dump about the
Fox family photo collection. Claude should:

1. **Ask Nolan for a brain dump** covering:
   - What photos exist (format, quantity, date range, condition)
   - What metadata is available (names on backs, dates, locations)
   - GEDCOM status (does one exist? what software? how complete?)
   - Who the audience is (same community? different? family-only?)
   - Cross-collection overlap (do Fox and Capeluto families share people?)
   - What "success" looks like for a Fox collection MVP
   - Geographic and temporal scope
   - Any sub-collections or organizational structure

2. **Review existing artifacts** with Nolan:
   - `docs/collections/fox_family_prep.md` — is this still accurate?
   - `docs/prds/030_multi_collection.md` — any concerns?
   - `docs/architecture/MULTI_TENANT.md` — right architecture?

3. **Iterate on the plan** — ask clarifying questions, propose alternatives,
   identify risks. Key questions to resolve:
   - Same domain or separate instance?
   - Same admin or different admins?
   - Collection-scoped browsing UX — how should it work?
   - Cross-collection identity linking — how visible to users?
   - Does Fox collection need GEDCOM enrichment? (Gemini date/location estimation)
   - What's the minimum viable onboarding? (5 photos? 50?)
   - Timeline: when does Nolan want this live?

4. **Produce artifacts:**
   - Updated `docs/prds/PRD-035_fox_family_collection.md` (or update PRD-030)
   - Implementation plan with phases and session estimates
   - Dependency map (what must be built first)
   - Data preparation checklist for Nolan

**Do NOT write code in this act.** This is planning only.

Commit planning artifacts: `docs(prds): Fox family collection PRD + implementation plan`

**IMMEDIATELY /clear after this commit.**

---

## Act 2: Merge Background Tracks (15 min) — sequential on main

After all background subagents complete:

1. Merge in order: D (docs) → C (CI) → B (branch) → A (UX)
2. Run `make test-fast` after each merge
3. Resolve any conflicts
4. Update session log with results from each track

Use `./scripts/merge.sh` for canonical merge flow.

Commit: `chore: merge session 94 housekeeping tracks`

**IMMEDIATELY /clear after this commit.**

---

## Act 3: Session Review + Assessment

1. Re-read this prompt
2. Verify all tracks completed
3. Run `/session-review`
4. Write `docs/assessments/session-94-assessment.md`
5. Update ROADMAP.md, BACKLOG.md, SESSION_HISTORY.md, CHANGELOG.md

---

## Acceptance Criteria

- [ ] Fox family PRD written with Nolan's input and implementation plan
- [ ] UX-042 fixed (identity page has source photo link)
- [ ] UX-134 fixed (mobile landing page no horizontal overflow)
- [ ] 82c branch resolved (merged or closed with explanation)
- [ ] CI status documented (running or fixed)
- [ ] BACKLOG.md header updated to v0.96.0
- [ ] All tests pass
- [ ] Assessment written with evidence
- [ ] Session log complete
