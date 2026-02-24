"""
Session 65a/65c — Upload status monitoring: timeout detection + thread-based processing.

Original (65a): Added subprocess PID tracking for death detection.
Updated (65c, AD-161): Replaced subprocess with background thread. PID tracking
removed — timeout is the safety net for stuck processing.

Root cause of upload freeze: subprocess loaded buffalo_l model (~300-500MB)
separately from the main app, exceeding Railway's 512MB memory limit.
Fix: background thread shares the main app's already-loaded hybrid models.
"""

import json
import os
import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta


class TestUploadProcessingTimeout:
    """Processing timeout detection shows errors to the user."""

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

    def test_processing_timeout_shows_log_excerpt(self, client, auth_disabled, tmp_path):
        """When processing times out, error should include log output if available."""
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
        status_data = {
            "status": "processing",
            "started_at": old_time,
            "total_files": 1,
            "files_succeeded": 0,
        }
        with patch("app.main.data_path", tmp_path):
            inbox_dir = tmp_path / "inbox"
            inbox_dir.mkdir()
            (inbox_dir / "test-job.status.json").write_text(json.dumps(status_data))
            (inbox_dir / "test-job.log").write_text(
                "INFO: Processing test_photo.jpg\nError: something went wrong\n"
            )
            response = client.get("/upload/status/test-job")

        assert response.status_code == 200
        assert "Log output" in response.text

    def test_processing_within_timeout_keeps_polling(self, client, auth_disabled, tmp_path):
        """If processing is recent and within timeout, keep showing progress."""
        status_data = {
            "status": "processing",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "total_files": 1,
            "files_succeeded": 0,
            "files_failed": 0,
            "current_file": "test_photo.jpg",
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

    def test_processing_no_started_at_still_shows_progress(self, client, auth_disabled, tmp_path):
        """Status files without started_at should still show progress (no crash)."""
        status_data = {
            "status": "processing",
            "total_files": 1,
            "files_succeeded": 0,
            "files_failed": 0,
            # No started_at field
        }
        with patch("app.main.data_path", tmp_path):
            inbox_dir = tmp_path / "inbox"
            inbox_dir.mkdir()
            (inbox_dir / "test-job.status.json").write_text(json.dumps(status_data))
            response = client.get("/upload/status/test-job")

        assert response.status_code == 200
        # Should not crash — shows progress
        assert "Processing" in response.text

    def test_processing_timeout_tells_user_photo_saved(self, client, auth_disabled, tmp_path):
        """Timeout error message should reassure user their photo was saved."""
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
        status_data = {
            "status": "processing",
            "started_at": old_time,
            "total_files": 1,
            "files_succeeded": 0,
        }
        with patch("app.main.data_path", tmp_path):
            inbox_dir = tmp_path / "inbox"
            inbox_dir.mkdir()
            (inbox_dir / "test-job.status.json").write_text(json.dumps(status_data))
            response = client.get("/upload/status/test-job")

        assert response.status_code == 200
        assert "saved" in response.text.lower()


class TestWriteStatusFilePreservesFields:
    """write_status_file must preserve started_at from initial status."""

    def test_preserves_started_at(self, tmp_path):
        """started_at from the initial status must survive status updates."""
        from core.ingest_inbox import write_status_file

        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()

        # Write initial status with started_at
        initial = {
            "status": "starting",
            "started_at": "2026-02-23T12:00:00+00:00",
        }
        (inbox_dir / "test-job.status.json").write_text(json.dumps(initial))

        # Thread writes "processing" status
        write_status_file(inbox_dir, "test-job", "processing", total_files=1)

        with open(inbox_dir / "test-job.status.json") as f:
            result = json.load(f)

        assert result["status"] == "processing"
        assert result["started_at"] == "2026-02-23T12:00:00+00:00"

    def test_face_ids_written_to_status(self, tmp_path):
        """face_ids should be written to the status file for R2 crop upload."""
        from core.ingest_inbox import write_status_file

        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()

        write_status_file(
            inbox_dir, "test-job", "success",
            faces_extracted=2,
            identities_created=["uuid-1"],
            face_ids=["inbox_abc123", "inbox_def456"],
        )

        with open(inbox_dir / "test-job.status.json") as f:
            result = json.load(f)

        assert result["face_ids"] == ["inbox_abc123", "inbox_def456"]


class TestPreferHybridParameter:
    """extract_faces prefer_hybrid parameter uses hybrid models when available."""

    def test_process_single_image_accepts_prefer_hybrid(self):
        """process_single_image should accept prefer_hybrid parameter without error."""
        import inspect
        from core.ingest_inbox import process_single_image
        sig = inspect.signature(process_single_image)
        assert "prefer_hybrid" in sig.parameters

    def test_process_directory_accepts_prefer_hybrid(self):
        """process_directory should accept prefer_hybrid parameter without error."""
        import inspect
        from core.ingest_inbox import process_directory
        sig = inspect.signature(process_directory)
        assert "prefer_hybrid" in sig.parameters

    def test_extract_faces_accepts_prefer_hybrid(self):
        """extract_faces should accept prefer_hybrid parameter."""
        import inspect
        from core.ingest_inbox import extract_faces
        sig = inspect.signature(extract_faces)
        assert "prefer_hybrid" in sig.parameters
