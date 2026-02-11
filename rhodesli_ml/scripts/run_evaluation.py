"""Run golden set evaluation and regression gate checks.

Usage:
    python -m rhodesli_ml.scripts.run_evaluation
    python -m rhodesli_ml.scripts.run_evaluation --threshold 1.05
"""

# Placeholder — will call evaluation/regression_gate.py once implemented.
#
# Pipeline:
# 1. Load golden set mappings
# 2. Load embeddings
# 3. Compute pairwise distances for all golden set pairs
# 4. Evaluate precision/recall at each threshold
# 5. Compare against current calibrated thresholds (AD-013)
# 6. Report pass/fail for regression gate
