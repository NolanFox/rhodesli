---
name: reference-multimodel-sprint-skill
description: The multimodel-sprint skill — how to run autonomous sprints with the architect/orchestrator/coder/auditor split. Cross-repo (rhodesli + fox-genealogy).
metadata: 
  node_type: memory
  type: reference
  originSessionId: f1eee225-738e-483c-b60e-8a8fe71184a1
---

`~/.claude/skills/multimodel-sprint/SKILL.md` (user-level, shared across rhodesli + fox-genealogy)
codifies the Fable-architect / Opus-orchestrator / Codex-coder / independent-auditor pattern the user
prefers for autonomous sprints. Invoke `/multimodel-sprint` (or state the roles) when the user asks to
"move the project ahead" / run an overnight or autonomous sprint / uses the Fable-Opus-Codex framing.

Validated Rhodesli Session 168 (verdict 7.5/10). The one load-bearing rule: **an independent
fresh-context audit of the ACTUAL diff is a HARD pre-push gate — the orchestrator NEVER audits its own
session's output** (independence of context, not model identity, is the active ingredient). Other core
rules: bound the coder's verify loop ("targeted tests only, not make test-fast"); long subagents stall
→ bound scope + fresh fallback auditor; simulate CI's *constraints* (missing deps AND data files), not
just its commands.

Mechanical helpers (rhodesli): `scripts/bootstrap-gate-files.sh <NN>` (gate-file skeletons first),
`scripts/check_ml_suite_ci_safe.py` (dep-subtraction), `scripts/simulate_ci_data.py` (data-subtraction
via HEAD worktree). See HD-036, `docs/session_context/session-168-meta-lessons.md`, harness Lessons
212–218. Research-repo (fox-genealogy) adaptation is in the skill: dives = vault gap-analysis, coder =
source-* skill tasks, auditor = [[gps-evaluator]] before tier→confirmed. Related: [[feedback_codex_iteration]], [[feedback_ai_tool_audit]].
