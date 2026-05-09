# Session 157 Log

**Date**: 2026-05-08
**Mode**: Implementation (truncated — usage-limit blocker)
**Predecessor**: Session 156 (Day 1 of PRD-063)
**Successor**: Session 157b (continuation — full Day 2 + Track A2 + Track E + Codex audit)
**Final successor planned**: Session 158 (PRD-063 Day 3 cutover)
**Critical deadline**: 2026-05-29 (Supabase free-tier 1.1 GB ceiling)

## What this session shipped

Only AD-244 entry committed to origin/main. The two parallel Track A subagents
(launched as `general-purpose` with `isolation: "worktree"`) both hit
Anthropic's user-level usage limit AT LAUNCH and returned within 5-10 seconds
each, having done **zero work** (0-2 tokens used per agent, no commits).

This locked the orchestrator out of the rest of Track A (CI-COMPARE fix,
TEST-ISOLATION fix, notes backfill, Codex audit) and made Track B / Track E
non-starters for the remaining session budget. Single-thread main work was
restricted to capturing the highest-value, lowest-cost artifact: AD-244.

## Phase checklist

- [x] **Phase 157-0**: Carry verification (v2 tables 21,998 / 6,741 / 9 ✅; Harry 5 anchors v=14 ✅; Belle Isle INBOX 1 note ✅)
- [x] **Track A1.1**: AD-244 entry — **inline on main** (not subagent), commit `fb4b200f`
- [ ] **Track A1.2**: NOTES-BACKFILL-156 — DEFERRED to 157b
- [ ] **Track A1.3**: Codex audit of Session 156 commits — DEFERRED to 157b
- [ ] **Track A2.1**: CI-COMPARE-FAIL-156 fix — DEFERRED to 157b
- [ ] **Track A2.2**: TEST-ISOLATION-156 fix — DEFERRED to 157b
- [ ] **Track B1**: Full backfill since cutover — DEFERRED to 157b
- [ ] **Track B2**: Dual-read helper + 4 tests — DEFERRED to 157b
- [ ] **Track B3**: Query timing — DEFERRED to 157b
- [ ] **Track B4**: Confidence assessment — DEFERRED to 157b
- [ ] **Track E**: GEDCOM upload UAT — DEFERRED to 157b (was already gated on user E1 authorization)
- [x] **Track Z**: Closeout — assessment + this log + CHANGELOG + ROADMAP + BACKLOG + 157b continuation prompt

## Verification gate results

| Gate | Method | Result |
|---|---|---|
| Carry verification | direct Supabase queries | ✅ PASS — v2 21,998/6,741/9; Harry 5/v14; Belle Isle INBOX/1 note |
| AD-244 in ALG_DECISIONS | `grep "^### AD-244" docs/ml/ALGORITHMIC_DECISIONS.md` | ✅ PASS |
| `make test-fast` | xdist parallel | ✅ PASS (4246) — same as 156 baseline |
| `git log origin/main..HEAD` post-push | git | ✅ EMPTY (after push of `fb4b200f`) |
| `git status` post-push | git | ✅ EMPTY |
| Track A subagents | usage-limit error | ❌ FAIL — both agents returned within 5-10s with zero work |
| Track B (Day 2 dual-read) | not run | ❌ DEFERRED |
| Track E (GEDCOM upload UAT) | not run | ❌ DEFERRED |

## Mid-session discoveries

1. **Anthropic usage-limit blocked parallel subagents**: Both Track A1 (AD-244 + notes backfill + Codex) and Track A2 (CI-COMPARE + TEST-ISOLATION) returned `You've hit your limit · resets 4:10am (America/New_York)` at launch, with 0-2 tokens consumed and no commits. The agents share the orchestrator's account budget, and the budget was already drained when the parallel calls fired. The orchestrator's main thread retained budget — that's how we landed AD-244 inline.
   - **Why this happened**: Session 156 had run heavy parallel work earlier the same day (UTC), and 157 was launched on the same account before the budget reset. Pre-launch budget check was not part of the harness.
   - **Lesson candidate**: Add a budget pre-flight check before launching parallel agents — `gh api user/account-status` equivalent if available, OR launch one agent and verify it consumes >>2 tokens before launching the second.

2. **AD-244 is the carry-the-context win even with a truncated session**: The design lineage (B3/B4/B5 commit hashes, v2 row counts, mechanism explanation, migration plan, acceptance gate for cutover) is now permanent on main. Sessions 157b and 158 can reference it without re-deriving from 156's assessment.

## Concurrency resilience (R1-R9)

- **R1 marker file**: NOT held this session (Track A is reversible; Track B Day 2 backfill commit and Track E import — both deferred — would have held it).
- **R2 optimistic concurrency**: N/A — no Supabase writes this session.
- **R3 additive only on v2**: N/A — no v2 writes this session.
- **R8 R2 namespace isolation**: N/A — no R2 writes this session.

## Commits this session (1)

| Hash | Description |
|---|---|
| `fb4b200f` | docs(session-157): AD-244 PRD-063 v2 schema design entry |

## Continuation handoff

Session 157b continuation prompt: `docs/prompts/session-157b-prompt.md`. Same scope as 157 minus AD-244 (already shipped). Re-run Phase 157-0 carry verification at start of 157b — production state could shift if a parallel genealogy session ran between sessions.

`git log origin/main..HEAD` empty after push. 4246 tests pass under xdist parallel.
