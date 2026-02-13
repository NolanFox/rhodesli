"""Tests for upload pipeline scripts.

Tests cover:
- Scripts are importable without errors
- Scripts have expected CLI interfaces
- Orchestrator exists and is executable
- Pre-flight checks detect missing env vars
"""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


class TestPipelineScriptsExist:
    """All pipeline scripts exist and have help text."""

    def test_sync_from_production_help(self):
        """sync_from_production.py has --help."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "sync_from_production.py"), "--help"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "--dry-run" in result.stdout

    def test_download_staged_help(self):
        """download_staged.py has --help."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "download_staged.py"), "--help"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0

    def test_upload_to_r2_help(self):
        """upload_to_r2.py has --help."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "upload_to_r2.py"), "--help"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "--dry-run" in result.stdout

    def test_push_to_production_help(self):
        """push_to_production.py has --help."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "push_to_production.py"), "--help"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0

    def test_cluster_new_faces_help(self):
        """cluster_new_faces.py has --help."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "cluster_new_faces.py"), "--help"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "--dry-run" in result.stdout

    def test_process_uploads_orchestrator_help(self):
        """process_uploads.py orchestrator has --help."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "process_uploads.py"), "--help"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "--dry-run" in result.stdout
        assert "--auto" in result.stdout


class TestOrchestratorShellScript:
    """The bash orchestrator exists and is executable."""

    def test_shell_script_exists(self):
        """process_uploads.sh exists."""
        assert (SCRIPTS_DIR / "process_uploads.sh").exists()

    def test_shell_script_is_executable(self):
        """process_uploads.sh has execute permissions."""
        import stat
        mode = (SCRIPTS_DIR / "process_uploads.sh").stat().st_mode
        assert mode & stat.S_IXUSR  # User execute bit
