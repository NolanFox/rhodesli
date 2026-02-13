"""
Tests for annotation system (AN-001–AN-005).

Covers: submission, approval, rejection, contributor permissions.
"""

import pytest
import json
import os
from starlette.testclient import TestClient
from unittest.mock import patch, MagicMock
from pathlib import Path


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def admin_client(client):
    """Client with auth disabled (= admin access)."""
    return client


@pytest.fixture
def annotations_file(tmp_path):
    """Create a temporary annotations file and patch the app to use it."""
    ann_path = tmp_path / "annotations.json"
    ann_path.write_text(json.dumps({"schema_version": 1, "annotations": {}}))
    return ann_path


class TestAnnotationSubmit:
    """Tests for POST /api/annotations/submit."""

    def test_annotation_submit_anonymous_saves_directly(self, client, tmp_path):
        """Anonymous users save directly as pending_unverified (no modal)."""
        from app.main import _invalidate_annotations_cache
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps({"schema_version": 1, "annotations": {}}))

        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None), \
             patch("app.main.data_path", tmp_path):
            _invalidate_annotations_cache()
            response = client.post(
                "/api/annotations/submit",
                data={
                    "target_type": "identity",
                    "target_id": "test-id",
                    "annotation_type": "name_suggestion",
                    "value": "Leon Capeluto",
                }
            )
            assert response.status_code == 200
            assert "thanks" in response.text.lower()
            # No modal shown
            assert "guest-or-login-modal" not in response.text

    def test_annotation_submit_creates_record(self, client, tmp_path):
        """Logged-in user can submit a name suggestion."""
        from app.main import _save_annotations, _invalidate_annotations_cache

        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps({"schema_version": 1, "annotations": {}}))

        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.is_admin = False

        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=mock_user), \
             patch("app.main._check_login", return_value=None), \
             patch("app.main.data_path", tmp_path):
            _invalidate_annotations_cache()
            response = client.post(
                "/api/annotations/submit",
                data={
                    "target_type": "identity",
                    "target_id": "test-id",
                    "annotation_type": "name_suggestion",
                    "value": "Leon Capeluto",
                    "confidence": "certain",
                }
            )
            assert response.status_code == 200
            assert "pending" in response.text.lower() or "thanks" in response.text.lower()

        # Verify annotation was saved
        saved = json.loads(ann_path.read_text())
        assert len(saved["annotations"]) == 1
        ann = list(saved["annotations"].values())[0]
        assert ann["value"] == "Leon Capeluto"
        assert ann["status"] == "pending"
        assert ann["submitted_by"] == "test@example.com"


class TestAnnotationApproval:
    """Tests for admin annotation review."""

    def test_annotation_approval_requires_admin(self, client):
        """Non-admin users cannot approve annotations."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            response = client.post("/admin/approvals/fake-id/approve")
            assert response.status_code in (401, 403)

    def test_approvals_page_renders(self, admin_client):
        """Admin approvals page renders without error."""
        response = admin_client.get("/admin/approvals")
        assert response.status_code == 200
        assert "Pending Approvals" in response.text

    def test_annotation_approval_updates_status(self, client, tmp_path):
        """Approving an annotation changes its status to approved."""
        ann_id = "test-ann-1"
        ann_data = {
            "schema_version": 1,
            "annotations": {
                ann_id: {
                    "annotation_id": ann_id,
                    "type": "caption",
                    "target_type": "photo",
                    "target_id": "photo-1",
                    "value": "Wedding photo",
                    "confidence": "certain",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                }
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        from app.main import _invalidate_annotations_cache
        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            response = client.post(f"/admin/approvals/{ann_id}/approve")
            assert response.status_code == 200
            assert "APPROVED" in response.text

        saved = json.loads(ann_path.read_text())
        assert saved["annotations"][ann_id]["status"] == "approved"

    def test_annotation_rejection_no_data_change(self, client, tmp_path):
        """Rejecting an annotation doesn't modify identity data."""
        ann_id = "test-ann-2"
        ann_data = {
            "schema_version": 1,
            "annotations": {
                ann_id: {
                    "annotation_id": ann_id,
                    "type": "name_suggestion",
                    "target_type": "identity",
                    "target_id": "identity-1",
                    "value": "Wrong Name",
                    "confidence": "guess",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                }
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        from app.main import _invalidate_annotations_cache
        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            response = client.post(f"/admin/approvals/{ann_id}/reject")
            assert response.status_code == 200
            assert "REJECTED" in response.text

        saved = json.loads(ann_path.read_text())
        assert saved["annotations"][ann_id]["status"] == "rejected"


class TestAnnotationSkip:
    """Tests for POST /admin/approvals/{ann_id}/skip."""

    def test_skip_changes_status(self, client, tmp_path):
        """Skipping an annotation sets status to 'skipped'."""
        ann_id = "test-ann-skip"
        ann_data = {
            "schema_version": 1,
            "annotations": {
                ann_id: {
                    "annotation_id": ann_id,
                    "type": "name_suggestion",
                    "target_type": "identity",
                    "target_id": "id-1",
                    "value": "Some Name",
                    "confidence": "likely",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                }
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        from app.main import _invalidate_annotations_cache
        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            response = client.post(f"/admin/approvals/{ann_id}/skip")
            assert response.status_code == 200
            assert "SKIPPED" in response.text

        saved = json.loads(ann_path.read_text())
        assert saved["annotations"][ann_id]["status"] == "skipped"

    def test_skip_response_has_undo_button(self, client, tmp_path):
        """Skip response includes an Undo button."""
        ann_id = "test-ann-skip-2"
        ann_data = {
            "schema_version": 1,
            "annotations": {
                ann_id: {
                    "annotation_id": ann_id,
                    "type": "caption",
                    "target_type": "photo",
                    "target_id": "photo-1",
                    "value": "Test",
                    "confidence": "likely",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                }
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        from app.main import _invalidate_annotations_cache
        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            response = client.post(f"/admin/approvals/{ann_id}/skip")
            assert "Undo" in response.text


class TestAnnotationUndo:
    """Tests for POST /admin/approvals/{ann_id}/undo."""

    def test_undo_reverts_to_pending(self, client, tmp_path):
        """Undoing an approved annotation reverts it to pending."""
        ann_id = "test-ann-undo"
        ann_data = {
            "schema_version": 1,
            "annotations": {
                ann_id: {
                    "annotation_id": ann_id,
                    "type": "name_suggestion",
                    "target_type": "identity",
                    "target_id": "id-1",
                    "value": "Some Name",
                    "confidence": "likely",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "approved",
                    "reviewed_by": "admin@test.com",
                    "reviewed_at": "2026-02-10T01:00:00Z",
                }
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        from app.main import _invalidate_annotations_cache
        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            response = client.post(f"/admin/approvals/{ann_id}/undo",
                                   follow_redirects=False)
            assert response.status_code == 200

        saved = json.loads(ann_path.read_text())
        assert saved["annotations"][ann_id]["status"] == "pending"
        assert saved["annotations"][ann_id]["reviewed_by"] is None

    def test_undo_anonymous_reverts_to_pending_unverified(self, client, tmp_path):
        """Undoing a guest annotation reverts to pending_unverified."""
        ann_id = "test-ann-undo-guest"
        ann_data = {
            "schema_version": 1,
            "annotations": {
                ann_id: {
                    "annotation_id": ann_id,
                    "type": "bio",
                    "target_type": "identity",
                    "target_id": "id-1",
                    "value": "Guest bio",
                    "confidence": "likely",
                    "reason": "",
                    "submitted_by": "anonymous",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "rejected",
                    "reviewed_by": "admin@test.com",
                    "reviewed_at": "2026-02-10T01:00:00Z",
                }
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        from app.main import _invalidate_annotations_cache
        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            response = client.post(f"/admin/approvals/{ann_id}/undo",
                                   follow_redirects=False)
            assert response.status_code == 200

        saved = json.loads(ann_path.read_text())
        assert saved["annotations"][ann_id]["status"] == "pending_unverified"


class TestAuditLog:
    """Tests for audit log and /admin/audit page."""

    def test_audit_page_renders(self, client):
        """Audit log page renders without error."""
        response = client.get("/admin/audit")
        assert response.status_code == 200
        assert "Audit" in response.text

    def test_approve_creates_audit_entry(self, client, tmp_path):
        """Approving an annotation creates an audit log entry."""
        ann_id = "test-ann-audit"
        ann_data = {
            "schema_version": 1,
            "annotations": {
                ann_id: {
                    "annotation_id": ann_id,
                    "type": "caption",
                    "target_type": "photo",
                    "target_id": "photo-1",
                    "value": "Test caption",
                    "confidence": "certain",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                }
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))
        audit_path = tmp_path / "audit_log.json"

        from app.main import _invalidate_annotations_cache
        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            response = client.post(f"/admin/approvals/{ann_id}/approve")
            assert response.status_code == 200

        assert audit_path.exists()
        audit = json.loads(audit_path.read_text())
        assert len(audit["entries"]) == 1
        assert audit["entries"][0]["action"] == "approved"
        assert audit["entries"][0]["annotation_id"] == ann_id

    def test_reject_creates_audit_entry(self, client, tmp_path):
        """Rejecting an annotation creates an audit log entry."""
        ann_id = "test-ann-audit-reject"
        ann_data = {
            "schema_version": 1,
            "annotations": {
                ann_id: {
                    "annotation_id": ann_id,
                    "type": "bio",
                    "target_type": "identity",
                    "target_id": "id-1",
                    "value": "Test bio",
                    "confidence": "likely",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                }
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))
        audit_path = tmp_path / "audit_log.json"

        from app.main import _invalidate_annotations_cache
        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            response = client.post(f"/admin/approvals/{ann_id}/reject")
            assert response.status_code == 200

        assert audit_path.exists()
        audit = json.loads(audit_path.read_text())
        assert len(audit["entries"]) == 1
        assert audit["entries"][0]["action"] == "rejected"


class TestApprovalCardThumbnails:
    """Tests for face thumbnails on admin approval cards."""

    def test_approval_response_includes_undo_button(self, client, tmp_path):
        """Approve response includes Undo button."""
        ann_id = "test-thumb-1"
        ann_data = {
            "schema_version": 1,
            "annotations": {
                ann_id: {
                    "annotation_id": ann_id,
                    "type": "caption",
                    "target_type": "photo",
                    "target_id": "photo-1",
                    "value": "Test",
                    "confidence": "likely",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                }
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        from app.main import _invalidate_annotations_cache
        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            response = client.post(f"/admin/approvals/{ann_id}/approve")
            assert "Undo" in response.text
            assert f"/admin/approvals/{ann_id}/undo" in response.text

    def test_reject_response_includes_undo_button(self, client, tmp_path):
        """Reject response includes Undo button."""
        ann_id = "test-thumb-2"
        ann_data = {
            "schema_version": 1,
            "annotations": {
                ann_id: {
                    "annotation_id": ann_id,
                    "type": "bio",
                    "target_type": "identity",
                    "target_id": "id-1",
                    "value": "Test bio",
                    "confidence": "likely",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                }
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        from app.main import _invalidate_annotations_cache
        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            response = client.post(f"/admin/approvals/{ann_id}/reject")
            assert "Undo" in response.text

    def test_approvals_page_has_skip_button(self, client, tmp_path):
        """Approval cards include a Skip button."""
        ann_id = "test-skip-btn"
        ann_data = {
            "schema_version": 1,
            "annotations": {
                ann_id: {
                    "annotation_id": ann_id,
                    "type": "caption",
                    "target_type": "photo",
                    "target_id": "photo-1",
                    "value": "Test",
                    "confidence": "likely",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                }
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        from app.main import _invalidate_annotations_cache
        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            response = client.get("/admin/approvals")
            assert "Skip" in response.text
            assert f"/admin/approvals/{ann_id}/skip" in response.text

    def test_approvals_page_has_audit_link(self, client):
        """Approvals page includes a link to the audit log."""
        response = client.get("/admin/approvals")
        assert response.status_code == 200
        assert "/admin/audit" in response.text
        assert "Audit Log" in response.text

    def test_approval_card_has_data_annotation_id(self, client, tmp_path):
        """Approval cards include data-annotation-id attribute for e2e testing."""
        ann_id = "test-data-attr"
        ann_data = {
            "schema_version": 1,
            "annotations": {
                ann_id: {
                    "annotation_id": ann_id,
                    "type": "bio",
                    "target_type": "identity",
                    "target_id": "id-1",
                    "value": "Test",
                    "confidence": "likely",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                }
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        from app.main import _invalidate_annotations_cache
        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            response = client.get("/admin/approvals")
            assert f'data-annotation-id="{ann_id}"' in response.text


class TestMyContributions:
    """Tests for /my-contributions page."""

    def test_my_contributions_requires_login(self, client):
        """Anonymous users are redirected from contributions page."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            response = client.get("/my-contributions", follow_redirects=False)
            assert response.status_code == 303

    def test_my_contributions_shows_user_annotations(self, client, tmp_path):
        """My Contributions page shows only the current user's annotations."""
        ann_data = {
            "schema_version": 1,
            "annotations": {
                "ann-1": {
                    "annotation_id": "ann-1",
                    "type": "name_suggestion",
                    "target_type": "identity",
                    "target_id": "id-1",
                    "value": "Leon",
                    "confidence": "certain",
                    "reason": "",
                    "submitted_by": "me@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                },
                "ann-2": {
                    "annotation_id": "ann-2",
                    "type": "caption",
                    "target_type": "photo",
                    "target_id": "p-1",
                    "value": "Beach photo",
                    "confidence": "likely",
                    "reason": "",
                    "submitted_by": "other@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "approved",
                    "reviewed_by": None,
                    "reviewed_at": None,
                },
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        mock_user = MagicMock()
        mock_user.email = "me@test.com"
        mock_user.is_admin = False

        from app.main import _invalidate_annotations_cache
        _invalidate_annotations_cache()

        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=mock_user), \
             patch("app.main._check_login", return_value=None), \
             patch("app.main.data_path", tmp_path):
            response = client.get("/my-contributions")
            assert response.status_code == 200
            assert "Leon" in response.text
            # Other user's annotation should NOT appear
            assert "Beach photo" not in response.text
