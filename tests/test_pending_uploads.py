"""Tests for the pending upload queue feature.

Tests cover:
- Pending uploads helper functions (_load, _save, _count)
- POST /upload creates pending record for non-admin users
- POST /upload follows existing flow for admin users
- GET /admin/pending requires admin
- POST /admin/pending/{id}/approve requires admin and updates status
- POST /admin/pending/{id}/reject requires admin and updates status
"""

import json
import io
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.auth import User


class TestPendingUploadsHelpers:
    """Unit tests for pending uploads registry helpers."""

    def test_load_returns_empty_when_file_missing(self, tmp_path):
        """_load_pending_uploads returns empty dict when file doesn't exist."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _load_pending_uploads
            result = _load_pending_uploads()
            assert result == {"uploads": {}}

    def test_save_creates_file(self, tmp_path):
        """_save_pending_uploads creates the pending_uploads.json file."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads, _load_pending_uploads
            data = {"uploads": {"abc123": {"job_id": "abc123", "status": "pending"}}}
            _save_pending_uploads(data)
            # Verify file exists
            assert (tmp_path / "pending_uploads.json").exists()
            # Verify content round-trips
            result = _load_pending_uploads()
            assert result == data

    def test_count_pending_uploads_empty(self, tmp_path):
        """_count_pending_uploads returns 0 when no pending uploads exist."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _count_pending_uploads
            assert _count_pending_uploads() == 0

    def test_count_pending_uploads_counts_only_pending(self, tmp_path):
        """_count_pending_uploads counts only uploads with status='pending'."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads, _count_pending_uploads
            data = {
                "uploads": {
                    "a": {"status": "pending"},
                    "b": {"status": "pending"},
                    "c": {"status": "approved"},
                    "d": {"status": "rejected"},
                }
            }
            _save_pending_uploads(data)
            assert _count_pending_uploads() == 2

    def test_save_is_atomic(self, tmp_path):
        """_save_pending_uploads uses atomic write (no .tmp file left behind)."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads
            _save_pending_uploads({"uploads": {}})
            # .tmp file should not exist after save
            assert not (tmp_path / "pending_uploads.tmp").exists()
            assert (tmp_path / "pending_uploads.json").exists()


class TestNonAdminUploadCreatesPending:
    """Non-admin uploads create a pending record in pending_uploads.json."""

    def test_non_admin_upload_creates_pending_record(self, client, auth_enabled, regular_user, tmp_path):
        """POST /upload by non-admin creates a pending upload record."""
        with patch("app.main.data_path", tmp_path), \
             patch("app.main._notify_admin_upload", return_value=None):
            # Create staging dir
            (tmp_path / "staging").mkdir(parents=True, exist_ok=True)

            # Upload a file
            file_content = b"fake image data"
            response = client.post(
                "/upload",
                files={"files": ("test_photo.jpg", io.BytesIO(file_content), "image/jpeg")},
                data={"source": "Test Collection"},
            )
            assert response.status_code == 200

            # Verify response mentions submission for review
            assert "submitted" in response.text.lower() or "review" in response.text.lower()

            # Verify pending_uploads.json was created
            pending_path = tmp_path / "pending_uploads.json"
            assert pending_path.exists()

            with open(pending_path) as f:
                pending = json.load(f)

            # Should have exactly one pending upload
            assert len(pending["uploads"]) == 1
            upload = list(pending["uploads"].values())[0]
            assert upload["status"] == "pending"
            assert upload["uploader_email"] == "user@example.com"
            assert upload["source"] == "Test Collection"
            assert upload["file_count"] == 1

    def test_admin_upload_does_not_create_pending_record(self, client, auth_enabled, admin_user, tmp_path):
        """POST /upload by admin does NOT create a pending upload record."""
        with patch("app.main.data_path", tmp_path), \
             patch("app.main.PROCESSING_ENABLED", False):
            # Create staging dir
            (tmp_path / "staging").mkdir(parents=True, exist_ok=True)

            # Upload a file as admin
            file_content = b"fake image data"
            response = client.post(
                "/upload",
                files={"files": ("test_photo.jpg", io.BytesIO(file_content), "image/jpeg")},
                data={"source": "Admin Collection"},
            )
            assert response.status_code == 200

            # Response should mention "Received" (admin staging flow), not "submitted for review"
            assert "received" in response.text.lower() or "pending admin" in response.text.lower()

            # pending_uploads.json should NOT exist (admin flow doesn't create it)
            pending_path = tmp_path / "pending_uploads.json"
            if pending_path.exists():
                with open(pending_path) as f:
                    pending = json.load(f)
                # If it exists, it should have no uploads
                assert len(pending["uploads"]) == 0


class TestAdminPendingPage:
    """Tests for the admin pending uploads review page."""

    def test_pending_page_shows_pending_uploads(self, client, auth_enabled, admin_user, tmp_path):
        """GET /admin/pending shows pending uploads."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads
            _save_pending_uploads({
                "uploads": {
                    "job1": {
                        "job_id": "job1",
                        "uploader_email": "contributor@example.com",
                        "source": "Family Album",
                        "files": ["photo1.jpg"],
                        "file_count": 1,
                        "submitted_at": "2026-02-06T00:00:00+00:00",
                        "status": "pending",
                    }
                }
            })

            response = client.get("/admin/pending")
            assert response.status_code == 200
            assert "contributor@example.com" in response.text
            assert "Family Album" in response.text
            assert "Approve" in response.text
            assert "Reject" in response.text

    def test_pending_page_shows_empty_state(self, client, auth_enabled, admin_user, tmp_path):
        """GET /admin/pending shows empty state when no pending uploads."""
        with patch("app.main.data_path", tmp_path):
            response = client.get("/admin/pending")
            assert response.status_code == 200
            assert "No pending uploads" in response.text


class TestApprovePendingUpload:
    """Tests for approving a pending upload."""

    def test_approve_updates_status(self, client, auth_enabled, admin_user, tmp_path):
        """POST /admin/pending/{id}/approve updates status to approved."""
        with patch("app.main.data_path", tmp_path), \
             patch("app.main.PROCESSING_ENABLED", False):
            from app.main import _save_pending_uploads
            _save_pending_uploads({
                "uploads": {
                    "job1": {
                        "job_id": "job1",
                        "uploader_email": "contributor@example.com",
                        "source": "Family Album",
                        "files": ["photo1.jpg"],
                        "file_count": 1,
                        "submitted_at": "2026-02-06T00:00:00+00:00",
                        "status": "pending",
                    }
                }
            })

            response = client.post("/admin/pending/job1/approve")
            assert response.status_code == 200
            assert "Approved" in response.text

            # Verify status updated in JSON
            with open(tmp_path / "pending_uploads.json") as f:
                data = json.load(f)
            assert data["uploads"]["job1"]["status"] == "approved"
            assert "reviewed_at" in data["uploads"]["job1"]
            assert data["uploads"]["job1"]["reviewed_by"] == "admin@rhodesli.test"

    def test_approve_nonexistent_upload(self, client, auth_enabled, admin_user, tmp_path):
        """POST /admin/pending/{id}/approve for missing upload returns error."""
        with patch("app.main.data_path", tmp_path):
            response = client.post("/admin/pending/nonexistent/approve")
            assert response.status_code == 200  # Returns HTML partial
            assert "not found" in response.text.lower()


class TestRejectPendingUpload:
    """Tests for rejecting a pending upload."""

    def test_reject_updates_status(self, client, auth_enabled, admin_user, tmp_path):
        """POST /admin/pending/{id}/reject updates status to rejected."""
        with patch("app.main.data_path", tmp_path):
            # Create staging directory with a file
            staging_dir = tmp_path / "staging" / "job1"
            staging_dir.mkdir(parents=True)
            (staging_dir / "photo1.jpg").write_bytes(b"fake")

            from app.main import _save_pending_uploads
            _save_pending_uploads({
                "uploads": {
                    "job1": {
                        "job_id": "job1",
                        "uploader_email": "contributor@example.com",
                        "source": "Family Album",
                        "files": ["photo1.jpg"],
                        "file_count": 1,
                        "submitted_at": "2026-02-06T00:00:00+00:00",
                        "status": "pending",
                    }
                }
            })

            response = client.post("/admin/pending/job1/reject")
            assert response.status_code == 200
            assert "Rejected" in response.text

            # Verify status updated in JSON
            with open(tmp_path / "pending_uploads.json") as f:
                data = json.load(f)
            assert data["uploads"]["job1"]["status"] == "rejected"

            # Verify staging files were cleaned up
            assert not staging_dir.exists()

    def test_reject_nonexistent_upload(self, client, auth_enabled, admin_user, tmp_path):
        """POST /admin/pending/{id}/reject for missing upload returns error."""
        with patch("app.main.data_path", tmp_path):
            response = client.post("/admin/pending/nonexistent/reject")
            assert response.status_code == 200  # Returns HTML partial
            assert "not found" in response.text.lower()

    def test_cannot_reject_already_approved(self, client, auth_enabled, admin_user, tmp_path):
        """Cannot reject an already-approved upload."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads
            _save_pending_uploads({
                "uploads": {
                    "job1": {
                        "job_id": "job1",
                        "status": "approved",
                    }
                }
            })

            response = client.post("/admin/pending/job1/reject")
            assert response.status_code == 200
            assert "already" in response.text.lower()
