# Session 97: Implement PRD-038 Longitudinal Face Modeling

**Context**: `docs/session_context/session-97-context.md`
**Primary plan**: `docs/prds/SDD-038_longitudinal_face_modeling.md`
**Predecessor**: PRD-038 planning package prepared on 2026-03-11

## Problem Statement

Build the revised PRD-038 matcher in the live repo with strong eval discipline.
Do not treat this as "tune the model and hope." Start by repairing measurement,
unifying the scorer path, then earn the right to ship any matcher change.

This session should be executed by Codex with worktree isolation, explicit
artifacts, and no dependence on chat history. If a Gemini review artifact exists
for this package, read it before Act 1 and fold it in.

## Session Protocol

- Read `AGENTS.md` and `docs/session_context/session-97-context.md` first.
- Work on an isolated branch/worktree. Never run this implementation on the
  user’s active checkout.
- Commit after each act with `[codex] ...` conventional commits.
- Update harness artifacts after each act, not only at the end.
- Run the smallest relevant tests during each act; run both required suites
  before final closeout.
- New research or user feedback must be written to harness artifacts before it
  changes implementation.
- Keep active context narrow:
  - before each act, read only the files listed for that act in the context file
  - do not reload earlier exploratory files unless needed

## Success Criteria

1. Eval CLI works on the current embedding schema and produces a reproducible
   baseline report.
2. `core/auto_cluster.py`, `scripts/cluster_new_faces.py`, and upload proposal
   generation share the same scoring core.
3. Recalibration hooks stay write-only in production and local recalibration is
   explicit, testable, and documented.
4. The longitudinal scorer improves the hard slices defined in
   `docs/prds/038_longitudinal/EVALUATION_AND_SAFETY.md` without harming kinship
   safety or community safety.
5. All research, decisions, and implementation breadcrumbs are preserved in the
   harness.

## Act 0: Orient, Review, And Isolate

1. Read the required files from `docs/session_context/session-97-context.md`.
2. If a Gemini review artifact exists for the PRD-038 package (`docs/assessments/session-97-gemini-review.md`), read it and
   update the plan docs before changing code. Evaluate Gemini's recommendations one by one and either adopt them or document a reasoned rejection in harness artifacts before implementation proceeds.
3. Create a dedicated worktree/branch for Session 97 implementation.
4. Create or replace `docs/session_logs/session-97-log.md` from the stub.
5. Record:
   - branch/worktree path
   - baseline git status
   - whether Gemini review was present
   - current data snapshot if it changed since the prep package

Commit: `[codex] chore(session-97): orient and establish worktree`

## Act 1: Phase 0 — Eval Repair And Scorer Path Unification

This is the first hard gate. Do not skip it.

### Scope

- Repair eval loaders for mixed `mu` / `embeddings` schema.
- Rebuild or version the golden set from current confirmed identities. Explicitly log skew / concentration metrics for the rebuilt training and evaluation assets in the session log.
- Create a single shared offline scoring core used by:
  - `core/auto_cluster.py` (architectural source of truth for offline batch matching)
  - `scripts/cluster_new_faces.py` (CLI wrapper over the shared pipeline)
  - upload proposal-generation paths

### Parallelization

Use at most two worktree tracks if file overlap stays low:
- Track A: eval asset repair + baseline reporting
- Track B: scorer-core extraction + wrapper updates

If the file overlap is messy, stay sequential.

### Required outputs

- eval command that runs cleanly
- baseline JSON artifact
- updated docs noting the baseline and any changed assumptions
- tests for mixed-schema loading and scorer-path parity

### Gate

Do not proceed until the baseline is reproducible and both scoring paths call
the same underlying scorer logic.

Commit: `[codex] feat(ml): repair eval path and unify offline scorer`

## Act 2: Phase 1 — Recalibration Hygiene And Label Taxonomy

### Scope

- Keep production hooks to pair insertion only.
- Add or repair a local recalibration CLI.
- Explicitly record label provenance:
  - `explicit_positive`
  - `explicit_negative`
  - `implicit_negative`
  - `discovery_confirmed`
- Add status reporting and tests.

### Required outputs

- runnable recalibration command
- status endpoint or status report path
- tests proving production hooks do not try to retrain on Railway
- decision-log update if label semantics changed materially

### Gate

Proceed only when recalibration behavior is explicit and auditable.

Commit: `[codex] feat(calibration): harden local recalibration workflow`

## Act 3: Phase 2 — Longitudinal Prototype Bank And Shadow Reranker

### Scope

- Build the per-identity prototype bank with temporal diversity override when metadata allows.
- Build longitudinal features.
- Train a frozen-embedding reranker in shadow mode with at least one explicit kinship-risk feature and a dominant-identity bias check.
- Keep rollout behind a flag.

### Required outputs

- prototype-bank builder
- feature dictionary
- ablation report
- slice report for:
  - year-gap >= 20
  - year-gap >= 30
  - same-family false positives
  - cross-community leakage

### Gate

Do not enable the new scorer unless the Phase 2 gate from
`docs/prds/038_longitudinal/EVALUATION_AND_SAFETY.md` passes.

Commit: `[codex] feat(ml): add longitudinal reranker in shadow mode`

## Act 4: Phase 3 — Active Learning Inside Review UX

### Scope

- Integrate active learning into existing review surfaces.
- Avoid a disconnected side widget.
- Respect AD-215: fixing wrong matches must stay effortless.

### Required outputs

- uncertainty/diversity queue
- no duplicate already-labeled pairs
- audit trail for same/different actions
- actionable audit/revert path for recent active-learning labels before recalibration consumes them
- tests for diversity and label persistence

### Gate

Queue quality must satisfy the Phase 3 diversity rules before this act closes.

Commit: `[codex] feat(review): add active learning to review flow`

## Act 5: Phase 4 — Adapter / LoRA Experiment Track

Run this act only if:
- Phase 2 is stable
- skew is still the main blocker
- there is time to leave a real experiment harness

### Scope

- Build experiment-only training/eval path.
- Use balanced sampling, family holdouts, and slice gates.
- Leave rollout off by default.

### Acceptable closeout

It is acceptable to end Session 97 with a solid experiment harness and no
shipped adapter if the slice gates are not yet met. It is not acceptable to
leave this as hand-wavy future work with no runnable evaluation path.

Commit: `[codex] feat(ml): add gated adapter experiment harness`

## Act 6: Final Verification, Artifacts, And Review Package

1. Run both required suites:
   - `pytest tests/ -x -q`
   - `pytest rhodesli_ml/tests/ -x -q`
2. Run the new eval CLI and record the final baseline vs candidate comparison.
3. Review the top changed proposals manually and record the result.
4. Update:
   - `docs/assessments/session-97-assessment.md`
   - `docs/session_logs/session-97-log.md`
   - any new AD/HD entries
   - PRD-038 docs if implementation materially changed assumptions
5. Record whether cloud-migration thresholds changed.

Final commit: `[codex] docs(session-97): assessment and verification`

## Non-Negotiables

- No destructive data operations.
- No app-facing matcher change without passing shadow eval and manual diff review.
- No leaving research or review feedback only in chat or terminal output.
- No switching to a cloud-serving rewrite during this session.
- No broad architecture changes unless the evidence forces them and the decision
  is logged.

## Required Session Outputs

- `docs/session_logs/session-97-log.md`
- `docs/assessments/session-97-assessment.md`
- updated evaluation artifacts
- updated research references if new sources materially changed decisions
- updated decision logs for any architectural or harness changes

## Scale Reminder

PRD-038 still launches as a local offline system. The code you write should make
later cloud extraction easy by keeping scorer execution artifact-based and
job-oriented, but this session should not move the workload into cloud serving
unless a new decision artifact explicitly changes that plan.
