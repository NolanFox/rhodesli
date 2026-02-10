"""
Route-level tests for the undo merge endpoint.

Tests verify:
1. Merge response includes Undo button (admin only)
2. Undo route restores identities after merge
3. Undo route returns error when no merge history
4. Contributor cannot access undo endpoint
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from core.registry import IdentityRegistry, IdentityState
from core.photo_registry import PhotoRegistry


@pytest.fixture
def merge_registries(tmp_path):
    """Create identity and photo registries with two mergeable identities."""
    photo_reg = PhotoRegistry()
    photo_reg.register_face("photo_1", "/path/photo_1.jpg", "face_a")
    photo_reg.register_face("photo_2", "/path/photo_2.jpg", "face_b")

    identity_reg = IdentityRegistry()
    target_id = identity_reg.create_identity(
        anchor_ids=["face_a"],
        user_source="test",
        name="Alice",
        state=IdentityState.CONFIRMED,
    )
    source_id = identity_reg.create_identity(
        anchor_ids=["face_b"],
        user_source="test",
    )
    return identity_reg, photo_reg, target_id, source_id


class TestUndoMergeButtonVisibility:
    """Admin sees Undo button in merge response toast."""

    def test_merge_toast_includes_undo_button(self, merge_registries):
        """After a merge, the response toast contains an Undo button."""
        identity_reg, photo_reg, target_id, source_id = merge_registries

        with patch("app.main.load_registry", return_value=identity_reg), \
             patch("app.main.save_registry"), \
             patch("app.main.load_photo_registry", return_value=photo_reg), \
             patch("app.main.is_auth_enabled", return_value=False):
            from app.main import app
            client = TestClient(app)
            response = client.post(
                f"/api/identity/{target_id}/merge/{source_id}",
                headers={"HX-Request": "true"})

        assert response.status_code == 200
        assert "Undo" in response.text
        assert "undo-merge" in response.text

    def test_undo_button_hidden_for_contributor(self):
        """Contributors get 403 when trying to undo a merge."""
        from app.auth import User
        from app.main import app

        client = TestClient(app)
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=User(
                 id="c1", email="contributor@test.com",
                 is_admin=False, role="contributor")):
            response = client.post(
                "/api/identity/some-id/undo-merge",
                headers={"HX-Request": "true"})

        assert response.status_code == 403


class TestUndoMergeRestoresIdentities:
    """Undoing a merge restores both identities with original faces."""

    def test_undo_merge_restores_identities(self, merge_registries):
        """Merge then undo: both identities should be restored."""
        identity_reg, photo_reg, target_id, source_id = merge_registries

        # Perform merge (source_id, target_id, user_source, photo_registry)
        identity_reg.merge_identities(source_id, target_id, "test", photo_reg)

        # Source should be marked as merged
        source = identity_reg.get_identity(source_id)
        assert source.get("merged_into") == target_id

        with patch("app.main.load_registry", return_value=identity_reg), \
             patch("app.main.save_registry"), \
             patch("app.main.is_auth_enabled", return_value=False):
            from app.main import app
            client = TestClient(app)
            response = client.post(
                f"/api/identity/{target_id}/undo-merge",
                headers={"HX-Request": "true"})

        assert response.status_code == 200
        assert "Merge undone" in response.text

        # Target should have original face only
        target = identity_reg.get_identity(target_id)
        all_faces = target.get("anchor_ids", []) + target.get("candidate_ids", [])
        assert "face_a" in all_faces
        assert "face_b" not in all_faces

        # Source should be restored (not merged)
        source = identity_reg.get_identity(source_id)
        assert "merged_into" not in source or source.get("merged_into") is None


class TestUndoMergeNoHistory:
    """Undo returns error when no merge history exists."""

    def test_undo_merge_no_history_returns_409(self):
        """Undo on identity with no merges returns warning toast."""
        identity_reg = IdentityRegistry()
        fresh_id = identity_reg.create_identity(
            anchor_ids=["face_x"],
            user_source="test",
            name="NeverMerged",
            state=IdentityState.CONFIRMED,
        )

        with patch("app.main.load_registry", return_value=identity_reg), \
             patch("app.main.save_registry"), \
             patch("app.main.is_auth_enabled", return_value=False):
            from app.main import app
            client = TestClient(app)
            response = client.post(
                f"/api/identity/{fresh_id}/undo-merge",
                headers={"HX-Request": "true"})

        assert response.status_code == 409
        assert "Nothing to undo" in response.text

    def test_undo_merge_nonexistent_identity_returns_404(self):
        """Undo on nonexistent identity returns 404."""
        identity_reg = IdentityRegistry()

        with patch("app.main.load_registry", return_value=identity_reg), \
             patch("app.main.is_auth_enabled", return_value=False):
            from app.main import app
            client = TestClient(app)
            response = client.post(
                "/api/identity/nonexistent-id/undo-merge",
                headers={"HX-Request": "true"})

        assert response.status_code == 404
