# Session 154 Log

**Date**: 2026-04-28 → 2026-04-29
**Mode**: Implementation + interactive (mixed)
**Predecessor**: Session 153b (`docs/assessments/session-153b-assessment.md`)
**Prompt**: `docs/prompts/session-154-prompt.md` (500 lines)
**Assessment**: `docs/assessments/session-154-assessment.md`
**Version shipped**: v0.99.70

## Phase checklist

- [x] Phase 0 — Setup + baseline: harness-check, make test-fast, git status
- [x] Pre-session repair (unplanned): fix 10 stale `test_hooks_clear_gate.py` failures (commit `e04e4caf`)
- [x] Track A Phase A0 — `gemini_api_calls.experiment_id` migration + retry-with-backoff
- [x] Track A Phase A1 — `gedcom_context` injection (AD-241)
- [x] Track A Phase A2 — `candidate_with_prior` iterative refinement (AD-242)
- [x] Track A Phase A3 — Detroit subset rerun (6 calls, $0.17) — gate FAILED on 02068
- [⏭️] Track A Phase A4 — full 12-photo eval — correctly SKIPPED per A3 gate
- [x] Track B Phase B1 — face-ID discrepancy resolved (worktree subagent)
- [x] Track B Phase B2 — Bessie hypothesis strengthened (worktree subagent)
- [x] Track C Phase C1 — Belle Isle citation (worktree subagent)
- [x] Track C Phase C2 — Irving anchor verification (worktree subagent)
- [x] Track E Phase E0.5 — GEDCOM bloat root-cause analysis (worktree subagent)
- [x] Track E Phase E1 — stopgap prune plan + tripwire script (worktree subagent)
- [⏸] Track E Phase E2 — prune execution — NOT EXECUTED, awaiting user authorization
- [x] Track E Phase E3 — retention script + admin endpoint + OD-013 (worktree subagent)
- [❌] Track E Phase E4 — PRD-063 GEDCOM mirror redesign — NOT WRITTEN (subagent hit usage limit)
- [⏸] Track D Phase D1 — Harry repair execution — NOT EXECUTED, 3 of 6 gates unmet
- [x] Track D Phase D2 — closeout (assessment, CHANGELOG, ROADMAP, push, memory backup)

## Verification gate (per `.claude/rules/verification-gate.md`)

| Check | Method | Result |
|---|---|---|
| Migration applied to production Supabase | psycopg2 read-back of `experiment_id` column via us-west-2 pooler | ✅ 3 rows backfilled, index created |
| AD-241 + AD-242 promoted PLANNED → implemented | grep `docs/ml/ALGORITHMIC_DECISIONS.md` | ✅ |
| Detroit gate verdict honestly captured | read `docs/feedback/session-154-shadow-eval-detroit-rerun.md` | ✅ FAIL captured + A4 correctly skipped |
| Track B/C/E worktrees merged with `--no-ff` | `git log --oneline --merges` | ✅ 3 merge commits visible (`f199c6c9`, `1be701f0`, `8e16b41f`) |
| All worktrees clean post-return | `git -C <wt> status --porcelain` per worktree | ✅ |
| `make test-fast` post-merge | 4205 passed (+27 from new tests) | ✅ |
| `git log origin/main..HEAD` empty | post-final-push | ✅ |
| `git status --short` empty | post-final-commit | ✅ |
| Production health 200 | curl × 5 | ✅ |
| Memory backup integrity | `scripts/backup-memory.sh` exit 0 | ✅ 56 files, no orphans |
| harness-check.sh exit 0 | runs | ❌ pre-existing 80-docs-over-cap (not introduced by 154) |
| GitHub Actions CI green on `main` | `gh run list` | ❌ pre-existing failure on `test_identity_suggestions::test_table_exists` (Supabase env not set in workflow) |

## Commits (12 total in 154 work)

```
b604c4b2 docs(session-154): closeout — A3 Detroit rerun analysis + assessment + CHANGELOG/ROADMAP v0.99.70
8e16b41f merge: Track E (Supabase E0.5 + E1 + E3 + OD-013)
1be701f0 merge: Track C (Belle Isle citation + Irving verification)
f199c6c9 merge: Track B (Harry face-ID resolution + Bessie strengthening)
021464f9 feat(session-154): Track E E3 — retention script + admin db-size endpoint + OD-013
1e0b0fbc docs(session-154): Supabase stopgap prune plan + tripwire script (E1)
a09f8700 feat(session-154): shadow eval A0+A1+A2 — schema fix, GEDCOM context, iterative refinement
58abbc16 docs(session-154): GEDCOM bloat root-cause analysis (E0.5)
0f043059 docs(session-154): Belle Isle archival citation (C1)
af4fcf8f docs(session-154): strengthen Bessie=3009 hypothesis (B2)
6d7e1bf0 docs(session-154): Irving anchor verification (C2)
371f9c26 docs(session-154): resolve Harry Fox face-ID discrepancy (B1)
e04e4caf test(hooks): repair clear-gate baseline for Opus 4.7 thresholds   ← unblocked GitHub Actions
```

Plus the 4 commits already on main at session start (3d0a31ea/27a8c907/3a26faef/aa007732 from 153b prep).

## Deviations from prompt

- Phase A4 (full 12-photo eval) — correctly skipped per A3 acceptance gate (the prompt's own gate said skip if Detroit fails, and 02068 failed).
- Phase E4 (PRD-063) — NOT WRITTEN. Track E worktree subagent hit usage limit before reaching it. Deferred to Session 155.
- Phase D1 (Harry repair execution) — NOT EXECUTED. 3 of 6 gates remain unmet. Deferred.
- Codex CLI audit calls were SUBSTITUTED with Claude general-purpose subagents per the session-defaults.md fallback policy — Codex `--full-auto` stdin-hang bug from sessions 152, 153, 153b is still unfixed and the substitution worked.
- Single-line `register_admin_db_routes(app)` in `app/main.py` was BLOCKED by the clear-gate hook at 600+ transcript lines and deferred to Session 155.
- `docs/BACKLOG.md` edit was BLOCKED by a hook-allowlist gap (`$REPO/BACKLOG.md` allowlisted but actual file is `$REPO/docs/BACKLOG.md`). Deferred items are captured in the assessment's "Deferred" section instead.

## Lessons emitted (informally, to update `tasks/lessons.md` later)

- **Pagination guard**: any Supabase REST client doing `.select(...).execute()` without `.range()` defaults to 1000 rows. The shadow eval's `resolve_gedcom_context` failed silently because of this — masked confirmed identities for the test photos. Fix: paginate via `.range(offset, offset+999)` loop.
- **Sycophancy guards need teeth**: the AD-242 "name a positive supporting feature" wording was too easy for Gemini to confabulate around — confidence on the WRONG NYC answer for 02068 went up, not down. Future sycophancy guards should require the supporting feature to be a NAMED GEDCOM event (subject + event type + date + place verbatim), not "a curved-glass roofline."
- **Direct Supabase hostnames are decommissioned**: `db.<project_ref>.supabase.co` is IPv6-only and unreachable from many networks. The pooler (`aws-0-<region>.pooler.supabase.com:6543` with username `postgres.<project_ref>`) is the durable path.
- **`merge.sh` cwd hazard**: invoking from a worktree cwd silently puts the merge commits on the wrong branch (`|| true` masks the checkout failure). The script needs a pre-check.
- **Hook allowlist gaps**: `pre-work-clear-gate.sh` allowlists `$REPO/BACKLOG.md` and `$REPO/CHANGELOG.md` but the actual files in this repo are at `docs/BACKLOG.md` and `CHANGELOG.md` (the latter is fine). The allowlist needs to match reality.
- **Subagent token-budget hazard**: Track E subagent ran out of tokens at E4 — the design artifact the user most wanted. When dispatching a 4-phase subagent task, plan for token budget and break to a 2-phase chunk if any phase is large (PRD writing is large).

## Cost ledger (Gemini API)

- Phase A3 Detroit subset rerun: 6 calls / $0.168138 / `experiment_id = session154_shadow_eval_1777434398`.
- No other live Gemini calls in this session.

Within the $2.00 cap by 12×.
