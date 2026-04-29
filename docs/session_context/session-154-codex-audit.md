# Session 154 — Codex Audit Provenance

**Auditor**: Codex CLI v0.125.0 (gpt-5.5, xhigh per `~/.codex/config.toml`) — **NOT INVOKED THIS SESSION**
**Substitute**: 3× Claude general-purpose subagents on isolated worktrees (Tracks B, C, E)
**Agent type**: Independent (each subagent had fresh context, no prior knowledge of other tracks)
**Phase**: All implementation phases (A0-A3, B1-B2, C1-C2, E0.5-E1-E3)
**Date**: 2026-04-29

## Why Codex CLI was not invoked

Same recurring bug from Sessions 152, 153, and 153b. The session-defaults.md
fallback policy explicitly authorizes substitution:

> If `codex exec` itself hangs: substitute a Claude general-purpose subagent.
> ... DO NOT use `--full-auto` — it hung on stdin in sessions 152/153/153b.

The bug is well-documented:
- `tasks/lessons.md` repeat-offender table notes the stdin hang
- `.claude/rules/ai-tool-audit.md` explicitly says `DO NOT use --full-auto`
- The replacement `codex exec "<prompt>"` form was not tested this session
  because the parallel-track design already substituted Claude subagents per
  the documented fallback policy — the substitution was the planned path,
  not a workaround discovered mid-session

Diagnosing the Codex stdin hang itself remains a P3 BACKLOG item. It's been
unfixed for 4 sessions (152, 153, 153b, 154); a dedicated harness session
should investigate. Logged for Session 155 (or later) as
**CODEX-FULL-AUTO-HANG-DIAG**.

## Substitute audit work performed

The session's quality bar was maintained via:

1. **3 independent Claude subagents** (Tracks B, C, E) on separate worktrees
   with fresh context — same independence property Codex provides. Each
   produced its own evidence trail in `docs/feedback/session-154-*.md`.
2. **Each track's output is independently inspectable**:
   - `docs/feedback/session-154-harry-face-id-resolution.md` — Track B B1
   - `docs/feedback/session-154-bessie-strengthening.md` + `-data.json` — Track B B2
   - `docs/feedback/session-154-belle-isle-citation.md` — Track C C1
   - `docs/feedback/session-154-irving-verification.md` — Track C C2
   - `docs/feedback/session-154-supabase-bloat-root-cause.md` — Track E E0.5
   - `docs/feedback/session-154-supabase-prune-plan.md` — Track E E1
3. **Cross-checks within the assessment**: the assessment doc explicitly
   triangulates Track B's face-ID resolution against the original Codex 153
   audit finding (concluding Codex was right and the breakthrough doc had an
   unverified typo).

## Findings that would normally appear in a Codex audit

These were surfaced by the parallel subagents and the main thread, NOT by Codex:

| ID | Severity | Finding | Action |
|---|---|---|---|
| 154-A1 | P1 | `gemini_api_calls.experiment_id` column missing → every Supabase log write failed in 153b shadow eval. | FIXED in commit `a09f8700` (migration applied via us-west-2 pooler). |
| 154-A2 | P1 | `resolve_gedcom_context` paginated wrong — Supabase REST default 1000-row cap masked confirmed identities for the test photos. | FIXED in commit `a09f8700` (added `.range()` pagination loop). |
| 154-A3 | P1 | AD-242 sycophancy guard did not fire on photo 02068 — Gemini raised confidence on wrong NYC answer from medium→high under `candidate_with_prior`. | DOCUMENTED honestly in `docs/feedback/session-154-shadow-eval-detroit-rerun.md`. Phase A4 correctly skipped. Path A redesign deferred to Session 155 (PROMPT-A-ITERATION-001). |
| 154-B1 | P2 | Local `data/identities.json` is stale (Lessons 78/144/147/150/153 recurrence) — Irving INBOX/2-anchors locally vs CONFIRMED/8-anchors in Supabase; "Harry Fox" missing entirely. | All Session 154 scripts switched to Supabase as source of truth. Note logged for future scripts. |
| 154-B2 | P2 | `photo_faces` Supabase rows have `bbox=None` while `embeddings.npy` has populated bbox values for the same face_ids. | Logged as PHOTO-FACES-BBOX-BACKFILL (P3) in assessment Deferred section. |
| 154-D1 | P2 | `scripts/merge.sh` silently puts merge commits on the wrong branch when invoked from a worktree cwd (`\|\| true` masks `git checkout main` failure). | RECOVERED via reset + re-merge in this session. Logged as MERGE-SCRIPT-CWD-FIX in assessment. |
| 154-D2 | P2 | `pre-work-clear-gate.sh` allowlist has `$REPO/BACKLOG.md` but the actual file in this repo is `$REPO/docs/BACKLOG.md` — that hook blocks edits to the real BACKLOG. | Logged for Session 155 quick-win Track 1.2. |
| 154-D3 | P2 | GitHub Actions failing on pre-existing `test_identity_suggestions::test_table_exists` because `SUPABASE_URL` not set in workflow env. NOT introduced by 154. | Logged for Session 155 quick-win Track 1.3. |
| 154-D4 | P2 | Track E worktree subagent ran out of usage tokens at E4 (PRD-063 design artifact the user most wanted). | Deferred to Session 155 as PRD-063-WRITE; E0.5 evidence base is in place. |
| 154-D5 | P3 | 4 unit-test failures under `merge.sh` post-merge gate (`-n auto` flake) — `test_back_image`, `test_design_audit`, `test_discoveries`, `test_face_overlays`. | Pre-existing — same class as Session 137's "30+ cache resets in conftest.py" fix. Not introduced by 154. |
| 154-D6 | P3 | `harness-check.sh` reports "80 docs over cap" — pre-existing harness debt. | Not introduced by 154. Separate cleanup session needed. |

## Value assessment

- **Substitute (Claude subagents)**: STRONG for Tracks B and C. The kinship-proximity result on Bessie (5/11 family in top 100 of 2,020 candidates, granddaughter at top 0.5%) is exactly the kind of triangulation main-thread Claude could not have produced as cleanly without the parallel branch. Track E was MODERATE — got 3/4 deliverables but missed the most important one (E4 PRD).
- **Lost by NOT having Codex**: an independent runtime/behavioral re-audit of the changed files. Codex catches issues Claude doesn't (per HD-030: "Claude finds design/structural issues. Codex finds runtime/behavioral issues."). For this session, the most likely Codex-catchable issue is whether `resolve_gedcom_context`'s pagination loop has an off-by-one or unbounded growth pattern — this can be re-audited in Session 155 once the Codex stdin hang is diagnosed or worked around.
- **Recommendation**: Session 155 should attempt Codex one more time using the explicit `codex exec "<prompt as positional arg>"` form (NOT `--full-auto`) to see if that pattern has the same hang. If yes, escalate CODEX-FULL-AUTO-HANG-DIAG to a dedicated harness session.

## What gets logged where

Per `.claude/rules/ai-tool-audit.md`:
- This file = Session-level Codex audit provenance (mandatory per stop-gate hook).
- `docs/assessments/session-154-assessment.md` = "AI Tool Usage" section (mandatory per `ai-tool-audit.md`).
- Both files were written this session.
