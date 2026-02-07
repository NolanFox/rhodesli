# Task: Add ML Algorithmic Decision Capture System

**Session**: 2026-02-06 (session 8)
**Status**: IN PROGRESS

## Phase 1: Create ML Docs
- [x] Create `docs/ml/ALGORITHMIC_DECISIONS.md` with AD-001 through AD-006
- [x] Create `docs/ml/MODEL_INVENTORY.md` with accurate model info

## Phase 2: Path-Scoped Rules
- [x] Create `.claude/rules/ml-pipeline.md` with paths for all ML files
- [x] Create `.claude/rules/data-files.md` with paths for data files
- [x] Verified `.claude/rules/` format is correct (YAML frontmatter + paths)

## Phase 3: Update Project Files
- [x] Add rules 10-11 to CLAUDE.md
- [x] Add ML docs to CLAUDE.md Key Docs table
- [x] Add lessons 27-28 to tasks/lessons.md

## Phase 4: Audit ML Code
- [x] `core/neighbors.py` — CLEAN. Multi-anchor (best-linkage) confirmed. Docstring explicitly says "Avoid centroid poisoning". `sort_faces_by_outlier_score` uses mean but only for intra-identity outlier detection, not cross-identity matching.
- [x] `core/clustering.py` — CLEAN. Pairwise MLS between all face pairs. Complete linkage. No centroid averaging.
- [x] `core/fusion.py` — ACCEPTABLE. Uses Bayesian fusion (weighted by inverse variance), NOT naive centroid. Used for variance explosion checks and re-evaluation, not for primary matching.
- [x] **VIOLATION FOUND**: `scripts/cluster_new_faces.py` — Uses centroid averaging (lines 124-141). `compute_centroid()` does `np.mean(np.vstack(embeddings), axis=0)` and matches new faces against these centroids. This is the exact pattern AD-001 rejects.

## TODO: Fix AD-001 violation in scripts/cluster_new_faces.py
- [ ] Replace `compute_centroid()` + `compute_distance_to_centroid()` with multi-anchor matching (min-distance to any anchor)
- [ ] Requires golden set testing before and after — do NOT fix without running `scripts/evaluate_golden_set.py`
- [ ] NOT fixing in this session — needs careful testing with ML dependencies

## Phase 5: Commit & Push
- [ ] Commit all changes
- [ ] Push to main

## Previous Session (2026-02-06, session 7)
- Photo Bug Fix + Documentation Restructure: COMPLETE
- 553 tests passing at end of session
