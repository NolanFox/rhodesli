"""Tests for upload pipeline fixes — Issues 1-5.

Issue 1: Compare uploads record logged-in user's email (not "anonymous")
Issue 2: Pending page thumbnails are clickable (wrapped in <a> tag)
Issue 3: Rejection preserves metadata via Supabase sync before file deletion
Issue 4: sync_pending_upload handles missing 'data' column gracefully
Issue 5: Rejecting a duplicate pending entry doesn't affect already-processed photos
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Issue 1: Compare uploads record user email ──


def test_compare_upload_records_user_email(client, tmp_path, monkeypatch):
    """Non-admin compare upload should record user email, not 'anonymous'."""
    import app.main as main_mod
    from app.auth import User

    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    monkeypatch.setattr(main_mod, "PROCESSING_ENABLED", True)
    (tmp_path / "staging").mkdir(parents=True, exist_ok=True)

    user = User(id="test-user-1", email="claude.benatar@example.com", is_admin=False)
    with (
        patch("app.main.is_auth_enabled", return_value=True),
        patch("app.main.get_current_user", return_value=user),
        patch("app.main._load_pending_uploads", return_value={"uploads": {}}),
        patch("app.main._save_pending_uploads") as mock_save,
        patch("app.main.posthog_capture"),
    ):
        response = client.post(
            "/api/compare/upload",
            files={"photo": ("test.jpg", b"fake-image-data", "image/jpeg")},
        )
        assert response.status_code == 200

        # Verify pending upload was saved with user's email
        if mock_save.called:
            saved = mock_save.call_args[0][0]
            uploads = saved["uploads"]
            assert len(uploads) == 1
            entry = list(uploads.values())[0]
            assert entry["uploader_email"] == "claude.benatar@example.com"
            assert entry["uploader_email"] != "anonymous"


def test_compare_contribute_records_user_email(client, monkeypatch):
    """The /api/compare/contribute route should include uploader_email key."""
    import app.main as main_mod
    from app.auth import User

    user = User(id="test-user-1", email="claude.benatar@example.com", is_admin=False)

    mock_meta = {"original_filename": "test.jpg", "faces_detected": 2}
    with (
        patch("app.main.is_auth_enabled", return_value=True),
        patch("app.main.get_current_user", return_value=user),
        patch("app.main._check_login", return_value=None),
        patch("app.main._load_pending_uploads", return_value={"uploads": {}}),
        patch("app.main._save_pending_uploads") as mock_save,
        patch("core.storage.can_write_r2", return_value=False),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value=json.dumps(mock_meta)),
    ):
        response = client.post("/api/compare/contribute?upload_id=test123")
        assert response.status_code == 200

        if mock_save.called:
            saved = mock_save.call_args[0][0]
            entry = list(saved["uploads"].values())[0]
            assert entry.get("uploader_email") == "claude.benatar@example.com"


# ── Issue 2: Pending page thumbnails clickable ──


def test_pending_thumbnails_wrapped_in_link(client, tmp_path, monkeypatch):
    """Pending upload thumbnails should be wrapped in <a> tags for click-to-open."""
    import app.main as main_mod

    monkeypatch.setattr(main_mod, "data_path", tmp_path)

    pending_data = {
        "uploads": {
            "abc123": {
                "job_id": "abc123",
                "status": "pending",
                "uploader_email": "user@example.com",
                "source": "Compare Upload",
                "collection": "",
                "files": ["photo.jpg"],
                "file_count": 1,
                "submitted_at": "2026-03-13T00:00:00Z",
            }
        }
    }

    with (
        patch("app.main._check_admin", return_value=None),
        patch("app.admin_routes.get_current_user", return_value=None),
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
                "discoveries": 0,
                "ready_to_confirm": 0,
                "rediscovered": 0,
                "unmatched": 0,
            },
        ),
        patch("app.main._load_pending_uploads", return_value=pending_data),
    ):
        mock_reg.return_value = MagicMock()
        response = client.get("/admin/pending")
        assert response.status_code == 200
        html = response.text
        # Verify thumbnail is wrapped in an anchor tag with target="_blank"
        assert 'target="_blank"' in html
        assert "staging-preview" in html
        assert 'data-testid="pending-thumb-abc123"' in html


# ── Issue 3: Rejection syncs to Supabase before file deletion ──


def test_rejection_syncs_to_supabase(client, tmp_path, monkeypatch):
    """Rejecting an upload should sync to Supabase BEFORE deleting staging files."""
    import app.main as main_mod

    monkeypatch.setattr(main_mod, "data_path", tmp_path)

    # Create staging directory to verify deletion happens
    staging_dir = tmp_path / "staging" / "job123"
    staging_dir.mkdir(parents=True)
    (staging_dir / "photo.jpg").write_bytes(b"fake")

    pending_data = {
        "uploads": {
            "job123": {
                "job_id": "job123",
                "status": "pending",
                "uploader_email": "user@example.com",
                "source": "Compare Upload",
                "files": ["photo.jpg"],
                "file_count": 1,
                "submitted_at": "2026-03-13T00:00:00Z",
            }
        }
    }

    call_order = []

    def mock_sync(job_id, data):
        # Record that sync was called and staging dir still exists
        call_order.append(("sync", staging_dir.exists()))

    original_rmtree = None

    with (
        patch("app.main._check_admin", return_value=None),
        patch("app.admin_routes.get_current_user", return_value=None),
        patch("app.main._load_pending_uploads", return_value=pending_data),
        patch("app.main._save_pending_uploads"),
        patch("app.main.log_user_action"),
        patch("app.supabase_data.sync_pending_upload", mock_sync),
    ):
        response = client.post("/admin/pending/job123/reject")
        assert response.status_code == 200
        assert "Rejected" in response.text

    # Verify sync was called while staging dir still existed
    assert len(call_order) == 1
    assert call_order[0] == ("sync", True), "Supabase sync must happen BEFORE staging file deletion"


def test_rejection_preserves_metadata_in_json(client, tmp_path, monkeypatch):
    """Rejecting an upload keeps the JSON record with rejected status."""
    import app.main as main_mod

    monkeypatch.setattr(main_mod, "data_path", tmp_path)

    pending_data = {
        "uploads": {
            "job456": {
                "job_id": "job456",
                "status": "pending",
                "uploader_email": "user@example.com",
                "source": "Compare Upload",
                "files": ["photo.jpg"],
                "file_count": 1,
                "submitted_at": "2026-03-13T00:00:00Z",
            }
        }
    }

    saved_data = {}

    def capture_save(data):
        saved_data.update(data)

    with (
        patch("app.main._check_admin", return_value=None),
        patch("app.admin_routes.get_current_user", return_value=None),
        patch("app.main._load_pending_uploads", return_value=pending_data),
        patch("app.main._save_pending_uploads", side_effect=capture_save),
        patch("app.main.log_user_action"),
        patch("app.supabase_data.sync_pending_upload"),
    ):
        response = client.post("/admin/pending/job456/reject")
        assert response.status_code == 200

    # Verify metadata was preserved with rejected status
    assert saved_data["uploads"]["job456"]["status"] == "rejected"
    assert "reviewed_at" in saved_data["uploads"]["job456"]
    assert saved_data["uploads"]["job456"]["uploader_email"] == "user@example.com"


# ── Issue 4: sync_pending_upload handles missing 'data' column ──


def test_sync_pending_upload_retries_without_data_column():
    """sync_pending_upload should retry without 'data' if column doesn't exist."""
    from app.supabase_data import sync_pending_upload

    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    # First call raises schema error about 'data' column
    import httpx

    schema_error = httpx.HTTPStatusError(
        "Could not find the 'data' column of 'pending_uploads' in the schema cache",
        request=MagicMock(),
        response=MagicMock(status_code=400),
    )
    # First upsert fails, second succeeds
    mock_upsert = MagicMock()
    mock_upsert.execute.side_effect = [schema_error, MagicMock()]
    mock_table.upsert.return_value = mock_upsert

    with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
        sync_pending_upload(
            "job789",
            {
                "status": "pending",
                "uploader_email": "user@example.com",
                "files": ["photo.jpg"],
            },
        )

    # Should have been called twice: once with data, once without
    assert mock_table.upsert.call_count == 2
    first_row = mock_table.upsert.call_args_list[0][0][0]
    second_row = mock_table.upsert.call_args_list[1][0][0]
    assert "data" in first_row
    assert "data" not in second_row


def test_sync_pending_upload_derives_uploader_email():
    """sync_pending_upload should derive uploader from multiple possible keys."""
    from app.supabase_data import sync_pending_upload

    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.upsert.return_value.execute.return_value = MagicMock()

    with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
        # Test uploader_email key
        sync_pending_upload("job1", {"uploader_email": "a@b.com", "status": "pending"})
        row = mock_table.upsert.call_args[0][0]
        assert row["user_id"] == "a@b.com"

        # Test submitted_by fallback
        sync_pending_upload("job2", {"submitted_by": "c@d.com", "status": "pending"})
        row = mock_table.upsert.call_args[0][0]
        assert row["user_id"] == "c@d.com"


def test_sync_pending_upload_derives_filename_from_files_list():
    """sync_pending_upload should use files[0] as filename fallback."""
    from app.supabase_data import sync_pending_upload

    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.upsert.return_value.execute.return_value = MagicMock()

    with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
        sync_pending_upload("job3", {"files": ["photo.jpg"], "status": "pending"})
        row = mock_table.upsert.call_args[0][0]
        assert row["filename"] == "photo.jpg"


# ── Issue 5: Duplicate rejection safety ──


def test_reject_duplicate_does_not_affect_processed_upload(client, tmp_path, monkeypatch):
    """Rejecting a duplicate pending entry must not affect already-processed photos.

    Verifies that rejection only touches data/staging/{job_id}/, not data/uploads/
    or identity/photo registries.
    """
    import app.main as main_mod

    monkeypatch.setattr(main_mod, "data_path", tmp_path)

    # Simulate already-processed upload in uploads dir
    processed_dir = tmp_path / "uploads"
    processed_dir.mkdir(parents=True)
    processed_file = processed_dir / "unknown_1.jpg"
    processed_file.write_bytes(b"processed photo data")

    # Duplicate pending entry
    dup_staging = tmp_path / "staging" / "efea638c"
    dup_staging.mkdir(parents=True)
    (dup_staging / "unknown_1.jpg").write_bytes(b"duplicate staging data")

    pending_data = {
        "uploads": {
            "efea638c": {
                "job_id": "efea638c",
                "status": "pending",
                "uploader_email": "user@example.com",
                "source": "Compare Upload",
                "files": ["unknown_1.jpg"],
                "file_count": 1,
                "submitted_at": "2026-03-13T00:00:00Z",
            }
        }
    }

    with (
        patch("app.main._check_admin", return_value=None),
        patch("app.admin_routes.get_current_user", return_value=None),
        patch("app.main._load_pending_uploads", return_value=pending_data),
        patch("app.main._save_pending_uploads"),
        patch("app.main.log_user_action"),
        patch("app.supabase_data.sync_pending_upload"),
    ):
        response = client.post("/admin/pending/efea638c/reject")
        assert response.status_code == 200

    # Staging dir should be deleted
    assert not dup_staging.exists()
    # Already-processed file must be untouched
    assert processed_file.exists()
    assert processed_file.read_bytes() == b"processed photo data"
