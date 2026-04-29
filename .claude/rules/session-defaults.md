# Session Defaults — Never Repeat These Instructions

Triggers: At the start of any implementation session.

## These are ALWAYS true. The user should NEVER have to say them.

### Execution
- **Parallelize** via worktree subagents for independent file changes.
  On Opus 4.7, explicitly instruct parallelization in prompts — 4.7 spawns
  fewer subagents by default than 4.6 did.
- **/clear between phases** — commit first, /clear immediately, no exceptions.
  Opus 4.7's MRCR v2 recall drops to 32.2% (vs 4.6's 78.3%); aggressive /clear
  is MORE important on 4.7, not less. Transcript gate now blocks at 600 lines
  (was 800) to reflect this.
- **Every change gets tests** — happy path + failure + regression
- **Zero regressions** — `make test-fast` must pass before every commit
- **Browser automation is READ-ONLY on production** (Lesson 149)

### Opus 4.7 Behavioral Adjustments (2026-04-18)
- **Literal instruction following**: 4.7 does exactly what it's asked, not
  what it infers. Session prompts need explicit acceptance criteria, not
  vibes. Ambiguous "fix the UI issue" will fix only that exact issue —
  related cleanup must be listed.
- **Adaptive thinking cues**: inject "think carefully, step-by-step" for
  data-integrity/ML work; inject "respond quickly" for UX tweaks. No
  fixed thinking budgets — 4.7 adapts.
- **Default effort is xhigh**; reserve `max` for data-integrity audits
  (the Lesson 153–156 category of bug).
- **Token inflation**: 4.7's tokenizer uses 1x–1.35x more tokens per unit
  of English text. CLAUDE.md stays ≤ 80 lines, docs stay ≤ 300 lines.

### Frozen Files (never modify)
- `core/neighbors.py`, `core/pfe.py`, `data/*` files

### Session End (mandatory, every session) — SINGLE SOURCE OF TRUTH
**This is the canonical session-end checklist.** `verification-gate.md` and
`self-assessment.md` elaborate sub-steps but do NOT define their own sequences.
1. Assessment: `docs/assessments/session-NN-assessment.md`
2. CHANGELOG: increment version
3. ROADMAP + SESSION_HISTORY: update both
4. BACKLOG: close done items, add new items
5. Deploy: `git push origin main`, verify health 200
6. Browser verify: landing, people grid, person page, compare, estimate, 404
7. `git log origin/main..HEAD` must be empty
8. Memory backup: automated by stop-gate.sh (runs `scripts/backup-memory.sh`).
   Manually invoke if the hook reports failure.
9. Run /session-review skill

### Skills (use without being asked)
- /session-review — at session end
- /ux-review — after any browser screenshots
- /simplify — after implementation phases

### Session Init (first actions, every session)
```bash
echo "NN" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast                  # Baseline
bash scripts/harness-check.sh   # Verify hooks/memory/doc caps are healthy
```
Create session log immediately. If `harness-check.sh` fails, stop and fix
BEFORE starting the session — a broken harness wastes more time than it saves.

### Dual-Audit Protocol (MANDATORY after every phase) — HD-030, Session 137
After completing each implementation phase (not at session end — after EACH phase):

1. **Codex CLI audit** (independent, fresh context — uses gpt-5.5 + xhigh per `~/.codex/config.toml`; verify pin via `.claude/rules/codex-model-pin.txt`):
   ```bash
   codex exec "Audit [changed files]. Security, code quality, test quality. P0/P1/P2/P3 report."
   # NEVER use --full-auto — it hangs on stdin (Sessions 152, 153, 153b).
   # Fallback if `codex exec` itself hangs: substitute a Claude general-purpose subagent.
   ```
2. **Claude Code reviews** the Codex findings:
   - P0/P1: fix immediately before next phase
   - P2: fix if quick (<5 min), otherwise BACKLOG with justification
   - P3: note in session log, no action required
   - **Claude may REJECT** Codex suggestions with written reasoning (e.g., "false positive because X")
3. **Iterate** if fixes introduce new issues — re-run Codex on the fixes
4. **Save** to `docs/session_context/session-NN-codex-audit.md` with provenance header:
   ```
   **Auditor**: Codex CLI v0.115.0 (model)
   **Agent type**: Independent (fresh context)
   **Phase**: [which phase was audited]
   **Date**: [ISO date]
   ```
5. Log ALL audit tool usage per `.claude/rules/ai-tool-audit.md`

**Why both**: Claude finds design/structural issues. Codex finds runtime/behavioral issues.
Session 137 proved neither catches what the other does. The cost is ~5 min per phase.

### Post-Merge Checker Subagent (R1 — Session 133 research)
After merging parallel worktrees:
- Launch a **checker subagent** on the merged code
- Checker reviews: auth guards on new POST routes, data integrity,
  test coverage delta, no hardcoded paths leaked
- This is a Claude subagent for speed, supplementing (not replacing) Codex

### Parallelization Decision (R4 — Session 133 research)
**Parallel** (subagents + worktrees): independent bug fixes, test writing, docs + code simultaneously
**Sequential** (same agent): anything touching app/main.py, data migrations, identity write paths
**Agent teams** (experimental, 2026): cross-layer features spanning auth + upload + UI + tests.
Enable per-session with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. Candidates:
TOOLS-002 (ML service extraction), WORKSPACE-001 (personal archive).

## Why This Exists (Session 127 — HD-029)
User had to repeat the same instructions in Sessions 125, 126, and 127.
These are operational procedures, not ad-hoc requests. They are now the
DEFAULT behavior. Prompts should only contain session-specific work items.
