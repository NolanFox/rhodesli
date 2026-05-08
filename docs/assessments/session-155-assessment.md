# Session 155 Assessment

**Span**: 2026-04-29 → 2026-05-07 (8-day arc)
**Mode**: Implementation + interactive
**Predecessor**: Session 154 (`docs/assessments/session-154-assessment.md`)
**Successor**: Session 156 (`docs/prompts/session-156-prompt.md`)

> Replaces the prep-state stub from the bridge conversation (which explicitly authorized force-replacement). Bridge conversation contributions preserved at `docs/session_logs/session-154-kickoff-log.md`.

## TL;DR

5-track session that surfaced two user decisions, audit-corrected the analysis with both Claude + Codex independent passes, recovered timed-out work via the working Codex CLI invocation discovered in Track 5, and handed off cleanly to a 3-session implementation arc for PRD-063. User came back after 8 days with two decisions: ship (c) for Harry repair with provenance note + skip the Supabase band-aid prune in favor of full PRD-063 implementation across Sessions 156-158. User then added a critical UAT requirement: upload the latest Fox-family GEDCOM in 156 and verify the new pipeline (a) is easier to use, (b) supports clear change-tracking between versions, (c) prevents the size-growth issue, (d) doesn't break Supabase.

## Per-track status

| Track | Status | Evidence |
|---|---|---|
| 1 — PRD-063 GEDCOM mirror redesign | PARTIAL — 373-line draft staged in worktree, recovery subagent moves it to canonical path | `.claude/worktrees/agent-a4225a5c1a52e58f3/docs/session_context/session-155-prd-063-draft.md` |
| 2 — 02068 prompt iteration Path A | PARTIAL — patches script written + edits uncommitted in worktree, Detroit Gemini reruns DEFERRED per user | `.claude/worktrees/agent-a895bf2bfccffee78/docs/feedback/session-155-track2-patches.py` |
| 3 — CI Supabase env + allowlist parity test | TIMED OUT, worktree cleaned — re-launching in recovery | (no commits originally; recovery subagent redoes) |
| 4 — User decisions surfacing + audit-corrected analysis | ✅ SHIPPED | `docs/feedback/session-155-user-decisions.md`, `docs/feedback/session-155-user-decisions-analysis.md` v2 (328 lines, commit `1a85e3df`) |
| 5 — Codex CLI hang diagnosis | ✅ SHIPPED | `docs/feedback/session-155-codex-cli-diagnosis.md` (commit `bc69a98f`). **Working invocation: `codex exec "<prompt>" </dev/null`**. First successful Codex run since Session 152. |
| 6 — Recovery + closeout | IN FLIGHT | recovery subagent dispatched 2026-05-07 |

## What shipped

- **Working Codex CLI invocation discovered + verified** (Track 5). The `</dev/null` redirect closes stdin and prevents the 4-session hang.
- **User-decisions analysis v2** with 2 independent audits incorporated inline. Both auditors said the recommendations stand, just sharper supporting facts. Confidence downgraded: Decision 1 HIGH → HIGH-MEDIUM, Decision 2 HIGH (unchanged).
- **Session 154 closeout sweep completed** during this arc: CI test fix `d5ab7dc1`, Harry/db-size route wired `be062370`, merge.sh cwd guard `dc39d687`, hook allowlist expanded, 6 lessons added (173-178).
- **Session 156 continuation prompt + context written** with concurrent-genealogy-session resilience (R1-R9) and GEDCOM upload UAT track.
- **Session 155 log + assessment** capturing research/iteration/failures.

## Bridge conversation contributions (parallel — separate Claude conversation while I was away)

While the 8-day gap unfolded, a parallel "Session 154 kickoff" conversation:
- Updated Codex CLI v0.125 → v0.129
- Updated Claude Code 2.1.122 → 2.1.133
- Added 14-day Codex model-pin freshness gate to `harness-check.sh`
- Added best-model principle + staying-current protocol to `.claude/rules/ai-tool-audit.md`
- Verified gpt-5.5/xhigh still latest as of 2026-05-07

See `docs/session_logs/session-154-kickoff-log.md` for that work.

**Implication for Session 156**: my Codex tests in 155 ran on v0.125, but the user is about to restart on v0.129. The `codex exec "<prompt>" </dev/null` form should still work (it's a stdin-handling fix, not version-specific) but Track 5's diagnosis doc should be re-verified at 156 kickoff under v0.129.

## What was deferred (encoded in Session 156 prompt)

- Track 1 PRD-063 final canonical position — recovery subagent moves it.
- Track 2 prompt-iteration patches — recovery subagent applies; Phase 2C/2D Detroit Gemini reruns explicitly deferred per user (no Gemini API spend without authorization).
- Track 3 CI env + allowlist parity test — recovery subagent redoes.
- Track 5 commit merge to main — recovery subagent cherry-picks.
- Harry repair execution → Session 156 Track A (user authorized option (c) with provenance note).
- Supabase prune execution → REJECTED by user; full PRD-063 implementation across 156-158 instead.
- **NEW**: GEDCOM upload + UAT (4 verification points) → Session 156 Track E (added by user mid-closeout).

## Red flags / concerns

| Severity | Item | Recommended action |
|---|---|---|
| P1 | Subagent transcript inheritance triggers 600-line clear-gate hook on turn 0 — 3 of 4 subagents had to work around the hook. | Subagent worktrees should default `.claude/session_mode.txt` to `interactive`. **Open lesson candidate.** |
| P1 | API stream-idle timeouts at ~30 min during long subagent runs (3 of 5 subagents hit this in 155). | Chunk subagent prompts into ≤ 30 min phases; orchestrator should `SendMessage` to resume rather than wait for full completion. **Open lesson candidate.** |
| P1 | The original v1 user-decisions analysis had 4 P0 factual errors caught by audit. Confidence calibration was off — I claimed HIGH on both decisions before audit-correction. | Run Codex audit BEFORE first user-facing claim, not after. Use the `</dev/null` form. |
| P2 | CI still red on `test_identity_suggestions::test_table_exists` until user pastes Supabase secrets in GitHub UI. | Surface to user in Session 156 Track C. |
| P2 | Pre-existing worktrees from prior sessions clutter `.claude/worktrees/`. | Periodic worktree cleanup separate session. |

## Verification gate (per `.claude/rules/verification-gate.md`)

| Check | Method | Result |
|---|---|---|
| User decisions captured + audit-corrected | read `docs/feedback/session-155-user-decisions-analysis.md` | ✅ v2 with [CORRECTED] markers |
| Both auditors said direction held | summary in §"Net effect" | ✅ Decision 1 PARTIALLY AGREE, Decision 2 AGREE |
| Codex CLI invocation found + verified | `docs/feedback/session-155-codex-cli-diagnosis.md` | ✅ `</dev/null` redirect |
| Track 5 committed cleanly | `git log` shows `bc69a98f` on its branch | ✅ |
| Recovery subagent dispatched | tasked with R1-R4 | ✅ in flight |
| Session 156 prompt + context written | `ls docs/prompts/session-156-prompt.md docs/session_context/session-156-context.md` | ✅ |
| Session 156 prompt resilient to concurrent genealogy session | grep "Concurrent genealogy session" `docs/prompts/session-156-prompt.md` | ✅ R1-R9 added |
| Session 156 prompt covers GEDCOM upload UAT | grep "GEDCOM upload" `docs/prompts/session-156-prompt.md` | added in this closeout |
| Session 155 log written | `ls docs/session_logs/session-155-log.md` | ✅ |
| Session 155 codex audit | written below | ✅ |
| `git push origin main` | post-closeout | pending |
| `git log origin/main..HEAD` empty | post-push | pending |
| `harness-check.sh` exit 0 | warn-only acceptable on doc-cap | partial |

## AI Tool Usage

### Codex CLI v0.125.0 (gpt-5.5, xhigh) — first successful run since Session 152
- **Agent type**: Independent (fresh context).
- **Task**: Audit user-decisions analysis doc for P0/P1/P2/P3 issues.
- **Findings**: 4 P0 factual errors, 2 P1 reasoning gaps, 2 P2 mis-stated tradeoffs.
- **Acted on**: ALL caught issues incorporated into v2 of the analysis with [CORRECTED] markers.
- **Discarded**: none.
- **Value assessment**: **STRONG**. Codex caught 4 P0 factual errors that the Claude subagent did not (snapshot paths, hash dedup misrepresentation, gedcom_versions preservation, predicate format). Worth the time.
- **Comparison note**: Claude subagent caught the missing PRD-062 option (P1#3) and Bessie-gate-threshold rewriting (P0#1) that Codex did not. Both audits in parallel = better coverage than either alone.

### Claude general-purpose subagent (Opus 4.7) — analysis audit
- **Agent type**: Independent (fresh context, no prior knowledge).
- **Task**: Audit user-decisions analysis doc.
- **Findings**: 3 P0, 5 P1, 4 P2.
- **Value assessment**: STRONG. Complementary to Codex.

### Claude general-purpose subagents (Opus 4.7) — Tracks 1/2/3/5 + Phase 6 recovery
- **Tracks 1+2**: TIMED OUT at ~30 min API stream-idle, but produced recoverable artifacts.
- **Track 3**: TIMED OUT, no commits, redoing in recovery.
- **Track 5**: ran cleanly, fully committed (`bc69a98f`).
- **Phase 6 recovery**: in flight as of assessment-write.
- **Value assessment**: MODERATE. Track 5's diagnosis is high-leverage. Track 1+2's timeout pattern is structural.

## Next session should verify FIRST

1. **Recovery subagent commits** all landed on origin/main. If not, re-recover per Session 156 Phase 156-0.
2. **CI green** on the latest origin/main commit (depends on user pasting Supabase secrets per Track C).
3. **Production health endpoint** returns 200 with ML loaded.
4. **PRD-063** at canonical path `docs/prds/063_gedcom_mirror_efficient_redesign.md` (not `session_context/`).
5. **Working Codex invocation still works under v0.129**: `codex exec "test" </dev/null` should return within 30s.

## Cost ledger

- Gemini API: **$0** in 155 (no Phase 2C/2D Detroit Gemini reruns; Track 2 deferred per user).
- Codex CLI: ~3 min total run time across 1 hung attempt + 1 killed attempt + 1 successful audit.
- Subagent token usage: ~700K tokens across 5 worktree subagents + 1 audit subagent.

## Memory backup

`scripts/backup-memory.sh` runs as part of the closeout (automated by stop-gate.sh hook).
