#!/usr/bin/env python
"""Verify the ML test suite is CI-safe: it must PASS or SKIP (never fail/error)
when the heavy deps that CI does NOT install are unavailable.

Why this exists (Session 168): CI installs `requirements.txt` only. `insightface`
transitively pulls in onnx, scikit-learn, matplotlib, joblib — but NOT
torch / torchvision / mlflow / pytorch_lightning / lightning / torchmetrics.
Any `rhodesli_ml/tests/` module that imports one of those (at MODULE, FUNCTION, or
FIXTURE level, or transitively) must guard it with `pytest.importorskip(...)` so
CI degrades gracefully instead of turning main red.

A `--collect-only` check is NOT sufficient — it only catches module-level imports.
This script installs an import blocker and ACTUALLY RUNS the suite (serially, since
the meta_path blocker lives in this process and xdist workers are subprocesses).

Run it whenever you add or change a test under rhodesli_ml/tests/:
    source venv/bin/activate && python scripts/check_ml_suite_ci_safe.py
Exit 0 = CI-safe. Non-zero = a test fails/errors under CI deps → add an importorskip guard.
"""
import importlib.abc
import sys

# Deps genuinely absent in CI (see module docstring). Keep in sync with
# requirements.txt + insightface's transitive deps if either changes.
CI_ABSENT = {
    "torch",
    "torchvision",
    "mlflow",
    "pytorch_lightning",
    "lightning",
    "torchmetrics",
}


class _CIAbsentBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in CI_ABSENT:
            raise ImportError(f"blocked {name} (CI-absent — simulating requirements.txt)")
        return None


def main() -> int:
    sys.meta_path.insert(0, _CIAbsentBlocker())
    import pytest

    rc = pytest.main(
        [
            "rhodesli_ml/tests/",
            "-q",
            "-p", "no:cacheprovider",
            "-p", "no:xdist",  # blocker is in-process; xdist workers wouldn't inherit it
            "-o", "addopts=",  # drop repo -n auto / maxfail
        ]
    )
    print(f"\n=== ML suite under CI-absent blocker: rc={rc} (0 = CI-safe) ===")
    if rc != 0:
        print(
            "FAIL: a test failed/errored without CI-absent deps. Add "
            "`pytest.importorskip(\"<dep>\", exc_type=ImportError)` to the offending module/test.",
            file=sys.stderr,
        )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
