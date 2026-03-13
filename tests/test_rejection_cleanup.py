"""Tests for upload rejection: metadata preservation and orphaned identity cleanup.

Covers:
- A. Supabase sync_pending_upload includes rejection metadata fields
- B. Orphaned identities (only faces from rejected upload) are marked REJECTED
- B. Identities with faces from OTHER photos are NOT touched
- B. CONFIRMED identities are never touched (Gatekeeper invariant)
- C. rejection_reason form field stored in pending_uploads.json and returned in HTML
- C. rejection_reason shows in the UI response fragment
- Regression: reject handler still returns card id for HTMX outerHTML swap
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_upload(job_id: str, status: str = "pending", files=None) -> dict:
    return {
        "job_id": job_id,
        "uploader_email": f"{job_id}@example.com",
        "uploaded_by": f"{job_id}@example.com",
        "source": "Test Source",
        "collection": "Test Collection",
        "files": files or ["photo1.jpg"],
        "file_count": len(files or ["photo1.jpg"]),
        "submitted_at": "2026-03-01T00:00:00+00:00",
        "status": status,
    }


def _make_identity(
    identity_id: str,
    anchor_ids: list,
    candidate_ids: list = None,
    state: str = "INBOX",
) -> dict:
    return {
        "identity_id": identity_id,
        "name": f"Person {identity_id[:6]}",
        "state": state,
        "anchor_ids": anchor_ids,
        "candidate_ids": candidate_ids or [],
        "negative_ids": [],
        "version_id": 1,
        "created_at": "2026-03-01T00:00:00+00:00",
        "updated_at": "2026-03-01T00:00:00+00:00",
    }


def _make_photo_registry_mock(photo_map: dict):
    """Build a photo_registry mock.

    photo_map: { photo_id: { "path": "...", "faces": set(...) } }
    """
    mock = MagicMock()
    mock._photos = {pid: {} for pid in photo_map}

    def get_path(pid):
        return photo_map[pid]["path"]

    def get_faces(pid):
        return set(photo_map[pid]["faces"])

    mock.get_photo_path.side_effect = get_path
    mock.get_faces_in_photo.side_effect = get_faces
    return mock


# ---------------------------------------------------------------------------
# A. sync_pending_upload — rejection metadata fields
# ---------------------------------------------------------------------------


class TestSyncPendingUploadRejectionFields:
    """sync_pending_upload must include reviewed_at, reviewed_by, rejection_reason."""

    def test_sync_includes_reviewed_at(self):
        upload = {
            "status": "rejected",
            "reviewed_at": "2026-03-13T12:00:00+00:00",
            "reviewed_by": "admin@rhodesli.test",
            "uploader_email": "user@example.com",
            "files": ["photo.jpg"],
        }
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table

        from app.supabase_data import sync_pending_upload

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            sync_pending_upload("job1", upload)

        upsert_call = mock_table.upsert.call_args[0][0]
        assert upsert_call["reviewed_at"] == "2026-03-13T12:00:00+00:00"
        assert upsert_call["reviewed_by"] == "admin@rhodesli.test"

    def test_sync_includes_rejection_reason(self):
        upload = {
            "status": "rejected",
            "reviewed_at": "2026-03-13T12:00:00+00:00",
            "reviewed_by": "admin@rhodesli.test",
            "rejection_reason": "Duplicate",
            "uploader_email": "user@example.com",
            "files": ["photo.jpg"],
        }
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table

        from app.supabase_data import sync_pending_upload

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            sync_pending_upload("job2", upload)

        upsert_call = mock_table.upsert.call_args[0][0]
        assert upsert_call["rejection_reason"] == "Duplicate"

    def test_sync_omits_none_rejection_fields_for_pending(self):
        """Pending uploads must NOT include None rejection columns — avoids schema errors."""
        upload = {
            "status": "pending",
            "uploader_email": "user@example.com",
            "files": ["photo.jpg"],
        }
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table

        from app.supabase_data import sync_pending_upload

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            sync_pending_upload("job3", upload)

        upsert_call = mock_table.upsert.call_args[0][0]
        assert "reviewed_at" not in upsert_call
        assert "reviewed_by" not in upsert_call
        assert "rejection_reason" not in upsert_call


# ---------------------------------------------------------------------------
# B. Orphaned identity cleanup
# ---------------------------------------------------------------------------


class TestCleanupOrphanedIdentities:
    """_cleanup_orphaned_identities_for_upload marks orphan identities REJECTED."""

    def test_orphaned_inbox_identity_marked_rejected(self):
        """An INBOX identity whose only face came from the rejected upload → REJECTED."""
        from core.registry import IdentityRegistry, IdentityState

        # Import here so the module is already loaded before patching
        import app.main as main_mod
        from app.admin_routes import _cleanup_orphaned_identities_for_upload

        iid = str(uuid.uuid4())
        face_id = "inbox_abc123"
        registry = IdentityRegistry()
        registry._identities[iid] = _make_identity(iid, anchor_ids=[face_id])

        photo_registry = _make_photo_registry_mock({"photo1": {"path": "photo1.jpg", "faces": {face_id}}})

        upload = _make_upload("job1", files=["photo1.jpg"])

        with (
            patch.object(main_mod, "load_registry", return_value=registry),
            patch.object(main_mod, "load_photo_registry", return_value=photo_registry),
            patch.object(main_mod, "save_registry"),
        ):
            result = _cleanup_orphaned_identities_for_upload(upload)

        assert iid in result
        assert registry._identities[iid]["state"] == IdentityState.REJECTED.value
        assert registry._identities[iid]["rejection_source"] == "upload_rejected"

    def test_identity_with_other_faces_not_touched(self):
        """Identity with faces from other photos is left untouched."""
        from core.registry import IdentityRegistry

        import app.main as main_mod
        from app.admin_routes import _cleanup_orphaned_identities_for_upload

        iid = str(uuid.uuid4())
        upload_face = "inbox_from_upload"
        other_face = "inbox_from_other_photo"
        registry = IdentityRegistry()
        registry._identities[iid] = _make_identity(iid, anchor_ids=[upload_face, other_face], state="PROPOSED")

        photo_registry = _make_photo_registry_mock({"photo1": {"path": "photo1.jpg", "faces": {upload_face}}})

        upload = _make_upload("job2", files=["photo1.jpg"])

        with (
            patch.object(main_mod, "load_registry", return_value=registry),
            patch.object(main_mod, "load_photo_registry", return_value=photo_registry),
            patch.object(main_mod, "save_registry"),
        ):
            result = _cleanup_orphaned_identities_for_upload(upload)

        assert iid not in result
        assert registry._identities[iid]["state"] == "PROPOSED"

    def test_confirmed_identity_never_touched(self):
        """CONFIRMED identities must not be touched (Gatekeeper invariant)."""
        from core.registry import IdentityRegistry

        import app.main as main_mod
        from app.admin_routes import _cleanup_orphaned_identities_for_upload

        iid = str(uuid.uuid4())
        face_id = "inbox_confirmed_face"
        registry = IdentityRegistry()
        registry._identities[iid] = _make_identity(iid, anchor_ids=[face_id], state="CONFIRMED")

        photo_registry = _make_photo_registry_mock({"photo1": {"path": "photo1.jpg", "faces": {face_id}}})

        upload = _make_upload("job3", files=["photo1.jpg"])

        with (
            patch.object(main_mod, "load_registry", return_value=registry),
            patch.object(main_mod, "load_photo_registry", return_value=photo_registry),
            patch.object(main_mod, "save_registry"),
        ):
            result = _cleanup_orphaned_identities_for_upload(upload)

        assert iid not in result
        assert registry._identities[iid]["state"] == "CONFIRMED"

    def test_no_upload_files_returns_empty(self):
        """Upload with no files listed skips cleanup gracefully."""
        from app.admin_routes import _cleanup_orphaned_identities_for_upload

        result = _cleanup_orphaned_identities_for_upload({"job_id": "x", "files": []})
        assert result == []

    def test_multiple_orphaned_identities_all_marked(self):
        """Multiple orphaned identities from one upload batch are all marked REJECTED."""
        from core.registry import IdentityRegistry, IdentityState

        import app.main as main_mod
        from app.admin_routes import _cleanup_orphaned_identities_for_upload

        iid1, iid2 = str(uuid.uuid4()), str(uuid.uuid4())
        face1, face2 = "inbox_face1", "inbox_face2"
        registry = IdentityRegistry()
        registry._identities[iid1] = _make_identity(iid1, anchor_ids=[face1])
        registry._identities[iid2] = _make_identity(iid2, anchor_ids=[face2])

        photo_registry = _make_photo_registry_mock({"photo1": {"path": "photo1.jpg", "faces": {face1, face2}}})

        upload = _make_upload("job4", files=["photo1.jpg"])

        with (
            patch.object(main_mod, "load_registry", return_value=registry),
            patch.object(main_mod, "load_photo_registry", return_value=photo_registry),
            patch.object(main_mod, "save_registry"),
        ):
            result = _cleanup_orphaned_identities_for_upload(upload)

        assert set(result) == {iid1, iid2}


# ---------------------------------------------------------------------------
# C. Rejection reason — stored in JSON and shown in HTML response
# ---------------------------------------------------------------------------

# Shared registry + photo_registry mocks for integration tests (no real identities)
_EMPTY_REGISTRY = MagicMock()
_EMPTY_REGISTRY._identities = {}
_EMPTY_REGISTRY.list_identities.return_value = []

_EMPTY_PHOTO_REGISTRY = MagicMock()
_EMPTY_PHOTO_REGISTRY._photos = {}
_EMPTY_PHOTO_REGISTRY.get_photo_path.return_value = None
_EMPTY_PHOTO_REGISTRY.get_faces_in_photo.return_value = set()


class TestRejectionReasonField:
    """rejection_reason is stored in pending_uploads.json and echoed in the response."""

    def test_reject_with_reason_stores_in_json(self, client, auth_enabled, admin_user, tmp_path):
        """POST /admin/pending/{job_id}/reject with rejection_reason stores it in JSON."""
        staging_dir = tmp_path / "staging" / "jobR"
        staging_dir.mkdir(parents=True)

        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
            patch("app.main.load_registry", return_value=_EMPTY_REGISTRY),
            patch("app.main.load_photo_registry", return_value=_EMPTY_PHOTO_REGISTRY),
            patch("app.main.save_registry"),
        ):
            from app.main import _save_pending_uploads, _load_pending_uploads

            _save_pending_uploads({"uploads": {"jobR": _make_upload("jobR")}})

            response = client.post(
                "/admin/pending/jobR/reject",
                data={"rejection_reason": "Duplicate"},
            )

            assert response.status_code == 200
            saved = _load_pending_uploads()
            assert saved["uploads"]["jobR"]["rejection_reason"] == "Duplicate"

    def test_reject_with_reason_shown_in_html(self, client, auth_enabled, admin_user, tmp_path):
        """rejection_reason label appears in the HTML response fragment."""
        staging_dir = tmp_path / "staging" / "jobS"
        staging_dir.mkdir(parents=True)

        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
            patch("app.main.load_registry", return_value=_EMPTY_REGISTRY),
            patch("app.main.load_photo_registry", return_value=_EMPTY_PHOTO_REGISTRY),
            patch("app.main.save_registry"),
        ):
            from app.main import _save_pending_uploads

            _save_pending_uploads({"uploads": {"jobS": _make_upload("jobS")}})

            response = client.post(
                "/admin/pending/jobS/reject",
                data={"rejection_reason": "Wrong archive"},
            )

            assert response.status_code == 200
            assert "Wrong archive" in response.text

    def test_reject_without_reason_still_works(self, client, auth_enabled, admin_user, tmp_path):
        """Rejecting without a reason omits rejection_reason key (backward compatible)."""
        staging_dir = tmp_path / "staging" / "jobT"
        staging_dir.mkdir(parents=True)

        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
            patch("app.main.load_registry", return_value=_EMPTY_REGISTRY),
            patch("app.main.load_photo_registry", return_value=_EMPTY_PHOTO_REGISTRY),
            patch("app.main.save_registry"),
        ):
            from app.main import _save_pending_uploads, _load_pending_uploads

            _save_pending_uploads({"uploads": {"jobT": _make_upload("jobT")}})

            response = client.post("/admin/pending/jobT/reject")

            assert response.status_code == 200
            assert "Rejected" in response.text
            saved = _load_pending_uploads()
            assert "rejection_reason" not in saved["uploads"]["jobT"]

    def test_reject_response_always_has_card_id(self, client, auth_enabled, admin_user, tmp_path):
        """Reject response always carries pending-card-{job_id} for HTMX outerHTML swap (regression)."""
        staging_dir = tmp_path / "staging" / "jobU"
        staging_dir.mkdir(parents=True)

        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
            patch("app.main.load_registry", return_value=_EMPTY_REGISTRY),
            patch("app.main.load_photo_registry", return_value=_EMPTY_PHOTO_REGISTRY),
            patch("app.main.save_registry"),
        ):
            from app.main import _save_pending_uploads

            _save_pending_uploads({"uploads": {"jobU": _make_upload("jobU")}})

            response = client.post(
                "/admin/pending/jobU/reject",
                data={"rejection_reason": "Poor quality"},
            )

            assert response.status_code == 200
            assert "pending-card-jobU" in response.text
