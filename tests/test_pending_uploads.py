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

    def test_count_pending_uploads_counts_pending_and_staged(self, tmp_path):
        """_count_pending_uploads counts uploads with status='pending' or 'staged'."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads, _count_pending_uploads
            data = {
                "uploads": {
                    "a": {"status": "pending"},
                    "b": {"status": "pending"},
                    "c": {"status": "approved"},
                    "d": {"status": "rejected"},
                    "e": {"status": "staged"},
                }
            }
            _save_pending_uploads(data)
            assert _count_pending_uploads() == 3  # 2 pending + 1 staged

    def test_count_excludes_processed(self, tmp_path):
        """_count_pending_uploads excludes uploads with status='processed'."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads, _count_pending_uploads
            data = {
                "uploads": {
                    "a": {"status": "pending"},
                    "b": {"status": "staged"},
                    "c": {"status": "processed"},
                    "d": {"status": "processed"},
                }
            }
            _save_pending_uploads(data)
            assert _count_pending_uploads() == 2  # only pending + staged

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

    def test_admin_upload_creates_staged_record(self, client, auth_enabled, admin_user, tmp_path):
        """POST /upload by admin on production creates a 'staged' pending record."""
        with patch("app.main.data_path", tmp_path), \
             patch("app.main.PROCESSING_ENABLED", False):
            # Create staging dir
            (tmp_path / "staging").mkdir(parents=True, exist_ok=True)

            # Upload a file as admin
            file_content = b"fake image data"
            response = client.post(
                "/upload",
                files={"files": ("test_photo.jpg", io.BytesIO(file_content), "image/jpeg")},
                data={"source": "personal photos", "collection": "Nace Capeluto Tampa Collection"},
            )
            assert response.status_code == 200

            # Response should show success message with collection/source info
            assert "uploaded successfully" in response.text.lower()
            assert "Nace Capeluto Tampa Collection" in response.text
            assert "Pending Uploads" in response.text  # link to pending page

            # pending_uploads.json should have a staged record
            pending_path = tmp_path / "pending_uploads.json"
            assert pending_path.exists()
            with open(pending_path) as f:
                pending = json.load(f)
            assert len(pending["uploads"]) == 1
            upload = list(pending["uploads"].values())[0]
            assert upload["status"] == "staged"
            assert upload["collection"] == "Nace Capeluto Tampa Collection"
            assert upload["source"] == "personal photos"


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

    def test_pending_page_shows_staged_admin_uploads(self, client, auth_enabled, admin_user, tmp_path):
        """GET /admin/pending shows staged admin uploads with 'Staged' badge."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads
            _save_pending_uploads({
                "uploads": {
                    "job2": {
                        "job_id": "job2",
                        "uploader_email": "admin@rhodesli.test",
                        "source": "personal photos",
                        "collection": "Nace Capeluto Tampa Collection",
                        "files": ["photo1.jpg", "photo2.jpg"],
                        "file_count": 2,
                        "submitted_at": "2026-02-10T00:00:00+00:00",
                        "status": "staged",
                    }
                }
            })

            response = client.get("/admin/pending")
            assert response.status_code == 200
            assert "admin@rhodesli.test" in response.text
            assert "Nace Capeluto Tampa Collection" in response.text
            assert "Staged" in response.text
            # Staged items should NOT have approve/reject buttons
            assert "Approve" not in response.text
            assert "Reject" not in response.text

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


class TestMarkProcessedAdminUI:
    """Tests for POST /admin/pending/{id}/mark-processed (admin UI)."""

    def test_mark_processed_updates_status(self, client, auth_enabled, admin_user, tmp_path):
        """POST /admin/pending/{id}/mark-processed updates staged to processed."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads
            _save_pending_uploads({
                "uploads": {
                    "job1": {
                        "job_id": "job1",
                        "uploader_email": "admin@example.com",
                        "source": "Family Album",
                        "files": ["photo1.jpg"],
                        "file_count": 1,
                        "submitted_at": "2026-02-06T00:00:00+00:00",
                        "status": "staged",
                    }
                }
            })

            response = client.post("/admin/pending/job1/mark-processed")
            assert response.status_code == 200
            assert "Processed" in response.text

            with open(tmp_path / "pending_uploads.json") as f:
                data = json.load(f)
            assert data["uploads"]["job1"]["status"] == "processed"

    def test_mark_processed_nonexistent(self, client, auth_enabled, admin_user, tmp_path):
        """POST /admin/pending/{id}/mark-processed for missing returns error."""
        with patch("app.main.data_path", tmp_path):
            response = client.post("/admin/pending/nonexistent/mark-processed")
            assert response.status_code == 200
            assert "not found" in response.text.lower()

    def test_mark_processed_wrong_status(self, client, auth_enabled, admin_user, tmp_path):
        """Cannot mark-processed a pending (non-staged) upload."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads
            _save_pending_uploads({
                "uploads": {
                    "job1": {
                        "job_id": "job1",
                        "status": "pending",
                    }
                }
            })

            response = client.post("/admin/pending/job1/mark-processed")
            assert response.status_code == 200
            assert "already" in response.text.lower()

    def test_admin_pending_page_has_mark_processed_button(self, client, auth_enabled, admin_user, tmp_path):
        """Admin pending page shows Mark Processed button for staged uploads."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads
            _save_pending_uploads({
                "uploads": {
                    "job1": {
                        "job_id": "job1",
                        "uploader_email": "admin@example.com",
                        "source": "Family Album",
                        "files": ["photo1.jpg"],
                        "file_count": 1,
                        "submitted_at": "2026-02-06T00:00:00+00:00",
                        "status": "staged",
                    }
                }
            })

            response = client.get("/admin/pending")
            assert response.status_code == 200
            assert "Mark Processed" in response.text


class TestMarkProcessedEndpoint:
    """Tests for POST /api/sync/staged/mark-processed."""

    def test_mark_all_staged_as_processed(self, client, tmp_path):
        """Mark all staged jobs as processed."""
        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads
            _save_pending_uploads({
                "uploads": {
                    "job1": {"job_id": "job1", "status": "staged"},
                    "job2": {"job_id": "job2", "status": "staged"},
                    "job3": {"job_id": "job3", "status": "pending"},
                }
            })

            response = client.post(
                "/api/sync/staged/mark-processed",
                headers={"Authorization": "Bearer test-token"},
                json={"all": True},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 2  # only staged jobs, not pending

            # Verify file was updated
            with open(tmp_path / "pending_uploads.json") as f:
                pending = json.load(f)
            assert pending["uploads"]["job1"]["status"] == "processed"
            assert pending["uploads"]["job2"]["status"] == "processed"
            assert pending["uploads"]["job3"]["status"] == "pending"  # unchanged

    def test_mark_specific_jobs_as_processed(self, client, tmp_path):
        """Mark specific job IDs as processed."""
        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads
            _save_pending_uploads({
                "uploads": {
                    "job1": {"job_id": "job1", "status": "staged"},
                    "job2": {"job_id": "job2", "status": "staged"},
                }
            })

            response = client.post(
                "/api/sync/staged/mark-processed",
                headers={"Authorization": "Bearer test-token"},
                json={"job_ids": ["job1"]},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert "job1" in data["marked_processed"]

            with open(tmp_path / "pending_uploads.json") as f:
                pending = json.load(f)
            assert pending["uploads"]["job1"]["status"] == "processed"
            assert pending["uploads"]["job2"]["status"] == "staged"

    def test_mark_processed_requires_token(self, client):
        """Mark-processed endpoint requires valid sync token."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.post(
                "/api/sync/staged/mark-processed",
                json={"all": True},
            )
            assert response.status_code == 401

    def test_processed_jobs_excluded_from_pending_page(self, client, auth_enabled, admin_user, tmp_path):
        """Processed jobs should not appear on the admin pending page."""
        with patch("app.main.data_path", tmp_path):
            from app.main import _save_pending_uploads
            _save_pending_uploads({
                "uploads": {
                    "job1": {
                        "job_id": "job1",
                        "uploader_email": "admin@test.com",
                        "status": "processed",
                        "source": "Processed Job",
                        "files": ["photo1.jpg"],
                        "file_count": 1,
                        "submitted_at": "2026-02-10T00:00:00+00:00",
                    }
                }
            })

            response = client.get("/admin/pending")
            assert response.status_code == 200
            # Processed job should NOT show as a pending/staged item
            assert "Processed Job" not in response.text
            assert "No pending uploads" in response.text


class TestUploadSafetyChecks:
    """Upload endpoints enforce file size limits, file type validation, and batch limits."""

    def test_rejects_disallowed_file_extension(self, client, auth_enabled, admin_user, tmp_path):
        """Upload rejects files with non-image extensions."""
        with patch("app.main.data_path", tmp_path):
            (tmp_path / "staging").mkdir(parents=True, exist_ok=True)
            response = client.post(
                "/upload",
                files={"files": ("malware.exe", io.BytesIO(b"fake"), "application/octet-stream")},
                data={"source": "Test"},
            )
            assert response.status_code == 200
            assert "not allowed" in response.text.lower()

    def test_rejects_oversized_file(self, client, auth_enabled, admin_user, tmp_path):
        """Upload rejects files exceeding 50 MB."""
        with patch("app.main.data_path", tmp_path):
            (tmp_path / "staging").mkdir(parents=True, exist_ok=True)
            # Create a 51 MB file
            big_content = b"x" * (51 * 1024 * 1024)
            response = client.post(
                "/upload",
                files={"files": ("huge.jpg", io.BytesIO(big_content), "image/jpeg")},
                data={"source": "Test"},
            )
            assert response.status_code == 200
            assert "too large" in response.text.lower()

    def test_rejects_too_many_files(self, client, auth_enabled, admin_user, tmp_path):
        """Upload rejects batches with more than 50 files."""
        with patch("app.main.data_path", tmp_path):
            (tmp_path / "staging").mkdir(parents=True, exist_ok=True)
            files = [("files", (f"photo_{i}.jpg", io.BytesIO(b"x"), "image/jpeg"))
                     for i in range(51)]
            response = client.post("/upload", files=files, data={"source": "Test"})
            assert response.status_code == 200
            assert "too many" in response.text.lower()

    def test_accepts_valid_image_upload(self, client, auth_enabled, admin_user, tmp_path):
        """Upload accepts valid image files within limits."""
        with patch("app.main.data_path", tmp_path), \
             patch("app.main.PROCESSING_ENABLED", False):
            (tmp_path / "staging").mkdir(parents=True, exist_ok=True)
            response = client.post(
                "/upload",
                files={"files": ("photo.jpg", io.BytesIO(b"fake image"), "image/jpeg")},
                data={"source": "Test"},
            )
            assert response.status_code == 200
            assert "not allowed" not in response.text.lower()
            assert "too large" not in response.text.lower()

    def test_accepts_zip_upload(self, client, auth_enabled, admin_user, tmp_path):
        """Upload accepts .zip files."""
        with patch("app.main.data_path", tmp_path), \
             patch("app.main.PROCESSING_ENABLED", False):
            (tmp_path / "staging").mkdir(parents=True, exist_ok=True)
            response = client.post(
                "/upload",
                files={"files": ("photos.zip", io.BytesIO(b"PK\x03\x04"), "application/zip")},
                data={"source": "Test"},
            )
            assert response.status_code == 200
            assert "not allowed" not in response.text.lower()

    def test_rejects_batch_exceeding_total_size(self, client, auth_enabled, admin_user, tmp_path):
        """Upload rejects batch when total size exceeds 500 MB."""
        with patch("app.main.data_path", tmp_path):
            (tmp_path / "staging").mkdir(parents=True, exist_ok=True)
            # 11 files x 49 MB each = 539 MB > 500 MB limit
            files = [("files", (f"photo_{i}.jpg", io.BytesIO(b"x" * (49 * 1024 * 1024)), "image/jpeg"))
                     for i in range(11)]
            response = client.post("/upload", files=files, data={"source": "Test"})
            assert response.status_code == 200
            assert "500 mb" in response.text.lower() or "too large" in response.text.lower()
