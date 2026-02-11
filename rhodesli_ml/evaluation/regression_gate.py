"""Regression gate: blocks model deployment if golden set metrics degrade.

Before any model is deployed to production, it must pass:
1. Golden set precision >= current threshold (100% at distance < 1.05)
2. Golden set recall >= current recall - 5% tolerance
3. No regression on known hard cases (ambiguous pairs)

This is the safety net that prevents ML changes from degrading user experience.
"""

# Placeholder — will be implemented after first model training.
#
# Interface:
# - run_regression_gate(model_path, golden_set_path) -> GateResult
# - GateResult: passed, metrics, regressions, warnings
# - CI integration: exit code 0 = pass, 1 = fail
