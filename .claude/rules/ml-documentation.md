---
paths:
  - rhodesli_ml/**
  - scripts/cluster_new_faces.py
  - scripts/apply_cluster_matches.py
  - scripts/evaluate_golden_set.py
  - scripts/calibrate_thresholds.py
  - scripts/build_golden_set.py
  - core/neighbors.py
  - core/clustering.py
  - core/grouping.py
  - core/temporal.py
  - core/pfe.py
  - core/config.py
  - docs/ml/**
---

# ML Documentation Rule

## ALGORITHMIC_DECISIONS.md is the ML source of truth

`docs/ml/ALGORITHMIC_DECISIONS.md` records EVERY decision about how the ML system works: thresholds, model choices, training strategies, evaluation criteria, data handling.

### When to update (MANDATORY):
- After changing ANY threshold, distance metric, or confidence tier
- After adding or modifying clustering/grouping logic
- After adding a new model, training script, or evaluation metric
- After making architectural decisions (framework choices, phase sequencing)
- After discovering data characteristics that affect model design (signal inventory, class imbalance)
- After completing ANY task that touches `rhodesli_ml/` files
- After modifying golden set evaluation or calibration scripts

### Format:
Each decision gets an AD-NNN entry (next: AD-028) with: Date, Context, Decision, Rationale, Evidence (if empirical), and Affects (what code/config it impacts).

### Cross-reference:
- `rhodesli_ml/config/*.yaml` should reference AD entries for hyperparameter choices
- `rhodesli_ml/README.md` should link to ALGORITHMIC_DECISIONS.md
- Training scripts should log which AD entries their parameters come from

### The test:
If someone reads ONLY `ALGORITHMIC_DECISIONS.md`, they should understand:
1. Why we chose this approach over alternatives
2. What evidence supports each decision
3. What the known limitations and future experiments are
4. The complete sequencing of ML phases and their dependencies
