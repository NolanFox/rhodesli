# Session 155 Context — Carry-Over From Session 154

**Predecessor**: Session 154 (`docs/assessments/session-154-assessment.md`)
**Predecessor-predecessor**: Session 153b (`docs/assessments/session-153b-assessment.md`)
**Written**: 2026-04-29 at end of Session 154
**Purpose**: Everything new-context Claude needs to resume without re-reading 154.

---

## TL;DR in 60 seconds

Session 154 shipped 16 commits (`e04e4caf` → `0c7b900b` plus the test-fix
`<TBD>` from Session 154 closeout sweep). Production at HTTP 200, working tree
clean, all 9 closeout steps satisfied. Five tracks left genuinely unfinished:

1. **Track A prompt iteration** (P1): Phase A3 Detroit gate FAILED on photo
   02068. The candidate prompt + `candidate_with_prior` retry both predicted
   NYC across 3 variants WITH 22.8KB GEDCOM context. AD-242 sycophancy guard
   raised confidence on the wrong NYC answer from `medium → high`. Path A
   (stronger explicit GEDCOM residence-distance scoring step) is the
   cheapest experiment.
2. **Track E PRD-063** (P1): GEDCOM mirror efficient redesign was the user's
   strategic ask. E0.5 root-cause data is in place; PRD just needs drafting.
3. **Track E E2 prune execution** (P1): Plan exists at commit `1e0b0fbc`,
   gated on user authorization message. Grace period ends 2026-05-29.
4. **Track D Harry repair** (P1): 3 of 6 gates remain. Needs user decision
   on whether to ship the conservative replacement label.
5. **CI Supabase env** (P2): GitHub Actions failing on
   `test_identity_suggestions::test_table_exists` (pre-existing — not
   introduced by 154). Add Supabase secrets to workflow.

Plus several P2/P3 follow-ups in `docs/BACKLOG.md` Session 154 deferred
items section (HOOK-ALLOWLIST-FIX partially-fixed, MERGE-SCRIPT-CWD-FIX
fixed in 154 closeout, PHOTO-FACES-BBOX-BACKFILL, CODEX-FULL-AUTO-HANG-DIAG).

---

## Outstanding work inventory (this is the canonical list)

### P1 — Must address in 155 if at all possible

| Item | Status | Owner / next action |
|---|---|---|
| **PRD-063-WRITE** (GEDCOM mirror redesign) | NOT STARTED in 154 (subagent ran out of tokens) | Drive from `docs/feedback/session-154-supabase-bloat-root-cause.md`. Output: `docs/prds/063_gedcom_mirror_efficient_redesign.md` ≤ 300 lines. Design only — NO CODE. |
| **PROMPT-A-ITERATION-001** (02068 prompt fix) | A3 evidence shipped, prompt redesign deferred | Path A or Path B. Path A is cheaper. Re-run Detroit subset; accept gate per A3 criteria. |
| **SUPABASE-PRUNE-EXEC-001** | Plan in place (commit `1e0b0fbc`), authorization not yet given | Surface to user. Run only on verbatim authorization message. Default = STOP. |
| **HARRY-REPAIR-001** | 2/6 gates met, 1/6 partial (Bessie POSSIBLE-GOOD ~55%), 3/6 unmet | Surface 3 options to user: (a) wait for 1910s Bessie reference, (b) search for third Belle Isle frame, (c) ship conservative replacement label "Belle Isle Conservatory Young Man c.1917-1918". Default: surface, do not execute. |

### P2

| Item | Status | Notes |
|---|---|---|
| **CI-SUPABASE-ENV** | Pre-existing CI fail on `test_identity_suggestions::test_table_exists` | Add `SUPABASE_URL` + `SUPABASE_ANON_KEY` to GitHub repo secrets and `.github/workflows/test.yml` env. User action required for the secrets paste. |
| **APP-MAIN-WIRE-DB-SIZE** | DONE in 154 closeout (commit `be062370`, merged `0c7b900b`) | Endpoint live on production at HTTP 401 (admin-gated). |
| **HOOK-ALLOWLIST-FIX** | Partially fixed in 154 (added `docs/BACKLOG.md`, `docs/prompts/`, `tasks/lessons.md`, `tasks/lessons/*`, `tasks/todo.md`) | Add structural test asserting every session-end-artifact path in `session-defaults.md` resolves to an allowlisted entry. |
| **MERGE-SCRIPT-CWD-FIX** | DONE in 154 (commit `dc39d687`) | Verify the guard fires correctly in 155 if tracks merge. |

### P3

| Item | Status | Notes |
|---|---|---|
| **CODEX-FULL-AUTO-HANG-DIAG** | OPEN since Session 152 | Try `codex exec "<positional>"` and `codex exec <<<heredoc` forms (NOT `--full-auto`). If still hung, escalate upstream. |
| **PHOTO-FACES-BBOX-BACKFILL** | OPEN | `photo_faces` Supabase rows have `bbox=None` while `embeddings.npy` populated. Either backfill or document fallback contract. |
| **DOCS-OVER-CAP** | OPEN | `harness-check.sh` reports "80 docs over cap" — pre-existing, separate cleanup session needed. Per `.claude/rules/doc-size-enforcement.md` doc files >300 lines must be SPLIT into sub-files, not trimmed. |

---

## Key files / IDs / facts to carry over

### Identity IDs (verified in Session 154)
| Person | ID | State (Supabase) |
|---|---|---|
| Albert Fox | `85546ebf-75b9-4971-a9d4-b2ce2271bc19` | CONFIRMED, 197 anchors |
| Bessie Fox | `b4a43575-9312-40ec-a574-85bf4294d0af` | CONFIRMED |
| Harry Fox (registry — actually Harshel Fox; F+G in Detroit photos are misassigned) | `d74cb556-6d44-4288-ade3-1cc8fa2b45a6` | CONFIRMED, 7 anchors |
| Irving Israel Fox | `7e6aae2b-2b70-4a8a-9ee5-46e2b2c16c41` | CONFIRMED, 8 anchors |
| Person 3009 (back-right Detroit, hypothesized Bessie) | `63a1c0c1-aed2-4429-9e54-9dfae1b099d4` | INBOX |

### Face IDs that matter for Harry repair
- `inbox_1fea75ce2caf` = face F (photo 01659, center young man) — needs to be DETACHED from Harry Fox identity
- `inbox_e507a54f204a` = face G (photo 02068, center seated young man) — needs to be DETACHED from Harry Fox identity
- The Session 153 breakthrough doc's `inbox_2bc31a40c34a` does NOT exist in the system (typo); Codex was right
- Harry repair gates per `docs/feedback/session-153b-harry-repair-decision.md`

### Supabase access (Session 154 finding)
- Direct host `db.<project_ref>.supabase.co` is IPv6-only and unreachable
- Use pooler: `aws-0-us-west-2.pooler.supabase.com:6543` (or :5432 session mode), username `postgres.fvynibivlphxwfowzkjl`, password from `SUPABASE_DB_PASSWORD` env
- Lesson 175

### Shadow eval (from Session 154 Phase A3)
- Detroit subset run: 6 calls / $0.168 / `experiment_id = session154_shadow_eval_1777434398`
- Photo 02068: NYC predicted across all 3 variants (gate FAILED)
- Photo 01659: Detroit correctly identified under candidate + candidate_with_prior (gate PASSED)
- Raw: `docs/feedback/session-154-shadow-eval-detroit-rerun.json`
- Analysis: `docs/feedback/session-154-shadow-eval-detroit-rerun.md`
- Test fixture (deterministic re-run): `tests/fixtures/session154_gedcom_context.json`

### Supabase storage (from Session 154 Phase E0.5)
- 2.22 GB total, 97.9% in `gedcom_*` tables
- Three identifiable causes of bloat (~1.42 GB of 2.17 GB GEDCOM):
  - 7/9 `gedcom_versions` rows are `status='failed'` and never rolled back (~1 GB)
  - `payload_hash` populated but never used at INSERT — top-20 hashes each repeat 7× (~400 MB)
  - `gedcom_change_log` has 1.24M of 1.65M rows with NULL old AND new value (~300 MB)
- Plan reaches ~840 MB final state (vs 1.1 GB ceiling, vs 900 MB target)
- Plan: `docs/feedback/session-154-supabase-prune-plan.md` (commit `1e0b0fbc`)
- Tripwire script (dry-run-default): `scripts/session154_supabase_prune.py`
- Retention sweep (dry-run-default): `scripts/retention_sweep.py`
- Live monitoring endpoint: `/api/admin/db-size` (admin-gated, returns top-10 tables + thresholds)

---

## Parallelization plan for Session 155

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Track 1 — PRD-063 design (worktree subagent)                            │
│   `docs/prds/063_gedcom_mirror_efficient_redesign.md` ≤ 300 lines       │
│   Drive from session-154-supabase-bloat-root-cause.md                   │
│                                                                         │
│ Track 2 — Track A prompt iteration (worktree subagent OR main thread)   │
│   Path A: stronger GEDCOM residence-distance scoring step               │
│   Re-run Detroit subset → 6 calls / ~$0.20 / acceptance gate            │
│                                                                         │
│ Track 3 — CI Supabase env + harness allowlist test (worktree subagent)  │
│   .github/workflows/test.yml env vars                                   │
│   New tests/test_session_artifact_paths.py asserting allowlist parity   │
│                                                                         │
│ Track 4 — Surface user decisions (main thread)                          │
│   Track D Harry repair: 3 options                                       │
│   Track E E2 prune: authorization message protocol                      │
│   These wait on user input — do NOT execute speculatively               │
│                                                                         │
│ Track 5 — Codex CLI hang diagnosis (worktree subagent, P3 — optional)   │
│   Try `codex exec "<positional>"` (no --full-auto), heredoc, pipe       │
└─────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                   Merge point — Phase D (close)
```

### File scope (so no parallel collisions)

- **Track 1** owns: `docs/prds/063_gedcom_mirror_efficient_redesign.md` only.
- **Track 2** owns: `scripts/session153_shadow_eval.py` (CANDIDATE_LOCATION_SECTION + PRIOR_PREDICTION_BLOCK), AD-243 entry in `docs/ml/ALGORITHMIC_DECISIONS.md`, `docs/feedback/session-155-shadow-eval-*.{json,md}`, `tests/fixtures/session154_gedcom_context.json` (extend, don't rewrite).
- **Track 3** owns: `.github/workflows/test.yml`, `tests/test_session_artifact_paths.py` (NEW).
- **Track 4** is main-thread; produces decision-surfacing notes in `docs/feedback/session-155-user-decisions.md`.
- **Track 5** owns: `docs/feedback/session-155-codex-cli-diagnosis.md`.

---

## Sessions 152 → 154 harness lesson summary

| Lesson | Sessions | Pattern |
|---|---|---|
| 89 | 80, 89 | /clear after every commit (REPEAT OFFENDER) |
| 102, 103 | 80, 89 | Behavioral instructions insufficient; mechanical enforcement only |
| 140, 143 | 142, 143 | Hooks must exit 2 to block; partial fixes create false confidence |
| 148 | 148 | Push verification — `git log origin/main..HEAD` empty mandatory |
| 166, 167 | 147 | Worktree agents must commit before returning; lock contention |
| 173 | 154 | Supabase REST 1000-row pagination guard |
| 174 | 154 | Sycophancy guards in retry prompts need NAMED-event teeth |
| 175 | 154 | Supabase direct hostnames are IPv6-only; use pooler |
| 176 | 154 | `merge.sh` worktree-cwd silent-misroute bug |
| 177 | 154 | Hook allowlist must match actual repo paths |
| 178 | 154 | Subagent token-budget hazard for multi-phase tasks |

---

## Workflow preferences (user, carry-over)

- READ-ONLY on production browsers (`.claude/rules/browser-read-only.md`)
- Commit after every phase. /clear between phases at 300+ transcript lines.
- Parallelize via worktree subagents for independent work.
- Every ML decision gets an AD entry.
- Harness Session End checklist (9 steps) is mandatory every session.
- Codex CLI `--full-auto` hangs on stdin (4 sessions in a row); fall back to Claude general-purpose subagents per `session-defaults.md` policy.

---

## DO NOT repeat (regression list from 154 closeout)

- ❌ Run `scripts/merge.sh` from a worktree cwd. (Lesson 176 — guard is in place but verify it fires.)
- ❌ Edit hook-blocked files without first checking the allowlist. The Session 154 closeout hit hook blocks 3 times; allowlist is now expanded but verify if you add new artifact types.
- ❌ Dispatch a subagent with 4+ phases including a large design phase. (Lesson 178.) Split into 2 subagents.
- ❌ Trust pretty progress messages over actual git state. After every merge, verify `git log` shows the merge commits on the expected branch.
- ❌ Skip the SESSION_HISTORY backfill if archiving from ROADMAP. (Lesson 77.)
