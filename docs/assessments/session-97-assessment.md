# Session 97 Assessment

## Outcome
- Session 97 shipped the PRD-038 foundation in code, not just planning.
- Phases 0-4 are implemented in the isolated worktree and fully wired into the harness.
- Rollout gates remain closed for matcher changes. The shadow reranker and adapter experiment are present for evaluation, but baseline Euclidean scoring still controls live proposal behavior.

## What Shipped
- Phase 0: mixed-schema eval repair, shared scorer core, rebuilt longitudinal baseline, prompt-manifest lineage on touched Gemini paths.
- Phase 1: write-only recalibration hooks, reversible calibration labels, local recalibration CLI, lineage-aware calibration pairs.
- Phase 2: prototype-bank longitudinal reranker in shadow mode with slice reporting and dominant-vs-tail gates.
- Phase 3: offline active-learning queue, reversible labels, review-UX endpoints, local queue artifact, audit mirroring.
- Phase 4: frozen-embedding adapter experiment harness with family-holdout reporting instead of premature LoRA rollout.
- Verification hardening: activity feed now tolerates incomplete rows; environment-dependent E2E/download/ONNX tests now skip cleanly when repo artifacts are absent and retain deterministic coverage where possible.

## Research / Decision Alignment
- Agreed with the original Claude draft on local-first recalibration, additive-only discovery, active learning, and keeping the base embedding model frozen until evidence says otherwise.
- Diverged by prioritizing eval repair and scorer-path unification before new modeling work.
- Replaced the “best face per decade” idea with a small quality-aware prototype bank plus a multifeature reranker.
- Kept LoRA/PEFT as a gated experiment only; current evidence supports adapter experimentation, not rollout.
- Extended the package to include prompt/state lineage so future Gemini-derived labels are auditable and A/B-testable.

## Verification
- Focused slices passed throughout implementation, including the new reranker, active-learning, recalibration, and adapter harness tests.
- Final merged-branch gate:
  - `pytest tests/ -x -q` → `4116 passed, 21 skipped`
  - `pytest rhodesli_ml/tests/ -x -q` → `578 passed, 2 skipped`
- Phase reports captured:
  - `docs/assessments/session-97-phase0-baseline.json`
  - `docs/assessments/session-97-phase2-shadow-report.json`
  - `docs/assessments/session-97-phase3-queue-report.json`
  - `docs/assessments/session-97-phase4-adapter-report.json`

## Gaps / Next Steps
- Phase 2 gate is still closed because age-gap and top-1 improvements were not strong enough on current data.
- Phase 4 gate is still closed because the current split lacks enough `year_gap >= 20` evidence to justify rollout.
- Prompt-manifest and calibration/state-event schema changes still need production migration execution beyond the local implementation package.
- The user-requested cross-app state-event coverage matrix is still the next documentation/implementation gap before more Gemini outputs become training inputs.
- Cloud scaling remains roadmap-only: local-first is intact, but the thresholded migration path is now documented for queued cloud workers when runtime, volume, or concurrency demand it.
