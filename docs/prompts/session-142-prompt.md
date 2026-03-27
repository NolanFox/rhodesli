# Session 142: Interactive Feedback Session

## Context
User will browse the live site and give real-time feedback. Fix everything in-session.
See `docs/session_context/session-142-context.md` for predecessor state.
**Codex CLI audit MANDATORY after all fixes** (HD-030, enforced by stop-gate).

## Phase 0: Setup
```bash
echo "142" > .claude/current_session.txt
echo "interactive" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline (~3815 tests)
```
Create feedback file immediately:
```bash
touch docs/feedback/session-142-feedback.md
```

## Phase 0b: Harness Gap Fix (parallel subagent — run during setup)
Launch a worktree subagent to fix any harness compliance gaps from recent sessions:
- Audit sessions 138-141 for missing files (prompts, contexts, codex audits, assessments, logs)
- Backfill any missing files from assessment content or git history
- Verify SESSION_HISTORY has entries for all sessions
- Verify BACKLOG items closed match ROADMAP completed items
- Commit on branch `session-142/harness-gaps`
This runs in background while you wait for user feedback.

## Interactive Feedback Protocol
This session is FEEDBACK-DRIVEN. The harness is at `.claude/rules/interactive-session-feedback.md`.

### On receiving ANY feedback:
1. **Acknowledge immediately**: "Got it, FB-NNN"
2. **Log via background subagent** to `docs/feedback/session-142-feedback.md`:
   ```
   ### FB-NNN: [Title]
   - **Severity:** P0/P1/P2/P3
   - **Context:** [What user was doing, what happened, what should have happened]
   - **Screenshot:** [if captured]
   - **Root cause:** [if identified]
   - **Fix:** IN PROGRESS
   - **Commit:** [hash when fixed]
   ```
3. **Assign severity** (P0 = broken, P1 = bad UX, P2 = polish, P3 = nice-to-have)
4. **Fix at next commit point** — do NOT defer to BACKLOG

### Parallelization strategy:
- **Independent fixes** (different files): Launch parallel worktree subagents
- **Dependent fixes** (same file): Fix sequentially, smallest first
- **Batch codex audit** after all fixes in a round (not per-fix)

### Between feedback rounds:
- If user is quiet, proactively browse production READ-ONLY and note issues
- Run `/simplify` on any code changed in the session
- Keep context lean — `/clear` between major fix rounds

## Codex Audit (MANDATORY — enforced by stop-gate)
After ALL feedback fixes are complete:
1. `codex exec --full-auto "Audit [changed files]. P0/P1/P2/P3."`
2. Fix P0/P1, evaluate P2, note P3
3. Save to `docs/session_context/session-142-codex-audit.md` with provenance header

## Session End Checklist
- [ ] ALL FB entries in `docs/feedback/session-142-feedback.md` have disposition FIXED
- [ ] Zero items deferred to BACKLOG (unless user explicitly approved)
- [ ] `make test-fast` passes
- [ ] Codex audit saved (`docs/session_context/session-142-codex-audit.md`)
- [ ] Assessment (`docs/assessments/session-142-assessment.md`)
- [ ] Session log (`docs/session_logs/session-142-log.md`)
- [ ] CHANGELOG, ROADMAP, BACKLOG, SESSION_HISTORY updated
- [ ] `git push origin main` + deploy verified
- [ ] Browser verify production
- [ ] `git log origin/main..HEAD` is empty
