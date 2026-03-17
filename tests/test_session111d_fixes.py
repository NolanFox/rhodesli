"""
Tests for Session 111d — Feedback Fix Sprint.

FB-068: Confirm button merges with best match when one exists.
FB-070: CI test fix (separate commit).
"""

import pytest
from unittest.mock import patch, MagicMock

from core.registry import IdentityRegistry, IdentityState
from core.photo_registry import PhotoRegistry
from app.auth import User


HTMX_HEADERS = {"HX-Request": "true"}


@pytest.fixture
def admin_user():
    user = User(id="test-admin", email="admin@test.com", is_admin=True, role="admin")
    with patch("app.main.get_current_user", return_value=user), patch("app.main.is_auth_enabled", return_value=True):
        yield user


@pytest.fixture
def confirm_merge_registry():
    """Registry with a PROPOSED identity and a CONFIRMED target for merge."""
    reg = IdentityRegistry()
    target_id = reg.create_identity(
        anchor_ids=["face_target_1", "face_target_2"],
        user_source="test",
        name="Charles Fox",
        state=IdentityState.CONFIRMED,
    )
    source_id = reg.create_identity(
        anchor_ids=["face_source_1"],
        user_source="test",
        name="Bob Test",
        state=IdentityState.PROPOSED,
    )
    inbox_id = reg.create_identity(
        anchor_ids=["face_inbox_1"],
        user_source="test",
        state=IdentityState.INBOX,
    )
    photo_reg = PhotoRegistry()
    photo_reg.register_face("photo_1", "/path/photo_1.jpg", "face_target_1")
    photo_reg.register_face("photo_2", "/path/photo_2.jpg", "face_target_2")
    photo_reg.register_face("photo_3", "/path/photo_3.jpg", "face_source_1")
    photo_reg.register_face("photo_4", "/path/photo_4.jpg", "face_inbox_1")
    return reg, target_id, source_id, inbox_id, photo_reg


class TestConfirmMerge:
    """FB-068: Confirm button merges with best match when strong match exists."""

    def test_confirm_with_strong_match_merges(self, client, admin_user, confirm_merge_registry):
        """When best match exists, confirm merges source into target."""
        reg, target_id, source_id, inbox_id, photo_reg = confirm_merge_registry
        best_match = {
            "target_identity_id": target_id,
            "target_identity_name": "Charles Fox",
            "distance": 0.75,
            "confidence": "VERY HIGH",
        }

        with (
            patch("app.main.load_registry", return_value=reg),
            patch("app.main.save_registry"),
            patch("app.main._get_best_match_for_identity", return_value=best_match),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.log_user_action"),
        ):
            resp = client.post(f"/confirm/{source_id}", headers=HTMX_HEADERS)
            assert resp.status_code == 200
            assert "Merged into Charles Fox" in resp.text

    def test_confirm_without_match_confirms_normally(self, client, admin_user, confirm_merge_registry):
        """When no best match, confirm promotes to CONFIRMED as before."""
        reg, target_id, source_id, inbox_id, photo_reg = confirm_merge_registry

        with (
            patch("app.main.load_registry", return_value=reg),
            patch("app.main.save_registry"),
            patch("app.main._get_best_match_for_identity", return_value=None),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.log_user_action"),
        ):
            resp = client.post(f"/confirm/{source_id}", headers=HTMX_HEADERS)
            assert resp.status_code == 200
            assert "confirmed" in resp.text.lower()

    def test_confirm_with_weak_match_does_not_merge(self, client, admin_user, confirm_merge_registry):
        """When best match is LOW confidence, confirm normally without merge."""
        reg, target_id, source_id, inbox_id, photo_reg = confirm_merge_registry
        best_match = {
            "target_identity_id": target_id,
            "target_identity_name": "Charles Fox",
            "distance": 1.5,
            "confidence": "LOW",
        }

        with (
            patch("app.main.load_registry", return_value=reg),
            patch("app.main.save_registry"),
            patch("app.main._get_best_match_for_identity", return_value=best_match),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.log_user_action"),
        ):
            resp = client.post(f"/confirm/{source_id}", headers=HTMX_HEADERS)
            assert resp.status_code == 200
            # Should confirm normally, not merge
            assert "Merged into" not in resp.text

    def test_inbox_confirm_with_strong_match_merges(self, client, admin_user, confirm_merge_registry):
        """Inbox confirm also merges with best match when strong."""
        reg, target_id, source_id, inbox_id, photo_reg = confirm_merge_registry
        best_match = {
            "target_identity_id": target_id,
            "target_identity_name": "Charles Fox",
            "distance": 0.90,
            "confidence": "HIGH",
        }

        with (
            patch("app.main.load_registry", return_value=reg),
            patch("app.main.save_registry"),
            patch("app.main._get_best_match_for_identity", return_value=best_match),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.log_user_action"),
        ):
            resp = client.post(f"/inbox/{inbox_id}/confirm", headers=HTMX_HEADERS)
            assert resp.status_code == 200
            assert "Merged into Charles Fox" in resp.text

    def test_confirm_merge_from_focus_returns_next_card(self, client, admin_user, confirm_merge_registry):
        """In focus mode, confirm-merge still returns next focus card."""
        reg, target_id, source_id, inbox_id, photo_reg = confirm_merge_registry
        best_match = {
            "target_identity_id": target_id,
            "target_identity_name": "Charles Fox",
            "distance": 0.75,
            "confidence": "VERY HIGH",
        }

        with (
            patch("app.main.load_registry", return_value=reg),
            patch("app.main.save_registry"),
            patch("app.main._get_best_match_for_identity", return_value=best_match),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.get_next_focus_card", return_value="<div>next card</div>"),
            patch("app.main.log_user_action"),
        ):
            resp = client.post(
                f"/confirm/{source_id}?from_focus=true",
                headers=HTMX_HEADERS,
            )
            assert resp.status_code == 200
            assert "Merged into Charles Fox" in resp.text
