# Session 97 Context — PRD-038 Longitudinal Face Modeling

**Prepared:** 2026-03-11
**Prepared by:** Codex
**Status:** Ready for review before implementation
**Primary brief:** `docs/prds/038_longitudinal_face_modeling.md`
**Primary plan:** `docs/prds/SDD-038_longitudinal_face_modeling.md`

---

## Goal

Implement and test the revised PRD-038 plan in a way that is:
- eval-first
- non-destructive
- easy to review
- compatible with later cloud extraction
- fully breadcrumbed into the harness

This context file is intentionally phase-scoped. Read the overview first, then only the files listed for the current phase.

---

## User Directives Captured

1. Build on Claude's PRD, but document where Codex agrees and where it diverges.
2. Research broadly: repo history, academic papers, product behavior, community pain points, and current agent/prompt best practices.
3. Do not interfere with ongoing Session 96 debugging. Work in isolated branches/worktrees.
4. Record research, user feedback, decisions, and work in harness artifacts as you go.
5. Optimize for evaluation and safety. Do not ship ML changes into the app unless evidence says they improve the system.
6. Preserve room for future prompt/context engineering. This planning pass is pre-work for the implementation prompt.
7. Design with cloud scale in mind even though PRD-038 should launch as a local offline pipeline.
8. Expect this review order:
   - Gemini review of the planning package
   - finish Session 96 stabilization
   - feed Gemini feedback back into this package
   - merge/rebase planning branch
   - user adds more Fox-family data
   - implement PRD-038
   - later Claude review of the implementation
9. Parallelize where it is genuinely safe, but do not split overlapping file sets just to look parallel.
10. No silent failures, no destructive data handling, no undocumented research loops.

---

## Current Factual Baseline

- Confirmed identities: 84
- Confirmed identities with 2+ faces: 28
- Same-identity confirmed pairs: about 1,453
- Same-identity pairs with date coverage: 331
- Same-identity pairs with year gap >= 20: 54
- Birth-year estimate records for confirmed identities: 32
- Current stale golden set: 125 mappings / 23 identities
- Schema-aware local spot check:
  - Euclidean AUC about 0.978
  - MLS AUC about 0.953
- Critical repo findings:
  - matcher path split across `core/auto_cluster.py` and `scripts/cluster_new_faces.py`
  - eval scripts stale against mixed `mu` / `embeddings` schema
  - production hooks should stay write-only for recalibration data

---

## Required Read Order

### Always read first

1. `AGENTS.md`
2. `docs/prds/038_longitudinal_face_modeling.md`
3. `docs/prds/SDD-038_longitudinal_face_modeling.md`
4. `docs/prds/038_longitudinal/EVALUATION_AND_SAFETY.md`
5. `docs/prds/038_longitudinal/RESEARCH_REFERENCES.md`
6. `docs/ml/ALGORITHMIC_DECISIONS.md` entries AD-215 through AD-217
7. `docs/HARNESS_DECISIONS.md` entries HD-024 and HD-025
8. `docs/assessments/session-97-gemini-review.md`

### Read only if present before implementation starts

1. `docs/assessments/session-97-post-gemini-assessment.md`
2. Any new Fox-family data audit or pair-count refresh

If those files exist, absorb them before coding. If they do not, continue with the artifacts above.

---

## Phase Map

### Phase 0 — Measurement Repair And Path Unification

**Read**
- `core/auto_cluster.py`
- `scripts/cluster_new_faces.py`
- `app/upload_routes.py`
- `scripts/evaluate_golden_set.py`
- `scripts/evaluate_mls_vs_euclidean.py`
- `scripts/build_golden_set.py`
- `rhodesli_ml/evaluation/`

**Deliver**
- working schema-tolerant eval CLI
- refreshed golden-set asset
- baseline JSON report
- shared scorer interface used by both clustering paths

**Do not proceed** until the baseline can be reproduced on the current repo state.

### Phase 1 — Recalibration Hygiene And Label Taxonomy

**Read**
- `rhodesli_ml/recalibration_hooks.py`
- `rhodesli_ml/similarity_calibration.py`
- `rhodesli_ml/calibration/`
- routes that write admin match labels or review actions

**Deliver**
- local recalibration CLI
- explicit label provenance taxonomy
- status reporting
- tests proving production hooks stay write-only

### Phase 2 — Frozen-Embedding Longitudinal Reranker

**Read**
- Phase 0 baseline report
- prototype-bank design in the SDD
- quality/date metadata sources

**Deliver**
- prototype-bank builder
- longitudinal feature builder
- shadow-mode reranker behind a flag
- ablation and slice reports

### Phase 3 — Active Learning In Review UX

**Read**
- AD-215
- current review surfaces and discovery routes
- Phase 2 slice gaps

**Deliver**
- active-learning queue integrated into review UX
- diversity rules
- audit trail for labels

### Phase 4 — Adapter / LoRA Experiment Track

**Read**
- skew audit
- family holdout design
- Phase 2 plateau evidence

**Deliver**
- experiment-only training path
- slice-gated eval
- no default rollout without explicit wins

If Phase 2 meaningfully improves the hard slices, Phase 4 can remain unshipped but should still leave a runnable experiment harness if time permits.

---

## Scale-Aware Roadmap

PRD-038 should launch as a local offline system, but the code should assume eventual extraction to queued cloud workers.

### Keep local for now

- current archive scale is still small enough for local batch work
- product risk is correctness, not throughput
- eval repair and scorer semantics matter more than infrastructure change

### Design constraints now

1. Keep all scorer stages artifact-driven and versioned.
2. Keep batch scoring callable as a job, not only as a local script side effect.
3. Keep web requests free of heavy ML.
4. Keep rollback pinned to artifact versions, not environment state.

### Cloud cutover triggers

Move offline scoring / retraining off the laptop when any of these become true:
- batch scoring or shadow replay routinely exceeds about 45 minutes
- new-face volume is consistently above about 100 faces per day
- archive scale reaches about 10k identities or 100k embeddings
- scheduled retraining or backfills are repeatedly skipped because they require Nolan's laptop
- multiple admins need shared access to the same ML queue

### Cloud target

The first cloud move is queued offline jobs, not synchronous request-time inference.
Use the existing ML service architecture docs as the north star:
- `docs/architecture/ML_SERVICE.md`
- queued workers
- artifact store
- pinned model/scorer versions
- same eval gates as local mode

---

## Non-Destructive Rules

1. Never modify `data/` files directly outside canonical save flows.
2. Confirmed identities remain human ground truth.
3. New model outputs are proposals only.
4. New research or user feedback must be written to harness artifacts before reuse.
5. Do not change app-visible matcher behavior until shadow eval and manual diff review pass.

---

## Mandatory Outputs

By the end of Session 97, the implementation pass should leave:
- `docs/session_logs/session-97-log.md` or an updated replacement for the stub
- `docs/assessments/session-97-assessment.md`
- updated decision logs if architecture or harness decisions changed
- updated research references if new sources materially changed decisions
- eval artifacts and reproducible commands
- explicit note on whether cloud migration thresholds changed

---

## Open Questions That Actually Matter

1. Should Phase 0 replace the current golden set entirely or version it alongside the old asset?
2. Which file should own the shared scorer interface: existing ML module vs new scorer module?
3. Which review surface is the best insertion point for active learning without duplicating AD-215 cluster-review work?
4. After Gemini review and new Fox-family data, do the skew and age-gap slices materially change enough to alter Phase 2 feature priorities?

If a new question appears and changes architecture, log it before moving on.
