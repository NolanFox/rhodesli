# Session Defaults — Never Repeat These Instructions

Triggers: At the start of any implementation session.

## These are ALWAYS true. The user should NEVER have to say them.

### Execution
- **Parallelize** via worktree subagents for independent file changes
- **/clear between phases** — commit first, /clear immediately, no exceptions
- **Every change gets tests** — happy path + failure + regression
- **Zero regressions** — `make test-fast` must pass before every commit
- **Browser automation is READ-ONLY on production** (Lesson 149)

### Frozen Files (never modify)
- `core/neighbors.py`, `core/pfe.py`, `data/*` files

### Session End (mandatory, every session)
1. Assessment: `docs/assessments/session-NN-assessment.md`
2. CHANGELOG: increment version
3. ROADMAP + SESSION_HISTORY: update both
4. BACKLOG: close done items, add new items
5. Deploy: `git push origin main`, verify health 200
6. Browser verify: landing, people grid, person page, compare, estimate, 404
7. `git log origin/main..HEAD` must be empty
8. Run /session-review skill

### Skills (use without being asked)
- /session-review — at session end
- /ux-review — after any browser screenshots
- /simplify — after implementation phases

### Session Init (first actions, every session)
```bash
echo "NN" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline
```
Create session log immediately.

### Codex Audit
- Run as background subagent during implementation
- Write findings to `docs/session_context/session-NN-codex-audit.md`
- Triage: P0/P1 fix immediately, quick wins implement, rest BACKLOG

## Why This Exists (Session 127 — HD-029)
User had to repeat the same instructions in Sessions 125, 126, and 127.
These are operational procedures, not ad-hoc requests. They are now the
DEFAULT behavior. Prompts should only contain session-specific work items.
