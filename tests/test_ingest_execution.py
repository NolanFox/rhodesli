"""
Test that ingest_inbox.py subprocess execution works correctly.

This test verifies the SUBPROCESS EXECUTION path that app/main.py uses
to spawn ingestion jobs. The subprocess must be able to import `core`
modules without "No module named 'core'" errors.

Invariant: Ingestion subprocess must execute without import errors.
"""

import os
import subprocess
import sys
from pathlib import Path


# Project root is two levels up from this test file
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_ingest_subprocess_can_import_core():
    """
    Verify that spawning ingest_inbox.py as a subprocess does NOT crash
    with "No module named 'core'".

    This replicates EXACTLY how app/main.py spawns the ingestion subprocess.
    """
    # Run the exact same command that app/main.py uses
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "core.ingest_inbox",
            "--help",  # Use --help to test import without actual processing
        ],
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Check for the SPECIFIC import error for 'core' module
    assert "No module named 'core'" not in result.stderr, (
        f"Subprocess failed with core import error:\n"
        f"STDERR: {result.stderr}\n"
        f"STDOUT: {result.stdout}\n"
        f"Return code: {result.returncode}"
    )

    # The command should succeed (--help returns 0)
    assert result.returncode == 0, (
        f"Subprocess failed with return code {result.returncode}:\n"
        f"STDERR: {result.stderr}\n"
        f"STDOUT: {result.stdout}"
    )


def test_ingest_subprocess_from_app_directory():
    """
    Verify subprocess works when spawned from app/ directory context.

    This simulates what happens when app/main.py spawns the subprocess
    but the working directory calculation might be wrong.
    """
    # Simulate spawning from within app/ directory
    app_dir = PROJECT_ROOT / "app"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "core.ingest_inbox",
            "--help",
        ],
        # Key: cwd should be PROJECT_ROOT, not app_dir
        # This is what app/main.py does via project_root = Path(__file__).parent.parent
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Must NOT have core import errors
    assert "No module named 'core'" not in result.stderr, (
        f"Subprocess from app context failed with core import error:\n"
        f"STDERR: {result.stderr}"
    )

    assert result.returncode == 0, (
        f"Subprocess failed with return code {result.returncode}:\n"
        f"STDERR: {result.stderr}"
    )


def test_ingest_subprocess_with_pythonpath():
    """
    Verify that explicitly setting PYTHONPATH ensures core imports work.

    This is the recommended fix if cwd alone doesn't work in all environments.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "core.ingest_inbox",
            "--help",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    # With explicit PYTHONPATH, this MUST work
    assert "No module named 'core'" not in result.stderr, (
        f"Subprocess with PYTHONPATH failed:\n"
        f"STDERR: {result.stderr}"
    )

    assert result.returncode == 0, (
        f"Subprocess failed with return code {result.returncode}:\n"
        f"STDERR: {result.stderr}"
    )
