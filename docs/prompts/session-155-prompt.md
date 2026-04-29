# Session 155 — Session 154 Followups + GEDCOM Mirror Redesign + 02068 Prompt Iteration

**Mode**: Implementation + interactive (mixed)
**Predecessor**: Session 154 (`docs/assessments/session-154-assessment.md`)
**Context file (MANDATORY first read)**: `docs/session_context/session-155-context.md`

**Why this session exists**: Session 154 closed with 5 P1 items genuinely
deferred — Track E PRD-063 (subagent ran out of tokens), Track A 02068
prompt iteration (A3 gate failed), Track E E2 prune (gated on user auth),
Track D Harry repair (gated on missing reference data), and CI Supabase env
(pre-existing infra debt). This session knocks out everything that doesn't
require fresh user input, surfaces the user-decision items cleanly, and
preserves the harness.

## Setup

```bash
echo "155" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
bash scripts/harness-check.sh             # warn-only on 80-docs-over-cap is acceptable
make test-fast                             # Baseline — must be green
git log origin/main..HEAD                  # MUST be empty
git pull origin main                       # Safety
```

## Required first reads (in order)

1. `docs/session_context/session-155-context.md` — full carry-over.
2. `docs/assessments/session-154-assessment.md` — what was deferred + why.
3. `docs/feedback/session-154-supabase-bloat-root-cause.md` — Track 1 evidence base.
4. `docs/feedback/session-154-shadow-eval-detroit-rerun.md` — Track 2 starting point.
5. `docs/feedback/session-154-supabase-prune-plan.md` — Track 4 prune plan (commit `1e0b0fbc`).
6. `docs/feedback/session-153b-harry-repair-decision.md` — Track 4 Harry gates.
7. `tasks/lessons.md` repeat-offender table (lessons 173-178 are new from 154).

## Non-negotiable rules

1. READ-ONLY on production browsers (`.claude/rules/browser-read-only.md`).
2. Never overclaim — STRONG/GOOD/POSSIBLE/WEAK/UNKNOWN, not "confirmed" without ≥3 sources WITH reference data.
3. Every phase commits atomically. /clear between phases at 300+ transcript lines.
4. Every ML decision gets an AD entry. Session 155 will create AD-243 (residence-distance scoring).
5. Harness closeout is mandatory — all 9 steps from `.claude/rules/session-defaults.md` Session End.

## Parallelization plan

```
┌──────────────────────────────────────────────────────────────────┐
│ Track 1 — PRD-063 GEDCOM mirror redesign (worktree subagent)     │
│   Phases 1A (read evidence), 1B (write PRD ≤ 300 lines)          │
│                                                                  │
│ Track 2 — 02068 prompt iteration Path A (worktree subagent)      │
│   Phases 2A (design AD-243), 2B (implement), 2C (Detroit rerun)  │
│                                                                  │
│ Track 3 — CI Supabase env + allowlist parity test (worktree)     │
│   Phases 3A (workflow env), 3B (parity test), 3C (verify CI green)│
│                                                                  │
│ Track 4 — Surface user decisions (MAIN thread, no execution)     │
│   Harry repair options + E2 prune authorization protocol         │
│                                                                  │
│ Track 5 — Codex CLI hang diagnosis (worktree, P3 / optional)     │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                   Merge point — Phase 6 (closeout)
```

Launch Tracks 1, 2, 3 (and optionally 5) as background worktree subagents
at session start. Run Track 4 in main thread. Synthesize at Phase 6.

---

## Track 1 — PRD-063 GEDCOM mirror redesign (worktree subagent)

### Phase 1A — Read evidence (~10 min)

1. `docs/feedback/session-154-supabase-bloat-root-cause.md` — the 3 dominant causes
2. `docs/feedback/session-154-supabase-prune-plan.md` — what the stopgap covers (so the redesign doesn't double-prune things)
3. `scripts/supabase_migration_002_gedcom_versioning.sql` + `_003_gedcom_rich_mirror.sql` — current schema
4. `rhodesli_ml/gedcom_context.py` — current read paths (variants: full, curated, first_order, co_occurrence)
5. `app/estimate_routes.py::_build_gedcom_context_for_photo` — the canonical app reader
6. `scripts/run_combined_pipeline.py::load_gedcom_data` — the canonical loader
7. AD-160 (in-app GEDCOM linking), AD-210 (business-name → owner lookup), AD-211 (Gemini context)

### Phase 1B — Write `docs/prds/063_gedcom_mirror_efficient_redesign.md` (~45 min, ≤ 300 lines)

Required sections per the Session 154 prompt's E4 spec:

1. **Goal**: preserve ALL current functionality (in-app GEDCOM search, identity↔GEDCOM linking [AD-160], business-name→owner lookup [AD-210], subject GEDCOM context for Gemini prompts [AD-211, AD-241], `/tree` rendering, versioning audit trail).

2. **Storage-reduction proposal** — for each mechanism, evaluate AGAINST E0.5 evidence and quantify expected reduction:
   - Hash-based dedup at INSERT (`payload_hash` no-op skip + version-range tracking) — E0.5 said top-20 hashes each repeat 7×; this alone is ~400 MB.
   - Single canonical row per individual + versioned archive (one row per `gedcom_id` ≈ 10-13K rows + per-version archive on R2 as compressed JSONL) — addresses the 7-version-retention bloat, ~700 MB.
   - Drop `raw_record_json` from runtime tables; archive per-import as gzipped blob on R2 — eliminates double-storage of raw vs structured.
   - Per-import change manifest (one row per import) replacing per-cell `gedcom_change_log` — reduces 1.65M rows to ~10 rows.
   - Drop unused indexes — cite E0.5's `pg_stat_user_indexes` data.

3. **Speed estimate** for the 5 most-frequent GEDCOM read paths:
   - Identity → GEDCOM lookup (AD-160 + AD-211 build_photo_context)
   - GEDCOM xref → individual record (`get_individual_by_xref`)
   - Surname search (used by `/tools/search` rule-based parser)
   - Business-name → owner lookup (AD-210)
   - Tree-page rendering (`/tree`)
   - Cite E0.5's index-usage data and table size; estimate query-time delta.

4. **Migration plan with zero data loss** (must be reversible at every step):
   - Step 1: archive every existing version to R2 as compressed JSONL (one file per `gedcom_versions` row). Reversible via re-import.
   - Step 2: build new schema in parallel (`gedcom_individuals_v2` etc.).
   - Step 3: backfill from `is_current = TRUE` rows.
   - Step 4: dual-read in app code for one session as a confidence check.
   - Step 5: cut over reads + drop v1 tables.
   - Step 6: VACUUM FULL.

5. **Operational guardrails**:
   - All current GEDCOM .ged files MUST be backed up to R2 BEFORE any prune/redesign work.
   - Before any DROP TABLE: snapshot to JSONL + verify roundtrip restoration on a separate test database.
   - Migration is gated on user authorization message at Phase E2 rigor.

6. **NO CODE.** No migrations, no scripts, no test files. Implementation is a future session (likely 156).

7. **Cap at 300 lines** per `.claude/rules/doc-size-enforcement.md`. Split into sub-files if it goes over.

Acceptance: `docs/prds/063_gedcom_mirror_efficient_redesign.md` exists, ≤ 300 lines, references E0.5 measurements, includes all 5 sections, NO code.

Commit: `docs(session-155): PRD-063 GEDCOM mirror efficient redesign (Track 1)`.

---

## Track 2 — 02068 prompt iteration Path A (worktree subagent)

### Phase 2A — Design AD-243 (~15 min)

Read `docs/feedback/session-154-shadow-eval-detroit-rerun.md`. The 02068 failure mode:
- Gemini ranks Detroit as candidate #2 or #3 every time
- The candidate prompt's "subject's own residence outweighs relative's" instruction is too vague
- AD-242's CONFIRM path raised confidence on the WRONG NYC answer (sycophancy)

Design Path A: explicit Round-2.5 GEDCOM residence-distance scoring step. Required additions to the candidate prompt:

```
## Round 2.5 — Residence-Distance Scoring (mandatory before naming a primary)

For EACH candidate location proposed in Round 2, fill out this scoring table:

| candidate | subject_residence_match | year_distance |
|---|---|---|
| <place> | <comma-separated list of subject names with a RESI/OCCU/child-BIRTH event near this location AT THE PHOTO'S DATE RANGE; if zero, write "0 subjects"> | <smallest absolute year delta between photo's likely date and the matching event; "n/a" if zero matches> |

For each row, you MUST:
- Cite the GEDCOM event verbatim (subject name + event type + date + place)
- "RELATED" or "FAMILY" is NOT a match — only the named subject's own
  residence/occupation, or one of their children's birth places
- Immigration / port-of-entry events do NOT count
- A relative's residence does NOT count

Tie-breaker rules (must apply IN ORDER):
1. Highest count of subject_residence_match wins
2. If tied, smallest year_distance wins
3. If still tied AND no GEDCOM signal, fall back to visual evidence only

Write the chosen primary `place` ONLY after this table is complete.

If ALL candidates have 0 subject_residence_match: lower confidence to "low"
and explicitly state "no biographical anchoring available — visual-only".
```

Then update AD-242's CONFIRM path:
```
- CONFIRM the prior prediction. To do so, you MUST:
  1. Cite the EXACT GEDCOM event (subject name + event type + date + place)
     that supports the prior prediction. NOT a visual feature on its own.
     If no GEDCOM event supports it, you MUST refute or lower confidence.
  2. State the prior prediction's `year_distance` from the Round 2.5 table.
     If that distance is greater than 5 years OR the prior prediction had
     0 subject_residence_match, you MUST refute or lower confidence.
```

Write **AD-243** in `docs/ml/ALGORITHMIC_DECISIONS.md`:
- Title: `AD-243: Round-2.5 Residence-Distance Scoring + AD-242 CONFIRM Path Tightening`
- Context: Session 154 Phase A3 Detroit gate failed on photo 02068. Candidate prompt + AD-242 retry both predicted NYC across 3 variants WITH GEDCOM context. Sycophancy guard raised confidence on wrong answer from medium→high. Path A response.
- Decision: New Round 2.5 explicit scoring table + tightened AD-242 CONFIRM clause.
- Rationale: forces Gemini to compute date-distance per candidate before naming primary, which makes the GEDCOM signal a hard constraint instead of soft guidance.
- Affects: `scripts/session153_shadow_eval.py` (CANDIDATE_LOCATION_SECTION + PRIOR_PREDICTION_BLOCK + CANDIDATE_LOCATION_SCHEMA).
- Failure mode: if Gemini ignores the table format, the constraint isn't enforced. Mitigation: require the table in the response schema as a structured field.

### Phase 2B — Implement (~20 min)

Edit `scripts/session153_shadow_eval.py`:
1. Replace `CANDIDATE_LOCATION_SECTION` with the new version including Round 2.5
2. Update `CANDIDATE_LOCATION_SCHEMA` to require the residence-distance table as a structured field (e.g., `residence_distance_table: [{candidate, subject_residence_match, year_distance}]`)
3. Update `PRIOR_PREDICTION_BLOCK` CONFIRM path per AD-243
4. Add a regression test in `tests/test_shadow_eval_prompt_structure.py` (NEW) asserting the new sections appear in `build_prompt(variant="candidate")`

Run `pytest tests/test_shadow_eval_prompt_structure.py` (new, expected to pass).

### Phase 2C — Detroit rerun (~10 min)

1. Run `python scripts/session153_shadow_eval.py --photo-ids inbox_fox-charlie-001_204_02068_p_13akf5twbc3600,inbox_fox-charlie-001_3_01659_p_13akf5twbc1045 --max-cost 0.50`
2. Cost target: ≤ $0.20 (6 calls × ~$0.03)
3. Acceptance gate (same as Session 154 A3):
   - Both photos `place = Detroit/Belle Isle/Michigan` at `≥medium` confidence under `candidate_with_prior`
   - Neither regresses under `candidate` (vs baseline) when given GEDCOM context
4. Output to `docs/feedback/session-155-shadow-eval-detroit-rerun.json` and `.md`
5. If gate passes → Phase 2D unlocks (full 12-photo eval, ~$0.50, output to `session-155-shadow-eval-full.{json,md}`)
6. If gate fails → STOP. Document failure mode honestly. Recommend Path B (PRD-061 multi-frame) for Session 156.

### Phase 2D (conditional) — Full 12-photo eval (~30 min, only if 2C passes)

1. Run `python scripts/session153_shadow_eval.py --max-cost 1.00`
2. Output to `docs/feedback/session-155-shadow-eval-full.{json,md}`
3. Decision per-photo: did Path A help? Per-bucket aggregate accuracy.
4. **Production deployment is NOT in this session** — the full eval produces evidence; deployment is a separate reviewed PR.

Commit per phase. Final commit message includes the run cost + verdict.

---

## Track 3 — CI Supabase env + allowlist parity test (worktree subagent)

### Phase 3A — Add Supabase env to GitHub Actions (~10 min)

The `Tests` workflow has been failing since at least Session 153b on
`test_identity_suggestions::test_table_exists` because `SUPABASE_URL` is not
set in the workflow env. **User action required**: paste the secrets into
GitHub UI before this phase can complete.

Subagent's responsibility:
1. Read `.github/workflows/test.yml`
2. Add an `env:` block to the `test` job referencing `${{ secrets.SUPABASE_URL }}` + `${{ secrets.SUPABASE_ANON_KEY }}` + `${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}` + `${{ secrets.GEMINI_API_KEY }}`
3. Note in the commit message that the secrets must be set in GitHub repo settings before CI will pass

If the user has not yet set the secrets, this phase still ships — CI will pass once secrets are pasted.

### Phase 3B — Allowlist parity test (~15 min)

`pre-work-clear-gate.sh` allowlist must match every session-end-artifact path mentioned in `session-defaults.md`. Session 154 found `docs/BACKLOG.md`, `docs/prompts/`, `tasks/lessons.md` were missing from the allowlist. Add a structural test that fails if any session-end artifact path doesn't have an allowlist match.

1. New file `tests/test_session_artifact_paths.py`
2. Read `.claude/rules/session-defaults.md` + `verification-gate.md` + `self-assessment.md`
3. Extract every file path mentioned in the session-end checklist (steps 1-9 + sub-rules)
4. For each path, simulate the hook with a transcript-line count of 1000 + that file path; assert the hook exits 0
5. Cover: `docs/assessments/session-NN-assessment.md`, `docs/session_logs/session-NN-log.md`, `docs/session_context/session-NN-codex-audit.md`, `docs/session_context/session-NN-context.md`, `docs/feedback/session-NN-*.md`, `docs/prompts/session-NN-prompt.md`, `CHANGELOG.md`, `ROADMAP.md`, `docs/BACKLOG.md`, `tasks/lessons.md`, `tasks/lessons/*.md`, `tasks/todo.md`

Commit: `test(harness): allowlist parity test for session-end artifacts`.

### Phase 3C — Verify CI green (~5 min)

After Phase 3A pushes (and user has set secrets), confirm the next CI run passes. If still failing, diagnose and fix or escalate.

---

## Track 4 — Surface user decisions (MAIN thread, no execution)

### 4A — Track D Harry repair (no execution)

Surface 3 options to the user:

> Track B (Session 154) confirmed the 2 face IDs to detach from the
> "Harry Fox" identity are `inbox_1fea75ce2caf` (face F, photo 01659) and
> `inbox_e507a54f204a` (face G, photo 02068). Track C confirmed Belle Isle.
> Bessie hypothesis is POSSIBLE-GOOD ~55% (granddaughter at top 0.5%).
>
> 6-gate status: 2/6 met (face-IDs, Belle Isle), 1/6 partial (Bessie not
> at full GOOD), 3/6 unmet (1910s reference, third frame, full Bessie GOOD).
>
> Three options:
>
> **(a) Wait** — search Ancestry tree 162873127 for a 1910s Bessie photo,
> compute embedding distance against face F+G's neighbor 3009. Strongest
> possible signal but requires user-side Ancestry browsing.
>
> **(b) Search for a third Belle Isle frame** — PRD-061 (event clustering)
> would be the home for this work. Search Charlie Fox collection + Ancestry
> for additional Belle Isle Conservatory photos that could triangulate.
>
> **(c) Ship the conservative replacement label** —
> "Belle Isle Conservatory Young Man c.1917-1918". Reversible if better
> evidence later surfaces. Gates 4-6 are partially met by Track B+C work.
> The label avoids the over-claim risk Session 153b retracted.
>
> Default if no decision: STOP. Repair stays gated.

Output: `docs/feedback/session-155-user-decisions.md` — capture the user's
response verbatim. Execute (c) only on explicit user authorization.

If (c) is authorized, the execution path is:
1. Snapshot Harry Fox identity to `backups/session-155/harry-fox-before-{UTC}.json`
2. Draft an audit_log row for the move
3. Detach `inbox_1fea75ce2caf` + `inbox_e507a54f204a` from Harry Fox identity
4. Create new INBOX identity "Belle Isle Conservatory Young Man c.1917-1918" with those 2 faces
5. Link the new identity to GEDCOM Harry Isaackovitz record as a *candidate*, not confirmed
6. Run structural tests (`tests/test_data_integrity.py`)
7. Browser-verify Harry Fox person page (now 5 anchors) + new identity page (READ-ONLY)
8. Commit + push

### 4B — Track E E2 prune authorization protocol (no execution)

Surface to user:

> The Session 154 E1 prune plan (commit `1e0b0fbc`,
> `docs/feedback/session-154-supabase-prune-plan.md`) reaches ~840 MB final
> from 2.22 GB current — well under the 1.1 GB ceiling. Phase E2 execution
> is gated on a verbatim authorization message naming:
>
> 1. The plan commit hash: `1e0b0fbc`
> 2. Every table touched (read the plan; expected: `gedcom_versions`,
>    `gedcom_individuals`, `gedcom_families`, `gedcom_relationships`,
>    `gedcom_events`, `gedcom_change_log`, plus VACUUM FULL list)
> 3. Every DELETE predicate (verbatim from the plan)
> 4. Every snapshot output path (`backups/session-155/<table>_pre-prune-<UTC>.jsonl.gz`)
> 5. The full VACUUM FULL list
>
> "Approved" alone is NOT sufficient. The grace period ends 2026-05-29.

If the user provides the verbatim message: execute via
`scripts/session154_supabase_prune.py --execute --step <name>` step by step,
snapshot-then-mutate-then-verify per step. After each step, re-run the size
query and append to `docs/feedback/session-155-supabase-size-progress.json`.

If the user declines or doesn't respond: STOP. Document in
`docs/feedback/session-155-user-decisions.md`.

---

## Track 5 — Codex CLI hang diagnosis (worktree subagent, P3 / optional)

Try in this order. If any succeeds without hanging > 60 sec, document as the
working invocation.

1. `codex exec "Audit scripts/session153_shadow_eval.py for security and data-integrity issues. P0/P1/P2/P3."` (positional arg, no `--full-auto`)
2. `codex exec <<< "Audit scripts/session153_shadow_eval.py..."` (heredoc)
3. `echo "Audit scripts/session153_shadow_eval.py..." | codex exec -` (pipe)
4. `codex --version` — log it.
5. If all hang, run `codex exec --help` and document any flags that may have changed in a newer Codex CLI version.

Output: `docs/feedback/session-155-codex-cli-diagnosis.md` with verdicts +
the working invocation pattern (or escalation to upstream if all hang).

---

## Phase 6 — Closeout (mandatory 9-step harness)

1. `docs/assessments/session-155-assessment.md`
2. CHANGELOG: increment to v0.99.71
3. ROADMAP + SESSION_HISTORY (the latter only if archiving 154 — usually NOT in 155)
4. `docs/BACKLOG.md`: close items resolved (PRD-063-WRITE if Track 1 ships, PROMPT-A-ITERATION-001 if Track 2 ships, CI-SUPABASE-ENV if Track 3 ships, HARRY-REPAIR-001 if user authorizes (c), SUPABASE-PRUNE-EXEC-001 if user authorizes E2). Update partial-fix items.
5. `git push origin main`
6. Browser verify the canonical 6 + the new `/api/admin/db-size` endpoint (admin auth via session cookie). READ-ONLY.
7. `git log origin/main..HEAD` empty
8. `git status --short` empty
9. `bash scripts/harness-check.sh` exit 0 (warn-only on doc-size cap is acceptable)
10. `bash scripts/backup-memory.sh`
11. Run `/session-review` skill

## Success gates

| Gate | How to check |
|---|---|
| PRD-063 written ≤ 300 lines | `wc -l docs/prods/063_gedcom_mirror_efficient_redesign.md` ≤ 300 |
| AD-243 written | `grep "^### AD-243" docs/ml/ALGORITHMIC_DECISIONS.md` |
| 02068 Detroit gate (Phase 2C) | `docs/feedback/session-155-shadow-eval-detroit-rerun.md` shows Detroit/Belle Isle/Michigan ≥medium under candidate_with_prior |
| Full eval (Phase 2D, conditional) | `docs/feedback/session-155-shadow-eval-full.{json,md}` exist |
| CI Supabase env added | `grep secrets.SUPABASE .github/workflows/test.yml` returns ≥3 matches |
| Allowlist parity test | `pytest tests/test_session_artifact_paths.py -q` green |
| User decisions captured | `docs/feedback/session-155-user-decisions.md` exists with at least Track 4A + 4B verdicts |
| (if authorized) Supabase ≤ 1.1 GB | `/api/admin/db-size` returns total_bytes ≤ 1_181_116_006 |
| (if authorized) Harry repair audit_log row | grep audit_log Supabase |
| Full closeout | all 11 harness steps; `git log` + `git status` clean |

## Anti-patterns to avoid

- ❌ Running `merge.sh` from a worktree cwd (Lesson 176 — guard now in place but verify it fires).
- ❌ Pruning Supabase without per-step snapshot validation (Lessons 155, 156).
- ❌ Editing `app/main.py` (or any non-allowlisted code path) at high transcript line counts without /clear first (Lesson 89).
- ❌ Single-source claims for Harry repair without 3-source triangulation.
- ❌ Dispatching a 4-phase subagent including a large design task (Lesson 178). Track 1 has 2 phases, Track 2 has 4 phases — Track 2's 4 phases are SHORT each (the longest is 2D conditional, runs only on gate pass).
- ❌ Skipping the SESSION_HISTORY backfill if archiving from ROADMAP (Lesson 77 — usually N/A in 155).

## Codex CLI invocation pattern

`~/.codex/config.toml` defaults: `model = "gpt-5.5"`, `model_reasoning_effort = "xhigh"`. Same as 154. DO NOT use `--full-auto` (4-session hang record). Track 5 will try alternatives.

If Track 5's diagnosis lands a working invocation, retroactively run a Codex
audit on Tracks 1, 2, 3 changes during Phase 6 closeout.

## Phase timing estimates

| Track | Phase | Solo-time |
|---|---|---|
| 1 | 1A read evidence | 10 min |
| 1 | 1B PRD-063 | 45 min |
| 2 | 2A AD-243 design | 15 min |
| 2 | 2B implement | 20 min |
| 2 | 2C Detroit rerun | 10 min (+ Gemini latency) |
| 2 | 2D full eval (conditional) | 30 min |
| 3 | 3A workflow env | 10 min |
| 3 | 3B parity test | 15 min |
| 3 | 3C verify CI | 5 min |
| 4 | 4A Harry surfacing | 10 min |
| 4 | 4B prune surfacing | 10 min |
| 5 | Codex diagnosis (P3) | 15 min |
| 6 | Closeout | 25 min |
| **Total** | sequential | **~3h 40min** |
| **Parallel** | 4 main + 1/2/3/5 in subagents | **~1h 40min** |
