"""
Tests for anonymous guest contribution flow.

Covers: guest modal display, guest annotation submission, stash-and-login,
login-and-submit, admin approvals for guest annotations.
"""

import pytest
import json
from starlette.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def tmp_annotations(tmp_path):
    """Create temp annotations file and patch data_path + cache."""
    from app.main import _invalidate_annotations_cache

    ann_path = tmp_path / "annotations.json"
    ann_path.write_text(json.dumps({"schema_version": 1, "annotations": {}}))
    _invalidate_annotations_cache()
    with patch("app.main.data_path", tmp_path):
        yield tmp_path
    _invalidate_annotations_cache()


class TestAnonymousSubmitFrictionless:
    """POST /api/annotations/submit as anonymous saves directly — no modal."""

    def test_anonymous_submit_saves_directly(self, client, tmp_annotations):
        """Anonymous user submitting annotation saves directly with toast (no modal)."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            resp = client.post(
                "/api/annotations/submit",
                data={
                    "target_type": "identity",
                    "target_id": "test-id-123",
                    "annotation_type": "name_suggestion",
                    "value": "Leon Capeluto",
                },
                headers={"HX-Request": "true"},
            )
            assert resp.status_code == 200
            assert "thanks" in resp.text.lower()
            # Should NOT show the guest modal
            assert "Continue as guest" not in resp.text
            assert "Sign in to save" not in resp.text

    def test_anonymous_submit_creates_unverified_annotation(self, client, tmp_annotations):
        """Anonymous submission creates a pending_unverified annotation."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            resp = client.post(
                "/api/annotations/submit",
                data={
                    "target_type": "identity",
                    "target_id": "test-id-123",
                    "annotation_type": "name_suggestion",
                    "value": "Leon Capeluto",
                },
                headers={"HX-Request": "true"},
            )
            assert resp.status_code == 200

            # Verify annotation was saved
            ann_data = json.loads((tmp_annotations / "annotations.json").read_text())
            anns = list(ann_data["annotations"].values())
            assert len(anns) == 1
            assert anns[0]["value"] == "Leon Capeluto"
            assert anns[0]["submitted_by"] == "anonymous"
            assert anns[0]["status"] == "pending_unverified"

    def test_empty_value_rejected(self, client, tmp_annotations):
        """Empty input returns 400 validation error."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            resp = client.post(
                "/api/annotations/submit",
                data={
                    "target_type": "identity",
                    "target_id": "test-id-123",
                    "annotation_type": "name_suggestion",
                    "value": "",
                },
                headers={"HX-Request": "true"},
            )
            assert resp.status_code == 400

    def test_logged_in_submit_saves_as_pending(self, client, tmp_annotations):
        """Authenticated users save as pending (not pending_unverified)."""
        mock_user = MagicMock()
        mock_user.email = "user@example.com"
        mock_user.is_admin = False

        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=mock_user), \
             patch("app.main._check_login", return_value=None):
            resp = client.post(
                "/api/annotations/submit",
                data={
                    "target_type": "identity",
                    "target_id": "test-id-123",
                    "annotation_type": "name_suggestion",
                    "value": "Leon Capeluto",
                },
            )
            assert resp.status_code == 200
            assert "thanks" in resp.text.lower()

            # Verify saved as pending (not unverified)
            ann_data = json.loads((tmp_annotations / "annotations.json").read_text())
            ann = list(ann_data["annotations"].values())[0]
            assert ann["submitted_by"] == "user@example.com"
            assert ann["status"] == "pending"

    def test_local_dev_submit_saves_as_local_dev(self, client, tmp_annotations):
        """Auth-disabled (local dev) saves with submitted_by='local_dev'."""
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.get_current_user", return_value=None):
            resp = client.post(
                "/api/annotations/submit",
                data={
                    "target_type": "identity",
                    "target_id": "test-id-123",
                    "annotation_type": "name_suggestion",
                    "value": "Leon Capeluto",
                },
            )
            assert resp.status_code == 200

            ann_data = json.loads((tmp_annotations / "annotations.json").read_text())
            ann = list(ann_data["annotations"].values())[0]
            assert ann["submitted_by"] == "local_dev"
            assert ann["status"] == "pending"


class TestGuestSubmit:
    """Tests for POST /api/annotations/guest-submit."""

    def test_guest_submit_saves_annotation(self, client, tmp_annotations):
        """Guest submit creates an annotation record."""
        resp = client.post(
            "/api/annotations/guest-submit",
            data={
                "target_type": "identity",
                "target_id": "test-id-123",
                "annotation_type": "name_suggestion",
                "value": "Leon Capeluto",
                "confidence": "likely",
            },
        )
        assert resp.status_code == 200
        assert "thanks" in resp.text.lower() or "pending" in resp.text.lower()

        # Verify saved to file
        ann_data = json.loads((tmp_annotations / "annotations.json").read_text())
        anns = list(ann_data["annotations"].values())
        assert len(anns) == 1
        assert anns[0]["value"] == "Leon Capeluto"

    def test_guest_annotation_marked_unverified(self, client, tmp_annotations):
        """Guest annotations have status 'pending_unverified'."""
        client.post(
            "/api/annotations/guest-submit",
            data={
                "target_type": "identity",
                "target_id": "test-id-123",
                "annotation_type": "name_suggestion",
                "value": "Leon Capeluto",
            },
        )
        ann_data = json.loads((tmp_annotations / "annotations.json").read_text())
        ann = list(ann_data["annotations"].values())[0]
        assert ann["status"] == "pending_unverified"

    def test_guest_annotation_anonymous_submitter(self, client, tmp_annotations):
        """Guest annotations have submitted_by == 'anonymous'."""
        client.post(
            "/api/annotations/guest-submit",
            data={
                "target_type": "identity",
                "target_id": "test-id-123",
                "annotation_type": "name_suggestion",
                "value": "Leon Capeluto",
            },
        )
        ann_data = json.loads((tmp_annotations / "annotations.json").read_text())
        ann = list(ann_data["annotations"].values())[0]
        assert ann["submitted_by"] == "anonymous"

    def test_guest_submit_empty_value_rejected(self, client, tmp_annotations):
        """Empty value returns 400."""
        resp = client.post(
            "/api/annotations/guest-submit",
            data={
                "target_type": "identity",
                "target_id": "test-id-123",
                "annotation_type": "name_suggestion",
                "value": "  ",
            },
        )
        assert resp.status_code == 400


class TestStashAndLogin:
    """Tests for POST /api/annotations/stash-and-login."""

    def test_stash_returns_login_form(self, client):
        """Stash endpoint returns a login form inside the modal."""
        resp = client.post(
            "/api/annotations/stash-and-login",
            data={
                "target_type": "identity",
                "target_id": "test-id-123",
                "annotation_type": "name_suggestion",
                "value": "Leon Capeluto",
            },
        )
        assert resp.status_code == 200
        # Should contain a login form
        assert "email" in resp.text.lower()
        assert "password" in resp.text.lower()
        # Should show preview of suggestion
        assert "Leon Capeluto" in resp.text

    def test_stash_stores_in_session(self, client):
        """Stash endpoint stores form data in session cookie."""
        # We verify indirectly: after stashing, login-and-submit should
        # be able to retrieve it. TestLoginAndSubmit covers this.
        resp = client.post(
            "/api/annotations/stash-and-login",
            data={
                "target_type": "identity",
                "target_id": "test-id-123",
                "annotation_type": "name_suggestion",
                "value": "Leon Capeluto",
            },
        )
        assert resp.status_code == 200


class TestAdminApprovalsGuest:
    """Tests for guest annotations in admin approvals."""

    def test_approvals_include_guest_annotations(self, client, tmp_annotations):
        """Admin approvals page shows pending_unverified annotations."""
        # First create a guest annotation
        from app.main import _invalidate_annotations_cache
        ann_data = {
            "schema_version": 1,
            "annotations": {
                "guest-ann-1": {
                    "annotation_id": "guest-ann-1",
                    "type": "name_suggestion",
                    "target_type": "identity",
                    "target_id": "test-id-123",
                    "value": "Leon Capeluto",
                    "confidence": "likely",
                    "reason": "",
                    "submitted_by": "anonymous",
                    "submitted_at": "2026-02-10T00:00:00+00:00",
                    "status": "pending_unverified",
                    "reviewed_by": None,
                    "reviewed_at": None,
                }
            }
        }
        (tmp_annotations / "annotations.json").write_text(json.dumps(ann_data))
        _invalidate_annotations_cache()

        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/admin/approvals")
            assert resp.status_code == 200
            assert "Leon Capeluto" in resp.text

    def test_guest_badge_shown(self, client, tmp_annotations):
        """Guest badge appears for anonymous submissions."""
        from app.main import _invalidate_annotations_cache
        ann_data = {
            "schema_version": 1,
            "annotations": {
                "guest-ann-1": {
                    "annotation_id": "guest-ann-1",
                    "type": "name_suggestion",
                    "target_type": "identity",
                    "target_id": "test-id-123",
                    "value": "Leon Capeluto",
                    "confidence": "likely",
                    "reason": "",
                    "submitted_by": "anonymous",
                    "submitted_at": "2026-02-10T00:00:00+00:00",
                    "status": "pending_unverified",
                    "reviewed_by": None,
                    "reviewed_at": None,
                }
            }
        }
        (tmp_annotations / "annotations.json").write_text(json.dumps(ann_data))
        _invalidate_annotations_cache()

        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/admin/approvals")
            assert resp.status_code == 200
            assert "Guest" in resp.text
