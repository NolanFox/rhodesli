"""
Tests for the restore (undo reject) feature.

Tests cover:
- Registry reset_identity method for REJECTED -> INBOX
- POST /api/identity/{id}/restore route
- Admin permission guard
- State validation (only REJECTED/CONTESTED can be restored)
"""

import pytest
from unittest.mock import patch, MagicMock

from core.registry import IdentityRegistry, IdentityState


class TestRegistryResetFromRejected:
    """Tests for reset_identity() on REJECTED identities."""

    def test_reset_rejected_to_inbox(self):
        """Resetting a REJECTED identity should move it to INBOX."""
        registry = IdentityRegistry()
        identity_id = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        registry.reject_identity(identity_id, user_source="test")
        assert registry.get_identity(identity_id)["state"] == "REJECTED"

        registry.reset_identity(identity_id, user_source="web_restore")

        identity = registry.get_identity(identity_id)
        assert identity["state"] == "INBOX"

    def test_reset_contested_to_inbox(self):
        """Resetting a CONTESTED identity should move it to INBOX."""
        registry = IdentityRegistry()
        identity_id = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        registry.contest_identity(identity_id, user_source="test", reason="test")
        assert registry.get_identity(identity_id)["state"] == "CONTESTED"

        registry.reset_identity(identity_id, user_source="web_restore")

        identity = registry.get_identity(identity_id)
        assert identity["state"] == "INBOX"

    def test_reset_records_event(self):
        """Resetting should record a RESET event with previous state."""
        registry = IdentityRegistry()
        identity_id = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        registry.reject_identity(identity_id, user_source="test")

        registry.reset_identity(identity_id, user_source="web_restore")

        history = registry.get_history(identity_id)
        reset_events = [e for e in history if e["action"] == "reset"]
        assert len(reset_events) == 1
        assert reset_events[0]["metadata"]["previous_state"] == "REJECTED"
        assert reset_events[0]["metadata"]["new_state"] == "INBOX"

    def test_reset_increments_version(self):
        """Resetting should increment the version_id."""
        registry = IdentityRegistry()
        identity_id = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        registry.reject_identity(identity_id, user_source="test")
        version_before = registry.get_identity(identity_id)["version_id"]

        registry.reset_identity(identity_id, user_source="web_restore")

        assert registry.get_identity(identity_id)["version_id"] == version_before + 1

    def test_reset_proposed_raises_error_default_state(self):
        """Cannot reset an identity that's in PROPOSED (default) state."""
        registry = IdentityRegistry()
        identity_id = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        # Default state is PROPOSED — already in review queue
        assert registry.get_identity(identity_id)["state"] == "PROPOSED"

        with pytest.raises(ValueError, match="cannot be reset"):
            registry.reset_identity(identity_id, user_source="web_restore")

    def test_reset_proposed_raises_error(self):
        """Cannot reset an identity that's in PROPOSED (reviewable) state."""
        registry = IdentityRegistry()
        identity_id = registry.create_identity(anchor_ids=["face_a"], user_source="test", state=IdentityState.PROPOSED)

        with pytest.raises(ValueError, match="cannot be reset"):
            registry.reset_identity(identity_id, user_source="web_restore")


class TestRestoreRoute:
    """Tests for POST /api/identity/{id}/restore route."""

    # Common patches for the restore route in identity_routes.py
    _PATCH_PREFIX = "app.identity_routes._main_mod"

    def _make_rejected_registry(self):
        """Create a registry with a REJECTED identity for testing."""
        registry = IdentityRegistry()
        identity_id = registry.create_identity(anchor_ids=["face_a"], user_source="test", name="Test Person")
        registry.reject_identity(identity_id, user_source="test")
        return registry, identity_id

    def test_restore_rejected_to_inbox(self):
        """POST /api/identity/{id}/restore should restore REJECTED to INBOX."""
        import app.main as main_mod

        registry, identity_id = self._make_rejected_registry()

        with (
            patch(f"{self._PATCH_PREFIX}.load_registry", return_value=registry),
            patch(f"{self._PATCH_PREFIX}.save_registry"),
            patch(f"{self._PATCH_PREFIX}._check_admin", return_value=None),
            patch(f"{self._PATCH_PREFIX}.is_auth_enabled", return_value=False),
            patch(f"{self._PATCH_PREFIX}.log_user_action"),
            patch(f"{self._PATCH_PREFIX}._check_merged_identity", return_value=(False, None)),
            patch(f"{self._PATCH_PREFIX}.get_current_user", return_value=None),
            patch("app.identity_routes._check_origin", return_value=None),
            patch("app.identity_routes._log_audit"),
        ):
            from starlette.testclient import TestClient

            client = TestClient(main_mod.app)
            response = client.post(
                f"/api/identity/{identity_id}/restore?from_person_page=true",
            )

        assert response.status_code == 200
        assert registry.get_identity(identity_id)["state"] == "INBOX"

    def test_restore_requires_admin(self):
        """Non-admin should be denied access to restore."""
        import app.main as main_mod
        from starlette.responses import Response as StarletteResponse

        registry, identity_id = self._make_rejected_registry()

        with (
            patch("app.identity_routes._check_origin", return_value=None),
            patch(f"{self._PATCH_PREFIX}._check_admin", return_value=StarletteResponse("Forbidden", status_code=403)),
        ):
            from starlette.testclient import TestClient

            client = TestClient(main_mod.app)
            response = client.post(
                f"/api/identity/{identity_id}/restore",
            )

        assert response.status_code == 403

    def test_restore_only_rejected_or_contested(self):
        """Cannot restore an identity that's not REJECTED or CONTESTED."""
        import app.main as main_mod

        registry = IdentityRegistry()
        identity_id = registry.create_identity(anchor_ids=["face_a"], user_source="test", name="Test Person")
        # Confirm it — CONFIRMED should not be restorable via this endpoint
        registry.confirm_identity(identity_id, user_source="test")

        with (
            patch(f"{self._PATCH_PREFIX}.load_registry", return_value=registry),
            patch(f"{self._PATCH_PREFIX}.save_registry"),
            patch(f"{self._PATCH_PREFIX}._check_admin", return_value=None),
            patch(f"{self._PATCH_PREFIX}.is_auth_enabled", return_value=False),
            patch(f"{self._PATCH_PREFIX}._check_merged_identity", return_value=(False, None)),
            patch("app.identity_routes._check_origin", return_value=None),
        ):
            from starlette.testclient import TestClient

            client = TestClient(main_mod.app)
            response = client.post(
                f"/api/identity/{identity_id}/restore",
            )

        assert response.status_code == 400
        assert "CONFIRMED" in response.text

    def test_restore_returns_action_buttons_on_person_page(self):
        """On person page, restore should return the INBOX action buttons."""
        import app.main as main_mod

        registry, identity_id = self._make_rejected_registry()

        with (
            patch(f"{self._PATCH_PREFIX}.load_registry", return_value=registry),
            patch(f"{self._PATCH_PREFIX}.save_registry"),
            patch(f"{self._PATCH_PREFIX}._check_admin", return_value=None),
            patch(f"{self._PATCH_PREFIX}.is_auth_enabled", return_value=False),
            patch(f"{self._PATCH_PREFIX}.log_user_action"),
            patch(f"{self._PATCH_PREFIX}._check_merged_identity", return_value=(False, None)),
            patch(f"{self._PATCH_PREFIX}.get_current_user", return_value=None),
            patch("app.identity_routes._check_origin", return_value=None),
            patch("app.identity_routes._log_audit"),
        ):
            from starlette.testclient import TestClient

            client = TestClient(main_mod.app)
            response = client.post(
                f"/api/identity/{identity_id}/restore?from_person_page=true",
            )

        assert response.status_code == 200
        html = response.text
        # Should contain the action buttons for INBOX state
        assert "Confirm" in html
        assert "Skip" in html
        assert "Reject" in html
        assert "person-admin-actions" in html

    def test_restore_identity_not_found(self):
        """Restore should return 404 for non-existent identity."""
        import app.main as main_mod

        registry = IdentityRegistry()

        with (
            patch(f"{self._PATCH_PREFIX}.load_registry", return_value=registry),
            patch(f"{self._PATCH_PREFIX}._check_admin", return_value=None),
            patch(f"{self._PATCH_PREFIX}._check_merged_identity", return_value=(False, None)),
            patch("app.identity_routes._check_origin", return_value=None),
        ):
            from starlette.testclient import TestClient

            client = TestClient(main_mod.app)
            response = client.post(
                "/api/identity/nonexistent-id/restore",
                headers={"Origin": "http://testserver"},
            )

        assert response.status_code == 404
