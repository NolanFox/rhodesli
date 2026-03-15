# Reranker Review — Session 103

**Date:** 2026-03-15 | **Session:** 103
**Related:** AD-220, AD-222, PRD-038, AD-224

## Summary

Session 103 ran the longitudinal reranker in shadow mode against baseline clustering.
**Result: Identical proposals. Zero differences.**

This document explains why, and defines when to revisit.

## What Was Tested

| Run | Scorer | Proposals | VERY HIGH | HIGH |
|-----|--------|-----------|-----------|------|
| Baseline | Euclidean distance | 470 | 86 | 384 |
| Reranker (shadow) | longitudinal-shadow | 470 | 86 | 384 |

**Diff:** 0 target changes, 0 tier changes, 0 score changes, 0 added, 0 removed.

## Why Zero Difference (Not a Bug)

### 1. Best variant was `distance_only`

The reranker training tried 4 feature variants:
- `distance_only` — baseline distance + rank + gap features (WINNER)
- `temporal` — adds age-gap, decade spread, date overlap
- `kinship` — adds GEDCOM relationship distance
- `full` — all features combined

The model selected `distance_only` because temporal/kinship features added noise with only ~95 confirmed identities.

### 2. distance_only features are deterministic functions of baseline

The 4 features used:
- `baseline_distance` (the raw Euclidean score)
- `baseline_rank` (1, 2, 3...)
- `distance_gap_to_best` (distance - best_distance)
- `distance_gap_to_competitor` (distance - competitor_distance)

All are deterministic transforms of baseline ordering. The HistGradientBoostingClassifier learned a monotonic mapping from distance → probability. Sorting by probability descending gives identical ordering to sorting by distance ascending.

### 3. Baseline is already near-ceiling

- **Top-1 recall:** 99.17% (baseline) = 99.17% (reranker)
- **AUC:** 0.9841 (baseline) vs 0.9992 (reranker) — reranker separates better but doesn't reorder
- **Phase 2 gate FAILED:** Age-gap improvement = 0.0%, needs ≥5%

### 4. Reranker doesn't discover new matches

The reranker only **reranks the top-5 candidates** that baseline already found. It cannot:
- Pull in faces that baseline missed entirely
- Lower distance thresholds for same-family members
- Expand search radius using confirmed cluster signal

This is a **reranker**, not a **retriever**.

## What About FB-147 (Big Leon)?

The FB-147 false positive (Big Leon appearing in Fox Family suggestions) had 1 proposal at distance 0.9455. The reranker cannot suppress this — it's within threshold and the reranker agrees with baseline's score.

**Actual fix:** Community-scoped filtering (shipped in Session 103 Phase 4). This is a **data scoping** problem, not a **scoring** problem.

## When to Revisit

### Trigger 1: Fox Family Speed-Run Completion
After completing the Fox Family triage (~467 remaining clusters), we'll have:
- More confirmed identities with age-gap diversity (currently ~95 total, ~8 Fox)
- More negative pairs (rejected matches)
- Better signal for temporal features

**Threshold:** When Fox triage reaches 50+ confirmed Fox identities, re-run:
```bash
source venv/bin/activate
python scripts/cluster_new_faces.py --scorer longitudinal-shadow --dry-run
python scripts/compare_ml_runs.py --file-a data/proposals.json --file-b data/proposals_shadow.json
```

### Trigger 2: 200+ Confirmed Identities Total
The Phase 2 gate requires ≥5% age-gap improvement. With more training data, temporal features may become significant.

### Trigger 3: Retrieval-Augmented Approach
If reranking continues to show no improvement, consider a different architecture:
- Use confirmed clusters as "anchors" to expand search radius for family members
- Lower distance threshold for faces near confirmed same-family identities
- This would be a new AD entry, not an extension of the reranker

## Artifacts

| File | Purpose |
|------|---------|
| `docs/ml/run_results/baseline_run_103.md` | Baseline clustering details |
| `docs/ml/run_results/reranker_comparison_103.md` | Shadow comparison results |
| `scripts/compare_ml_runs.py` | Diff tool for comparing any two runs |
| `scripts/cluster_new_faces.py` | Pipeline with `--scorer` flag |
| `rhodesli_ml/longitudinal_reranker.py` | Reranker implementation |

## Decision

**Do NOT activate reranker.** Keep in shadow mode. Revisit after Fox triage speed-run reaches 50+ confirmed Fox identities, or 200+ confirmed identities total.

See: AD-224 for the formal decision entry.
