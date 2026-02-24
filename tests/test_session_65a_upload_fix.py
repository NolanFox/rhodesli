"""
Session 65a — Upload status monitoring: subprocess death detection + timeout.

Fixes the bug where upload progress bar freezes at "Processing 0/1 (0%)"
when the subprocess crashes (OOM, segfault, etc.) during face detection.

Root cause: The status poller had no timeout or process-alive check for
the "processing" state. Only the "starting" state had a 2-minute timeout.
"""

import json
import os
import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta


class TestUploadProcessingSubprocessDeath:
    """When the processing subprocess dies, the UI must show an error."""

    def test_processing_dead_subprocess_shows_error(self, client, auth_disabled, tmp_path):
        """If subprocess PID no longer exists, show crash error."""
        status_data = {
            "status": "processing",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "total_files": 1,
            "files_succeeded": 0,
            "files_failed": 0,
            "current_file": "test_photo.jpg",
            "pid": 999999999,  # Non-existent PID
        }
        with patch("app.main.data_path", tmp_path):
            inbox_dir = tmp_path / "inbox"
            inbox_dir.mkdir()
            (inbox_dir / "test-job.status.json").write_text(json.dumps(status_data))
            response = client.get("/upload/status/test-job")

        assert response.status_code == 200
        assert "failed" in response.text.lower()
        assert "crashed" in response.text.lower() or "out of memory" in response.text.lower()
        # Should NOT be polling anymore
        assert "hx-trigger" not in response.text

    def test_processing_dead_subprocess_shows_log_excerpt(self, client, auth_disabled, tmp_path):
        """When subprocess crashes, error should include log output."""
        status_data = {
            "status": "processing",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "total_files": 1,
            "files_succeeded": 0,
            "pid": 999999999,
        }
        with patch("app.main.data_path", tmp_path):
            inbox_dir = tmp_path / "inbox"
            inbox_dir.mkdir()
            (inbox_dir / "test-job.status.json").write_text(json.dumps(status_data))
            (inbox_dir / "test-job.log").write_text(
                "Killed\nOut of memory: Kill process 12345\n"
            )
            response = client.get("/upload/status/test-job")

        assert response.status_code == 200
        assert "Log output" in response.text
        assert "Killed" in response.text or "memory" in response.text.lower()

    def test_processing_timeout_shows_error(self, client, auth_disabled, tmp_path):
        """Processing status past 5-minute timeout should show error."""
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
        status_data = {
            "status": "processing",
            "started_at": old_time,
            "total_files": 1,
            "files_succeeded": 0,
            "files_failed": 0,
            "current_file": "test_photo.jpg",
            "pid": os.getpid(),  # Current process — still alive
        }
        with patch("app.main.data_path", tmp_path):
            inbox_dir = tmp_path / "inbox"
            inbox_dir.mkdir()
            (inbox_dir / "test-job.status.json").write_text(json.dumps(status_data))
            response = client.get("/upload/status/test-job")

        assert response.status_code == 200
        assert "failed" in response.text.lower() or "timed out" in response.text.lower()
        # Should NOT be polling anymore
        assert "hx-trigger" not in response.text

    def test_processing_alive_subprocess_keeps_polling(self, client, auth_disabled, tmp_path):
        """If subprocess is alive and within timeout, keep showing progress."""
        status_data = {
            "status": "processing",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "total_files": 1,
            "files_succeeded": 0,
            "files_failed": 0,
            "current_file": "test_photo.jpg",
            "pid": os.getpid(),  # Current process — still alive
        }
        with patch("app.main.data_path", tmp_path):
            inbox_dir = tmp_path / "inbox"
            inbox_dir.mkdir()
            (inbox_dir / "test-job.status.json").write_text(json.dumps(status_data))
            response = client.get("/upload/status/test-job")

        assert response.status_code == 200
        assert "Processing 0/1 (0%)" in response.text
        # Should still be polling
        assert "hx-get" in response.text or "hx_get" in response.text

    def test_processing_no_pid_still_has_timeout(self, client, auth_disabled, tmp_path):
        """Old status files without PID should still timeout after 5 min."""
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
        status_data = {
            "status": "processing",
            "started_at": old_time,
            "total_files": 1,
            "files_succeeded": 0,
            "files_failed": 0,
            # No pid field (old format)
        }
        with patch("app.main.data_path", tmp_path):
            inbox_dir = tmp_path / "inbox"
            inbox_dir.mkdir()
            (inbox_dir / "test-job.status.json").write_text(json.dumps(status_data))
            response = client.get("/upload/status/test-job")

        assert response.status_code == 200
        assert "failed" in response.text.lower() or "timed out" in response.text.lower()

    def test_processing_tells_user_photo_saved(self, client, auth_disabled, tmp_path):
        """Error message should reassure user their photo was saved."""
        status_data = {
            "status": "processing",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "total_files": 1,
            "files_succeeded": 0,
            "pid": 999999999,  # Dead process
        }
        with patch("app.main.data_path", tmp_path):
            inbox_dir = tmp_path / "inbox"
            inbox_dir.mkdir()
            (inbox_dir / "test-job.status.json").write_text(json.dumps(status_data))
            response = client.get("/upload/status/test-job")

        assert response.status_code == 200
        assert "saved" in response.text.lower()


class TestWriteStatusFilePreservesFields:
    """write_status_file must preserve started_at and pid from initial status."""

    def test_preserves_started_at(self, tmp_path):
        """started_at from the initial status must survive status updates."""
        from core.ingest_inbox import write_status_file

        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()

        # Write initial status with started_at and pid
        initial = {
            "status": "starting",
            "started_at": "2026-02-23T12:00:00+00:00",
            "pid": 12345,
        }
        (inbox_dir / "test-job.status.json").write_text(json.dumps(initial))

        # Subprocess writes "processing" status
        write_status_file(inbox_dir, "test-job", "processing", total_files=1)

        with open(inbox_dir / "test-job.status.json") as f:
            result = json.load(f)

        assert result["status"] == "processing"
        assert result["started_at"] == "2026-02-23T12:00:00+00:00"
        assert result["pid"] == 12345

    def test_preserves_pid(self, tmp_path):
        """pid from the initial status must survive status updates."""
        from core.ingest_inbox import write_status_file

        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()

        initial = {
            "status": "starting",
            "started_at": "2026-02-23T12:00:00+00:00",
            "pid": 99999,
        }
        (inbox_dir / "test-job.status.json").write_text(json.dumps(initial))

        write_status_file(inbox_dir, "test-job", "success", faces_extracted=3)

        with open(inbox_dir / "test-job.status.json") as f:
            result = json.load(f)

        assert result["status"] == "success"
        assert result["pid"] == 99999
