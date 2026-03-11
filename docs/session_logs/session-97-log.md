# Session 97 Log
Started: 2026-03-11
Prompt: docs/prompts/session-97-prompt.md
Context: docs/session_context/session-97-context.md

## Worktree
- Branch: `codex-session-97-impl`
- Path: `/tmp/rhodesli-session-97-impl`
- Start head: `2fe7942`
- Base app head at worktree creation: `8b45e37`
- Planning package merged from: `codex-prd-038-plan` @ `25f6bc2`

## Initial Conditions
- Main checkout intentionally left dirty for Session 96 cleanup:
  - `app/identity_routes.py`
  - `app/main.py`
  - `app/page_routes.py`
  - `data/identities.json`
- Parallel worktrees present at start:
  - `/tmp/rhodesli-prd038-plan`
  - `/tmp/rhodesli-session-98-gedcom`
- Gemini review artifacts present and treated as required inputs.

## Phase Checklist
- [x] Act 0: isolate Session 97 implementation worktree
- [x] Act 0: merge approved PRD-038 planning package into implementation branch
- [ ] Phase 0: repair mixed-schema eval loaders
- [ ] Phase 0: unify offline scorer path across `core/auto_cluster.py` and `scripts/cluster_new_faces.py`
- [ ] Phase 0: wire prompt-manifest lineage into touched Gemini paths
- [ ] Phase 0: record baseline artifacts and slice metrics
- [ ] Phase 1: recalibration hygiene and label taxonomy
- [ ] Phase 2: longitudinal reranker shadow path
- [ ] Phase 3: active learning in review UX
- [ ] Phase 4: adapter experiment harness
- [ ] Final verification and assessment

## Progress
### 2026-03-11 12:09 EDT
- Created isolated Session 97 implementation worktree from `main`.
- Merged the reviewed PRD-038 package into the implementation branch so the build branch contains the approved SDD, research package, Gemini review, lineage specs, and harness breadcrumbs.

### 2026-03-11 12:20 EDT
- Audited Phase 0 codepaths:
  - `core/auto_cluster.py`
  - `scripts/cluster_new_faces.py`
  - `app/upload_routes.py`
  - `scripts/evaluate_golden_set.py`
  - `scripts/evaluate_mls_vs_euclidean.py`
  - Gemini logging paths in `app/estimate_routes.py`, `app/face_alignment.py`, and `app/supabase_data.py`
- Confirmed duplicated embedding loaders still diverge from `app.main.load_face_embeddings()`.
- Reproduced the current Phase 0 failure on live repo data:
  - `python3 scripts/evaluate_golden_set.py --threshold 1.2`
  - `python3 scripts/evaluate_mls_vs_euclidean.py --cross-pairs 50 --seed 42`
  - Both fail on `KeyError: 'embedding'` because current `data/embeddings.npy` rows are `mu`/`sigma_sq` dicts.

### 2026-03-11 12:45 EDT
- Landed shared Phase 0 primitives:
  - `core.embeddings_io.load_face_data()` now handles `mu`, `embedding`, and `embeddings` schemas.
  - `core.identity_scoring` now holds shared best-linkage helpers used by:
    - `core/auto_cluster.py`
    - `scripts/cluster_new_faces.py`
    - upload proposal generation via the existing script wrapper
- Repaired live eval commands using the shared loader.
- Added prompt-manifest lineage helper:
  - `rhodesli_ml/prompt_manifest.py`
- Wired explicit prompt lineage fields into Gemini logging for:
  - `app.estimate_routes._call_gemini_date_estimate`
  - `app.face_alignment.call_gemini_alignment`
- Added SQL artifacts for prompt lineage fields and a `prompt_manifests` table.

### 2026-03-11 12:52 EDT
- Used shared project venv at `/Users/nolanfox/rhodesli/venv` for dependency-complete validation.
- Focused test passes:
  - `pytest tests/test_estimate_gemini.py tests/test_gemini_api_logging.py tests/test_combined_pipeline.py -q` → `52 passed`
  - `pytest tests/test_ml_clustering.py tests/test_auto_cluster.py tests/test_mls_vs_euclidean.py -q` → `124 passed`
  - `pytest tests/test_session92_gemini_ml.py tests/test_face_alignment.py tests/test_face_alignment_supabase.py -q` → `80 passed`
- Added explicit test coverage for:
  - mixed-schema `embeddings.npy` loading
  - prompt-manifest field persistence in `gemini_api_calls`
  - face-alignment prompt lineage forwarding

### 2026-03-11 12:58 EDT
- Live Phase 0 baseline captured in:
  - `docs/assessments/session-97-phase0-baseline.json`
- Repaired live eval outputs now match the planning package:
  - stale golden set still at `125` mappings / `23` identities
  - dry-run rebuilt golden set would be `257` mappings / `84` identities
  - Euclidean at threshold `1.196`: precision `0.9005`, recall `0.8424`, F1 `0.8705`
  - MLS vs Euclidean (`cross_pairs=200`, `seed=42`): Euclidean AUC `0.9844`, MLS AUC `0.9446`

### 2026-03-11 13:15 EDT
- Added `scripts/evaluate_longitudinal.py` as the reproducible Phase 0 baseline command.
- Corrected MLS baseline identity loading so confirmed candidate faces count as confirmed ground truth in the MLS-vs-Euclidean path.
- Generated versioned baseline artifacts:
  - `evaluation/golden_set_v2.json`
  - `evaluation/baselines/longitudinal_phase0_baseline.json`
- Current rebuilt baseline on live repo data:
  - Golden Set V2: `257` mappings / `84` identities / `46` photos
  - Euclidean @ `1.196`: precision `0.9036`, recall `0.8451`, F1 `0.8734`
  - Dominant positive-pair recall: `0.8747`
  - Tail positive-pair recall: `0.7143`
  - MLS vs Euclidean (same=`1453`, cross=`200`): Euclidean AUC `0.9851`, MLS AUC `0.9245`

### 2026-03-11 13:18 EDT
- User merge-order instruction recorded here for compaction safety:
  - commit regularly and push when done
  - do not merge this worktree until Session 96 has completed and pushed
  - merge Session 97 before Session 98
  - preserve full audit/review/rollback traceability in harness artifacts

## Open Notes
- First implementation slice will centralize face-data loading and shared best-linkage scoring before touching thresholds.
- Prompt-manifest lineage will be added to `gemini_api_calls` as explicit columns plus caller-side manifest fields for date estimation and face alignment.
