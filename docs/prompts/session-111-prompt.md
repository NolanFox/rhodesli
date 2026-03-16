# Session 111 — Interactive Fox Family Upload Review + Fix Sprint

## Context
- Predecessor: Session 110 (James Fields UX bug sprint — merge/override/confirm fixes deployed)
- Session 110 assessment: Next session should verify James Fields merge workflow
- Fox Family Archive: ~636 photos, ~3433 identities, ~95 confirmed
- Mode: **Interactive** — Nolan drives triage in browser, Claude fixes or documents

## Pre-Requisites
- Read `tasks/lessons.md` + `tasks/todo.md`
- Read `docs/feedback/2026-03-14-fox-triage-round2.md` (FB-120 through FB-146)
- Read `docs/BACKLOG.md` open items
- Set `.claude/current_session.txt` to `111`
- Set `.claude/session_mode.txt` to `interactive`
- Open production site in browser: https://rhodesli.nolanandrewfox.com/c/fox-family/

## Part 1: Interactive Triage (Nolan-Driven)

Nolan will navigate the Fox Family upload review in the browser. During this phase:

### Your Responsibilities
1. **Listen and document** — Every piece of feedback gets an FB-NNN entry
2. **Reproduce immediately** — When Nolan reports a bug, try to reproduce via browser tools or code inspection
3. **Quick fixes (<5 min)** — Fix immediately, commit, deploy, verify. Tell Nolan when it's live.
4. **Larger fixes** — Log with severity, root cause analysis, and estimated effort. Don't attempt during Part 1.
5. **Data observations** — If Nolan identifies wrong clusters, bad matches, or data quality issues, log them with identity IDs and expected behavior

### Documentation Format
For each feedback item, create an entry in `docs/feedback/session-111-feedback.md`:
```markdown
### FB-NNN: [Title]
- **Severity:** P0/P1/P2/P3
- **Context:** [What Nolan was doing, what happened, what should have happened]
- **Screenshot:** [if captured]
- **Root cause:** [if identified]
- **Fix:** [FIXED in session / BACKLOG — effort estimate]
- **BACKLOG:** [ID if deferred]
```

### What to Watch For
- Session 110 fixes: Do merge/override/confirm work on James Fields?
- Similar panel behavior after merge
- Loading indicators on slow actions
- Cross-community data pollution (Rhodes items in Fox Family)
- Speed-run vs person page vs photo page navigation flow
- Cluster quality — are ML matches good? Bad? What patterns?
- Any new bugs from Session 110 changes

## Part 2: Fix Sprint (Claude-Driven)

After Nolan finishes providing feedback, execute fixes in priority order:

### Execution Rules
1. Fix P0 bugs first, then P1, then P2
2. Commit after every fix (conventional commits: `fix(scope): description`)
3. Run `make test-fast` before every commit
4. Deploy after each batch of related fixes
5. Browser-verify each fix on production
6. /clear between major fix batches (every 3-4 commits)

### For Each Fix
- Write test FIRST (TDD)
- Implement fix
- Run tests
- Commit
- Update `docs/feedback/session-111-feedback.md` status

### For Items NOT Fixed This Session
1. Add to `docs/BACKLOG.md` with:
   - Clear description of the issue
   - Root cause if known
   - Estimated effort
   - Source breadcrumb: `Source: Session 111 FB-NNN`
2. Add to ROADMAP if it blocks a roadmap item
3. Update the feedback file entry: `Fix: BACKLOG — [effort] — [BACKLOG ID]`

## Phase 3: Harness Outputs (10 min)

1. **Assessment**: `docs/assessments/session-111-assessment.md`
   - List every FB item with FIXED/DEFERRED status
   - Evidence for each fix (test name, commit hash)
   - Red flags and next-session priorities
2. **Session log**: `docs/session_logs/session-111-log.md`
3. **BACKLOG**: All deferred items wired with breadcrumbs
4. **ROADMAP**: Update completed items, move to Recently Completed
5. **CHANGELOG**: v0.99.16 or appropriate version
6. **Feedback index**: Update `docs/feedback/FEEDBACK_INDEX.md`
7. Verify: `git log origin/main..HEAD` is empty (all pushed)

## Verification Checklist

- [ ] All FB items from Part 1 documented in `docs/feedback/session-111-feedback.md`
- [ ] P0 fixes deployed and browser-verified
- [ ] P1 fixes deployed and browser-verified (or documented if deferred)
- [ ] BACKLOG entries for all deferred items
- [ ] Assessment written with per-item evidence
- [ ] All tests pass (`make test-fast`)
- [ ] `git log origin/main..HEAD` is empty

## Reference: Known Open Fox Family Issues (from BACKLOG)

| ID | Severity | Summary |
|----|----------|---------|
| COMMUNITY-015 | P1 | Internal links don't include community prefix |
| FB-151 | P2 | Suggestion name truncated in Speed Loop |
| FB-161 | P2 | Dismissed identities re-appear in speed-run |
| FB-165 | P2 | Speed-run cards need face/photo toggle |
| UX-067 | P2 | No "Recently Confirmed" section |
| UX-062 | P2 | Dense photos need batch confirmation |
| CROP-001 | P2 | Some Fox Family crops show as grey boxes |
| UX-093 | P0 | Speed-run slower than manual New Matches browse |
| UX-086 | P0 | No connected flow: speed-run ↔ photo ↔ face tagging |
| UX-089 | P1 | Speed Loop exists but nearly unreachable |
| UX-090 | P1 | Speed Loop face boxes misaligned |
| BUG-001 | P0 | Speed Loop tags don't save |
