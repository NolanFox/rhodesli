# Session 97 Log — PRD-038 Longitudinal ML Foundation
## Mission: implement the reviewed PRD-038 package end-to-end in an isolated worktree, keep live matcher changes gated behind evals, and leave a traceable merge path for Session 98
## Started: 2026-03-11
## Version: v0.98.0
## Assessment: docs/assessments/session-97-assessment.md

### Phase 1: Foundation
- [x] Merged the reviewed PRD-038 planning package into an isolated Session 97 branch/worktree
- [x] Repaired mixed-schema eval scripts and rebuilt the longitudinal baseline
- [x] Unified scorer-path logic shared by clustering and offline proposal generation
- [x] Added prompt-manifest lineage to touched Gemini callers

### Phase 2: ML Implementation
- [x] `rhodesli_ml/calibration_lineage.py` + `scripts/recalibrate.py`: reversible calibration labels, local recalibration hygiene, audit mirroring
- [x] `rhodesli_ml/longitudinal_reranker.py`: prototype-bank reranker in shadow mode with slice reporting
- [x] `rhodesli_ml/active_learning.py` + `app/cluster_review_routes.py`: active-learning queue, review actions, reversible labels
- [x] `rhodesli_ml/embedding_adapter_experiment.py`: frozen-embedding adapter experiment harness

### Phase 3: Verification
- [x] Phase-focused slices passed during implementation across eval repair, reranker, active learning, recalibration, and adapter experiments
- [x] Full required gate:
  - `pytest tests/ -x -q` -> `4116 passed, 21 skipped`
  - `pytest rhodesli_ml/tests/ -x -q` -> `578 passed, 2 skipped`
- [x] Merged `origin/main` (`892f72b`, Session 96f-cont1) into the Session 97 branch before final verification
- [x] Residual warnings documented explicitly rather than hidden (Starlette deprecations, MLflow filesystem deprecations, Lightning trainer-registration warnings, intermittent full-suite recalibration-hook warning)

### Phase 4: Documentation + Lessons
- [x] `docs/assessments/session-97-assessment.md`
- [x] `docs/session_logs/session-97-log.md`
- [x] `CHANGELOG.md`, `ROADMAP.md`, `docs/BACKLOG.md`, and `docs/session_logs/INDEX.md` updated
- [x] Session 97 branch left merge-ready for Session 98 to stack on top afterward
- [x] No destructive data operations were introduced; live matcher changes remain gated off

### Key Commits
- `50b68f2` `[codex] feat(ml): repair eval path and prompt lineage`
- `ad9bb73` `[codex] feat(eval): add longitudinal baseline command`
- `c198caf` `[codex] feat(calibration): harden local recalibration workflow`
- `a0aa2ce` `[codex] feat(ml): add shadow reranker and active learning harness`
- `850862d` `[codex] test(ml): harden session 97 verification gates`
- `15dd09b` `Merge remote-tracking branch 'origin/main' into codex-session-97-impl`
