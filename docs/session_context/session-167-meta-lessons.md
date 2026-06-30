# Session 167 — Meta-Lessons (live log of the parallel-autonomy experiment)

Running record of what we learn about running a 5-track Opus-orchestrated /
Codex-coded / Codex-audited session mostly autonomously. Finalized into
`tasks/lessons/harness-lessons.md` at session end.

## Tooling / environment frictions
- **M1 — `timeout` is not on macOS.** `timeout 420 codex ...` → `command not found`.
  Use `gtimeout` (coreutils) if installed, or background the process. Cost: 1 cycle.
- **M2 — `codex exec` audits run >2 min, exceeding the Bash default 120 s timeout.**
  Foreground `codex exec` gets SIGTERM at 2 min (exit 143). Must run with Bash
  `run_in_background: true` OR pass an explicit longer `timeout`. Note: a plan/codebase
  audit that actually reads files takes ~3–6 min.
- **M3 — `nohup codex ... & ; echo $!` makes the launcher return instantly**, so the
  harness "background command completed (exit 0)" notification is the *launcher*, not
  codex. The real codex keeps running detached. To know when codex is actually done,
  poll its output file or `pgrep -fl "codex exec"`. Cleaner: run `codex exec` itself as
  the backgrounded Bash command (not wrapped in nohup+&) so the harness tracks it.

## Stop-gate friction (mid-session)
- **M4 — The Stop gate blocks turn-end on missing `session-NN-assessment.md` AND
  `session-NN-codex-audit.md`, even when the session is legitimately mid-flight** (agents
  still running). Resolution that satisfies the gate honestly: write a PROVISIONAL
  assessment marked IN PROGRESS, and run a real Codex audit of the *plan/scaffolding*
  (high-ROI anyway — audit at scope boundaries, fox-genealogy lesson). Both are genuine,
  not theater.

## What's working
- **M5 — The parallel Opus+Codex pattern is observably live.** Within ~10 min of
  dispatch, Track D's lead was already running its OWN `codex exec` audit (quoting AD-243,
  the residence-distance table, the toothy sycophancy guard, Lesson 174). Subagents
  successfully cd into their worktree, drive Codex, and self-audit as instructed.
- **M6 — Route-module decomposition is what makes this parallelizable.** Because each
  feature is a separate `app/<x>_routes.py` self-registering via `from app.main import rt`,
  the merge conflict surface collapses to one `main.py` import line (Track C only) + the
  shared doc files. Monolithic `main.py` (Lesson 88) would have forced these sequential.

## Open questions being tested
- **Q1 — worktree+venv test isolation:** does `pytest` from a worktree import the
  worktree's `app/` or the main repo's? (`app` is NOT pip-installed editable.) The plan
  audit is checking conftest/pytest config now. If it imports main-repo `app/`, every
  track's "tests pass" is meaningless. CRITICAL — resolve before trusting any track's green.
- **Q2 — merge ordering:** docs-only vs code; main.py import line; shared
  ROADMAP/BACKLOG/CHANGELOG reconciliation. merge-resolver pattern.
- **Q3 — coordination overhead vs throughput:** is the orchestrator time spent dispatching
  + reviewing + merging less than the parallel speedup? (Answer at session end.)

## Resolved
- **Q1 → RESOLVED (isolation works).** From a worktree with venv active,
  `import app.main` resolves to `<worktree>/app/main.py` (verified for s167-ops-hardening),
  NOT the main repo. Reason: cwd is `sys.path[0]` and `app` is not pip-installed editable.
  So worktree pytest tests worktree code. No agent warning needed; the default is correct.
  (Caveat: agents MUST run pytest from the worktree cwd, which the briefs already require.)

## The session-level plan audit earned its keep (STRONG)
Running a Codex plan-audit at the dispatch boundary (before deep track work) caught
**2 P0 + 4 P1 + 4 P2** real coordination risks, and I corrected the 4 live agents
mid-flight via SendMessage. This is the fox-genealogy "audit-at-boundaries = HIGH ROI"
pattern, validated again. Highest-value catches:
- **M7 — Brief vs PRD contradiction:** my Track B brief said ".ged upload" but PRD-055
  scopes file-upload OUT and existing xfail tests are PASTE-oriented. An unattended agent
  would have built the wrong thing + broken the xfail contract. Lesson: when a brief
  paraphrases a PRD, the agent must treat the PRD as authoritative — and the orchestrator
  should diff brief-against-PRD BEFORE dispatch.
- **M8 — Cross-repo orchestration is blocked by deliberate deny rules.** Track E (rhodes-wiki)
  inherits this session's `.claude/settings.json` DENY on Write/Edit/python to
  `/Users/nolanfox/rhodes-wiki/**` (the cross-repo safety invariant). A subagent of repo X
  CANNOT write to repo Y when Y is deny-listed. **Multi-repo parallel sprints need one
  session PER repo** (or an explicit, user-approved settings relaxation). Track E is
  deferred to a dedicated rhodes-wiki session; its read-only PLAN is the handoff.
- **M9 — Shared-doc freeze was missing from the briefs.** I told tracks to test+commit but
  not to AVOID ROADMAP/BACKLOG/CHANGELOG/SESSION_HISTORY/conftest/components. Parallel
  agents each editing those = guaranteed merge conflicts. Fix: the dispatch template MUST
  include an explicit "shared-doc freeze; orchestrator reconciles" clause. Sent as a
  mid-flight correction; should be pre-baked next time.
- **M10 — "No $ spend" needs to be mechanical, not behavioral.** Worktrees didn't get `.env`
  (raw `git worktree add`, not setup-worktree.sh — lucky), but agents can still
  `load_dotenv(main/.env)` by absolute path. A real spend cap must be script-enforced
  (`--max-usd`/`--max-calls` + ledger), not a sentence in the brief.

## Orchestration-overhead tally (running)
Dispatch + isolation-verify + plan-audit + 5 course-correction messages ≈ the coordination
cost so far. The plan audit (caught 10 findings) clearly paid for itself. Net read at
session end: did parallel throughput beat this overhead? (TBD as tracks land.)
