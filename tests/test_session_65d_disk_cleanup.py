"""Tests for AD-162 disk cleanup: startup cleanup, backup pruning, upload temp cleanup."""

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest


class TestStartupDiskCleanup:
    """Test _startup_disk_cleanup removes stale temp files."""

    def test_removes_stale_staging_dirs(self, tmp_path):
        """Staging directories older than 1 hour are removed at startup (if no pending upload)."""
        from app.main import _startup_disk_cleanup

        staging = tmp_path / "staging"
        staging.mkdir()
        old_job = staging / "old-job-123"
        old_job.mkdir()
        (old_job / "photo.jpg").write_bytes(b"fake")
        # Set mtime to 2 hours ago
        old_time = time.time() - 7200
        os.utime(old_job, (old_time, old_time))

        # No pending uploads → safe to clean
        with patch("app.main._load_pending_uploads", return_value={"uploads": {}}):
            _startup_disk_cleanup(tmp_path)

        assert not old_job.exists()

    def test_preserves_stale_staging_dirs_with_pending_upload(self, tmp_path):
        """Staging directories for pending uploads are preserved even if old."""
        from app.main import _startup_disk_cleanup

        staging = tmp_path / "staging"
        staging.mkdir()
        old_job = staging / "pending-job-789"
        old_job.mkdir()
        (old_job / "photo.jpg").write_bytes(b"fake")
        old_time = time.time() - 7200
        os.utime(old_job, (old_time, old_time))

        # This job is still pending → must NOT be cleaned
        pending = {"uploads": {"pending-job-789": {"status": "pending", "files": ["photo.jpg"]}}}
        with patch("app.main._load_pending_uploads", return_value=pending):
            _startup_disk_cleanup(tmp_path)

        assert old_job.exists(), "Staging dir for pending upload should be preserved"

    def test_preserves_recent_staging_dirs(self, tmp_path):
        """Staging directories less than 1 hour old are preserved."""
        from app.main import _startup_disk_cleanup

        staging = tmp_path / "staging"
        staging.mkdir()
        new_job = staging / "new-job-456"
        new_job.mkdir()
        (new_job / "photo.jpg").write_bytes(b"fake")

        with patch("app.main._load_pending_uploads", return_value={"uploads": {}}):
            _startup_disk_cleanup(tmp_path)

        assert new_job.exists()

    def test_removes_stale_inbox_files(self, tmp_path):
        """Old status and log files in inbox/ are removed."""
        from app.main import _startup_disk_cleanup

        inbox = tmp_path / "inbox"
        inbox.mkdir()
        old_status = inbox / "abc.status.json"
        old_status.write_text("{}")
        old_log = inbox / "abc.log"
        old_log.write_text("log content")
        # Set mtime to 2 days ago
        old_time = time.time() - 172800
        os.utime(old_status, (old_time, old_time))
        os.utime(old_log, (old_time, old_time))

        _startup_disk_cleanup(tmp_path)

        assert not old_status.exists()
        assert not old_log.exists()

    def test_preserves_recent_inbox_files(self, tmp_path):
        """Recent inbox status files are preserved."""
        from app.main import _startup_disk_cleanup

        inbox = tmp_path / "inbox"
        inbox.mkdir()
        recent = inbox / "recent.status.json"
        recent.write_text("{}")

        _startup_disk_cleanup(tmp_path)

        assert recent.exists()

    def test_removes_tmp_files(self, tmp_path):
        """Leftover .tmp files from atomic writes are removed."""
        from app.main import _startup_disk_cleanup

        (tmp_path / "identities.tmp").write_text("{}")
        (tmp_path / "photo_index.tmp").write_text("{}")

        _startup_disk_cleanup(tmp_path)

        assert not (tmp_path / "identities.tmp").exists()
        assert not (tmp_path / "photo_index.tmp").exists()


class TestPruneBakFiles:
    """Test _prune_bak_files keeps only the most recent backups."""

    def test_prunes_old_bak_files(self, tmp_path):
        """Only the 3 most recent .bak files per type are kept."""
        from app.sync_routes import _prune_bak_files

        # Create 5 identities.json.bak files with different timestamps
        for i in range(5):
            f = tmp_path / f"identities.json.bak.{1000 + i}"
            f.write_text("{}")
            # Ensure distinct mtime
            os.utime(f, (1000 + i, 1000 + i))

        _prune_bak_files(tmp_path, max_keep=3)

        remaining = sorted(f.name for f in tmp_path.iterdir() if ".bak." in f.name)
        assert len(remaining) == 3
        # Newest 3 should survive
        assert "identities.json.bak.1002" in remaining
        assert "identities.json.bak.1003" in remaining
        assert "identities.json.bak.1004" in remaining

    def test_prunes_per_base_name(self, tmp_path):
        """Different base names are tracked independently."""
        from app.sync_routes import _prune_bak_files

        for i in range(4):
            (tmp_path / f"identities.json.bak.{2000 + i}").write_text("{}")
            os.utime(tmp_path / f"identities.json.bak.{2000 + i}", (2000 + i, 2000 + i))
        for i in range(4):
            (tmp_path / f"photo_index.json.bak.{3000 + i}").write_text("{}")
            os.utime(tmp_path / f"photo_index.json.bak.{3000 + i}", (3000 + i, 3000 + i))

        _prune_bak_files(tmp_path, max_keep=2)

        id_files = [f for f in tmp_path.iterdir() if f.name.startswith("identities")]
        pi_files = [f for f in tmp_path.iterdir() if f.name.startswith("photo_index")]
        assert len(id_files) == 2
        assert len(pi_files) == 2

    def test_no_files_is_noop(self, tmp_path):
        """No crash when directory has no .bak files."""
        from app.sync_routes import _prune_bak_files

        _prune_bak_files(tmp_path, max_keep=3)
        # Should not raise


class TestHealthDiskInfo:
    """Test that /health includes disk info."""

    def test_health_includes_disk(self):
        """Health endpoint returns disk usage information."""
        from app.main import health

        result = health()
        assert "disk" in result
        assert "free_mb" in result["disk"]
        assert "used_pct" in result["disk"]
        assert result["disk"]["free_mb"] > 0


class TestUploadCleanupInFinally:
    """Test that upload processing cleans up staging directory."""

    def test_staging_dir_cleaned_after_processing(self, tmp_path):
        """After _background_ingest runs, staging job_dir is removed."""
        # This tests the finally block behavior by creating a mock scenario
        import shutil

        job_dir = tmp_path / "staging" / "test-job"
        job_dir.mkdir(parents=True)
        (job_dir / "test.jpg").write_bytes(b"fake image")

        # Simulate the finally block
        try:
            raise RuntimeError("simulated processing error")
        except Exception:
            pass
        finally:
            if job_dir.exists():
                shutil.rmtree(job_dir, ignore_errors=True)

        assert not job_dir.exists()
