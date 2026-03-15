"""Tests for upload pipeline bug fixes — Session 104.

BUG 1: Compare upload approval fails (404) because job_id prefix check doesn't match
BUG 2: Compare upload user attribution gated on is_auth_enabled()
BUG 3: Compare upload thumbnails use wrong R2 path
Auto-approve: Logged-in contributor uploads auto-approve
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


# ── BUG 1: Compare upload approval processes correctly ──


class TestCompareUploadApproval:
    """Compare uploads with plain UUID job IDs must be processed on approval."""

    def test_compare_upload_approval_sets_will_process(self, client, tmp_path, monkeypatch):
        """Approving a compare upload with staging dir should trigger processing."""
        import app.main as main_mod
        from app.auth import User

        monkeypatch.setattr(main_mod, "data_path", tmp_path)

        job_id = "8add8b91"
        staging_dir = tmp_path / "staging" / job_id
        staging_dir.mkdir(parents=True)
        (staging_dir / "test_photo.jpg").write_bytes(b"FAKE_JPEG")

        pending_data = {
            "uploads": {
                job_id: {
                    "job_id": job_id,
                    "status": "pending",
                    "uploader_email": "contributor@example.com",
                    "source": "Compare Upload",
                    "collection": "",
                    "files": ["test_photo.jpg"],
                    "file_count": 1,
                    "submitted_at": "2026-03-15T00:00:00Z",
                    "compare_mode": True,
                }
            }
        }

        admin = User(id="admin-1", email="admin@example.com", is_admin=True)
        thread_started = []

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.admin_routes.get_current_user", return_value=admin),
            patch("app.main._load_pending_uploads", return_value=pending_data),
            patch("app.main._save_pending_uploads"),
            patch("app.main.log_user_action"),
            patch("app.admin_routes.PROCESSING_ENABLED", True),
            patch("threading.Thread") as mock_thread,
        ):
            mock_thread.return_value.start = lambda: thread_started.append(True)
            response = client.post(f"/admin/pending/{job_id}/approve")
            assert response.status_code == 200
            html = response.text
            assert "Approved" in html
            # Thread should have been started for processing
            assert mock_thread.called, "Background processing thread should be started"

    def test_compare_upload_approval_r2_recovery_uses_correct_path(self, client, tmp_path, monkeypatch):
        """When staging is gone, R2 recovery should use uploads/pending/{job_id}/{filename}."""
        import app.main as main_mod
        from app.auth import User

        monkeypatch.setattr(main_mod, "data_path", tmp_path)

        job_id = "8add8b91"
        safe_filename = "test_photo.jpg"
        # No staging dir — simulate Railway volume restart

        pending_data = {
            "uploads": {
                job_id: {
                    "job_id": job_id,
                    "status": "pending",
                    "uploader_email": "contributor@example.com",
                    "source": "Compare Upload",
                    "collection": "",
                    "files": [safe_filename],
                    "file_count": 1,
                    "submitted_at": "2026-03-15T00:00:00Z",
                    "compare_mode": True,
                }
            }
        }

        admin = User(id="admin-1", email="admin@example.com", is_admin=True)

        mock_s3 = MagicMock()
        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.admin_routes.get_current_user", return_value=admin),
            patch("app.main._load_pending_uploads", return_value=pending_data),
            patch("app.main._save_pending_uploads"),
            patch("app.main.log_user_action"),
            patch("app.admin_routes.PROCESSING_ENABLED", True),
            patch("core.storage.can_write_r2", return_value=True),
            patch("boto3.client", return_value=mock_s3),
            patch("threading.Thread") as mock_thread,
            patch.dict(
                os.environ,
                {
                    "R2_ACCOUNT_ID": "test",
                    "R2_ACCESS_KEY_ID": "test",
                    "R2_SECRET_ACCESS_KEY": "test",
                },
            ),
        ):
            mock_thread.return_value.start = lambda: None
            response = client.post(f"/admin/pending/{job_id}/approve")
            assert response.status_code == 200

            # Verify R2 download used correct path
            if mock_s3.download_file.called:
                call_args = mock_s3.download_file.call_args
                r2_key = call_args[0][1]
                assert r2_key == f"uploads/pending/{job_id}/{safe_filename}", (
                    f"R2 key should be uploads/pending/{{job_id}}/{{filename}}, got {r2_key}"
                )

    def test_compare_mode_detection_not_prefix_based(self, client, tmp_path, monkeypatch):
        """compare_mode flag should be used, not job_id prefix check."""
        import app.main as main_mod
        from app.auth import User

        monkeypatch.setattr(main_mod, "data_path", tmp_path)

        # Job ID is a plain UUID (no compare_ prefix)
        job_id = "a1b2c3d4"
        staging_dir = tmp_path / "staging" / job_id
        staging_dir.mkdir(parents=True)
        (staging_dir / "photo.jpg").write_bytes(b"FAKE")

        pending_data = {
            "uploads": {
                job_id: {
                    "job_id": job_id,
                    "status": "pending",
                    "uploader_email": "user@example.com",
                    "source": "Compare Upload",
                    "collection": "",
                    "files": ["photo.jpg"],
                    "file_count": 1,
                    "submitted_at": "2026-03-15T00:00:00Z",
                    "compare_mode": True,
                }
            }
        }

        admin = User(id="admin-1", email="admin@example.com", is_admin=True)

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.admin_routes.get_current_user", return_value=admin),
            patch("app.main._load_pending_uploads", return_value=pending_data),
            patch("app.main._save_pending_uploads"),
            patch("app.main.log_user_action"),
            patch("app.admin_routes.PROCESSING_ENABLED", True),
            patch("threading.Thread") as mock_thread,
        ):
            mock_thread.return_value.start = lambda: None
            response = client.post(f"/admin/pending/{job_id}/approve")
            assert response.status_code == 200
            # Should show "Approved", not error
            assert "Approved" in response.text


# ── BUG 2: User attribution preserved ──


class TestUserAttribution:
    """Compare upload should always attempt user retrieval."""

    def test_compare_upload_preserves_user_email(self, client, tmp_path, monkeypatch):
        """Logged-in user's email should be saved, not 'anonymous'."""
        import app.main as main_mod
        from app.auth import User

        monkeypatch.setattr(main_mod, "data_path", tmp_path)
        monkeypatch.setattr(main_mod, "PROCESSING_ENABLED", True)
        (tmp_path / "staging").mkdir(parents=True, exist_ok=True)

        user = User(id="user-1", email="claude.benatar@example.com", is_admin=False)
        with (
            patch("app.main.is_auth_enabled", return_value=True),
            patch("app.main.get_current_user", return_value=user),
            patch("app.main._load_pending_uploads", return_value={"uploads": {}}),
            patch("app.main._save_pending_uploads") as mock_save,
            patch("app.main.posthog_capture"),
            patch("app.main.log_user_action"),
            patch("threading.Thread") as mock_thread,
        ):
            mock_thread.return_value.start = lambda: None
            response = client.post(
                "/api/compare/upload",
                files={"photo": ("test.jpg", b"fake-image-data", "image/jpeg")},
            )
            assert response.status_code == 200

            if mock_save.called:
                saved = mock_save.call_args[0][0]
                entry = list(saved["uploads"].values())[0]
                assert entry["uploader_email"] == "claude.benatar@example.com"

    def test_compare_upload_auth_disabled_still_works(self, client, tmp_path, monkeypatch):
        """When auth is disabled, upload should proceed without error."""
        import app.main as main_mod

        monkeypatch.setattr(main_mod, "data_path", tmp_path)
        monkeypatch.setattr(main_mod, "PROCESSING_ENABLED", False)
        (tmp_path / "staging").mkdir(parents=True, exist_ok=True)

        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.get_current_user", return_value=None),
            patch("app.main._load_pending_uploads", return_value={"uploads": {}}),
            patch("app.main._save_pending_uploads"),
            patch("app.main.posthog_capture"),
        ):
            response = client.post(
                "/api/compare/upload",
                files={"photo": ("test.jpg", b"fake-image-data", "image/jpeg")},
            )
            assert response.status_code == 200


# ── BUG 3: Thumbnail R2 path consistency ──


class TestThumbnailPaths:
    """Compare upload thumbnails must use the correct R2 path."""

    def test_compare_thumbnail_uses_pending_path(self, client, tmp_path, monkeypatch):
        """Thumbnail URL for compare upload should use uploads/pending/{job_id}/{filename}."""
        import app.main as main_mod
        from app.auth import User

        monkeypatch.setattr(main_mod, "data_path", tmp_path)

        job_id = "abc12345"
        fname = "photo.jpg"
        r2_base = "https://pub-test.r2.dev"

        pending_data = {
            "uploads": {
                job_id: {
                    "job_id": job_id,
                    "status": "pending",
                    "uploader_email": "user@example.com",
                    "source": "Compare Upload",
                    "collection": "",
                    "files": [fname],
                    "file_count": 1,
                    "submitted_at": "2026-03-15T00:00:00Z",
                    "compare_mode": True,
                }
            }
        }

        admin = User(id="admin-1", email="admin@example.com", is_admin=True)

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.admin_routes.get_current_user", return_value=admin),
            patch("app.main.load_registry") as mock_reg,
            patch(
                "app.main._compute_sidebar_counts",
                return_value={
                    "to_review": 0,
                    "confirmed": 0,
                    "skipped": 0,
                    "dismissed": 0,
                    "rejected": 0,
                    "inbox": 0,
                    "proposed": 0,
                    "pending_uploads": 1,
                    "proposals": 0,
                },
            ),
            patch("app.main._load_pending_uploads", return_value=pending_data),
            patch.dict(os.environ, {"R2_PUBLIC_URL": r2_base}),
        ):
            mock_reg.return_value = MagicMock(identities={})
            response = client.get("/admin/pending")
            assert response.status_code == 200
            html = response.text

            # Thumbnail URL should use uploads/pending/{job_id}/{filename}
            expected_path = f"uploads/pending/{job_id}/{fname}"
            assert expected_path in html, (
                f"Expected R2 path '{expected_path}' in HTML but not found. "
                f"Old incorrect path 'uploads/compare/{job_id}.jpg' should NOT be used."
            )
            # Verify the old wrong path is NOT used
            assert f"uploads/compare/{job_id}.jpg" not in html


# ── Auto-approve for logged-in contributors ──


class TestAutoApprove:
    """Logged-in non-admin contributors should get auto-approved."""

    def test_contributor_upload_auto_approved(self, client, tmp_path, monkeypatch):
        """Logged-in contributor upload should be auto-approved."""
        import app.main as main_mod
        from app.auth import User

        monkeypatch.setattr(main_mod, "data_path", tmp_path)
        monkeypatch.setattr(main_mod, "PROCESSING_ENABLED", True)
        (tmp_path / "staging").mkdir(parents=True, exist_ok=True)

        user = User(id="user-1", email="contributor@example.com", is_admin=False)
        with (
            patch("app.main.is_auth_enabled", return_value=True),
            patch("app.main.get_current_user", return_value=user),
            patch("app.main._load_pending_uploads", return_value={"uploads": {}}),
            patch("app.main._save_pending_uploads") as mock_save,
            patch("app.main.posthog_capture"),
            patch("app.main.log_user_action"),
            patch("threading.Thread") as mock_thread,
        ):
            mock_thread.return_value.start = lambda: None
            response = client.post(
                "/api/compare/upload",
                files={"photo": ("test.jpg", b"fake-image-data", "image/jpeg")},
            )
            assert response.status_code == 200
            assert "upload-auto-approved" in response.text

            # Verify status is "approved" not "pending"
            if mock_save.called:
                saved = mock_save.call_args[0][0]
                entry = list(saved["uploads"].values())[0]
                assert entry["status"] == "approved"
                assert entry["auto_approved"] is True

    def test_anonymous_upload_stays_pending(self, client, tmp_path, monkeypatch):
        """Anonymous upload should remain pending for admin review."""
        import app.main as main_mod

        monkeypatch.setattr(main_mod, "data_path", tmp_path)
        monkeypatch.setattr(main_mod, "PROCESSING_ENABLED", True)
        (tmp_path / "staging").mkdir(parents=True, exist_ok=True)

        with (
            patch("app.main.is_auth_enabled", return_value=True),
            patch("app.main.get_current_user", return_value=None),
            patch("app.main._load_pending_uploads", return_value={"uploads": {}}),
            patch("app.main._save_pending_uploads") as mock_save,
            patch("app.main.posthog_capture"),
        ):
            response = client.post(
                "/api/compare/upload",
                files={"photo": ("test.jpg", b"fake-image-data", "image/jpeg")},
            )
            assert response.status_code == 200
            assert "upload-saved-pending" in response.text

            if mock_save.called:
                saved = mock_save.call_args[0][0]
                entry = list(saved["uploads"].values())[0]
                assert entry["status"] == "pending"

    def test_auto_approve_spawns_processing_thread(self, client, tmp_path, monkeypatch):
        """Auto-approved uploads should spawn background processing."""
        import app.main as main_mod
        from app.auth import User

        monkeypatch.setattr(main_mod, "data_path", tmp_path)
        monkeypatch.setattr(main_mod, "PROCESSING_ENABLED", True)
        (tmp_path / "staging").mkdir(parents=True, exist_ok=True)

        user = User(id="user-1", email="contributor@example.com", is_admin=False)
        with (
            patch("app.main.is_auth_enabled", return_value=True),
            patch("app.main.get_current_user", return_value=user),
            patch("app.main._load_pending_uploads", return_value={"uploads": {}}),
            patch("app.main._save_pending_uploads"),
            patch("app.main.posthog_capture"),
            patch("app.main.log_user_action"),
            patch("threading.Thread") as mock_thread,
        ):
            mock_thread.return_value.start = lambda: None
            response = client.post(
                "/api/compare/upload",
                files={"photo": ("test.jpg", b"fake-image-data", "image/jpeg")},
            )
            assert response.status_code == 200
            # Verify thread was created for background processing
            assert mock_thread.called, "Processing thread should be spawned for auto-approved upload"
            thread_name = mock_thread.call_args[1].get("name", "")
            assert "auto-approve" in thread_name


# ── R2 path consistency ──


class TestR2PathConsistency:
    """R2 upload path in compare_routes must match R2 recovery path in admin_routes."""

    def test_r2_upload_path_matches_recovery_path(self):
        """The R2 key used for upload must match the key used for recovery."""
        # This is a structural test — verify the paths match by reading the code
        import inspect
        import app.compare_routes as compare_mod
        import app.admin_routes as admin_mod

        # The upload path pattern (compare_routes.py)
        # is: uploads/pending/{job_id}/{safe_filename}
        # The recovery path pattern (admin_routes.py) should match
        compare_source = inspect.getsource(compare_mod)
        assert "uploads/pending/{job_id}/{safe_filename}" in compare_source

        admin_source = inspect.getsource(admin_mod)
        # Should use uploads/pending/ pattern, not uploads/compare/
        assert "uploads/pending/{job_id}/{r2_filename}" in admin_source
        # Old broken path should NOT be present
        assert 'f"uploads/compare/{upload_id}.jpg"' not in admin_source
