"""
Regression test for subprocess entrypoint invocation.

Ensures that `python -m core.ingest_inbox` can be invoked from the project root
without ModuleNotFoundError. This matches the real invocation pattern used by
app/main.py when processing uploads.

This test does NOT mock subprocess calls - it invokes the real entrypoint.
"""

import subprocess
import sys
from pathlib import Path

# Single source of truth for project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_ingest_inbox_module_invocation():
    """
    Verify that core.ingest_inbox can be invoked as a module.

    This test matches the exact invocation used by app/main.py:
    - Uses sys.executable (same Python interpreter)
    - Uses -m core.ingest_inbox (module invocation)
    - Sets cwd=PROJECT_ROOT (deterministic execution context)
    """
    result = subprocess.run(
        [sys.executable, "-m", "core.ingest_inbox", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    # Assert no module import errors
    assert "ModuleNotFoundError" not in result.stderr, (
        f"Module import failed: {result.stderr}"
    )
    assert "No module named" not in result.stderr, (
        f"Module not found: {result.stderr}"
    )

    # Assert successful execution (--help should exit 0)
    assert result.returncode == 0, (
        f"Entrypoint failed with code {result.returncode}. "
        f"stderr: {result.stderr}"
    )

    # Assert help output contains expected content
    assert "usage:" in result.stdout.lower() or "usage:" in result.stderr.lower(), (
        "Expected argparse help output"
    )
