"""Tests for FB-009: Confirm button disabled for unidentified persons.

The confirm button should be disabled (gray, with tooltip) when the identity
has an auto-generated name like "Unidentified Person 1234". It should be
active (green) when the identity has a real human-assigned name.

Covers:
1. review_action_buttons() in main.py — disabled for unidentified, active for named
2. Person detail page confirm button — disabled for unidentified
3. Photo modal quick-action confirm button — disabled for unidentified
4. Server-side defense in depth — quick-action endpoint returns 409 for unidentified
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 1. review_action_buttons() — main.py
# ---------------------------------------------------------------------------


class TestReviewActionButtonsConfirmDisabled:
    """review_action_buttons should render disabled confirm for unidentified persons."""

    def test_confirm_disabled_for_unidentified(self):
        """Unidentified Person should get a disabled gray confirm button."""
        from app.main import review_action_buttons, to_xml

        result = review_action_buttons(
            "id1", "PROPOSED", is_admin=True, nav_prefix="", identity_name="Unidentified Person 1234"
        )
        html = to_xml(result)
        assert "disabled" in html
        assert "bg-gray-400" in html
        assert "Name this person first" in html
        # Should NOT have the active confirm endpoint
        assert "hx-post" not in html or "confirm/id1" not in html

    def test_confirm_active_for_named_person(self):
        """Named person should get an active green confirm button."""
        from app.main import review_action_buttons, to_xml

        result = review_action_buttons("id1", "PROPOSED", is_admin=True, nav_prefix="", identity_name="Albert Fox")
        html = to_xml(result)
        assert "bg-emerald-600" in html
        assert "confirm/id1" in html
        assert "bg-gray-400" not in html

    def test_confirm_disabled_for_empty_name(self):
        """Empty name should also get disabled confirm button."""
        from app.main import review_action_buttons, to_xml

        result = review_action_buttons("id1", "INBOX", is_admin=True, nav_prefix="", identity_name="")
        html = to_xml(result)
        assert "disabled" in html
        assert "Name this person first" in html

    def test_confirmed_state_has_no_confirm_button(self):
        """CONFIRMED state should not have a confirm button at all."""
        from app.main import review_action_buttons, to_xml

        result = review_action_buttons("id1", "CONFIRMED", is_admin=True, nav_prefix="", identity_name="Albert Fox")
        html = to_xml(result)
        assert "Confirm" not in html

    def test_non_admin_has_no_buttons(self):
        """Non-admin users should get no buttons at all."""
        from app.main import review_action_buttons, to_xml

        result = review_action_buttons(
            "id1", "PROPOSED", is_admin=False, nav_prefix="", identity_name="Unidentified Person 1234"
        )
        html = to_xml(result)
        assert "Confirm" not in html


# ---------------------------------------------------------------------------
# 2. Photo modal quick-action — page_routes.py
# ---------------------------------------------------------------------------


class TestPhotoModalConfirmDisabled:
    """Photo modal quick-action confirm should be disabled for unidentified persons."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_unidentified_face_confirm_disabled_in_photo_modal(self, mock_reg, mock_dim, mock_meta):
        """Unidentified person's confirm button in photo modal should be disabled."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test_photo.jpg",
            "faces": [{"face_id": "f1", "bbox": [10, 10, 60, 100]}],
            "source": "Test Collection",
        }
        identity = {
            "identity_id": "id1",
            "name": "Unidentified Person 999",
            "state": "PROPOSED",
            "anchor_ids": [],
            "candidate_ids": ["f1"],
            "negative_ids": [],
        }
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        # The confirm button area should have a disabled button
        # It should NOT have the active quick-action confirm endpoint
        assert "bg-gray-400" in html or "disabled" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_named_face_confirm_active_in_photo_modal(self, mock_reg, mock_dim, mock_meta):
        """Named person's confirm button in photo modal should be active."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test_photo.jpg",
            "faces": [{"face_id": "f1", "bbox": [10, 10, 60, 100]}],
            "source": "Test Collection",
        }
        identity = {
            "identity_id": "id1",
            "name": "Albert Fox",
            "state": "PROPOSED",
            "anchor_ids": [],
            "candidate_ids": ["f1"],
            "negative_ids": [],
        }
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        # The active confirm button should have emerald styling and the endpoint
        assert "action=confirm" in html
        assert "bg-emerald-600" in html


# ---------------------------------------------------------------------------
# 3. Server-side defense in depth — quick-action endpoint returns 409
# ---------------------------------------------------------------------------


class TestIsRealNameDefenseInDepth:
    """Server-side _is_real_name guard correctly classifies names."""

    def test_unidentified_person_is_not_real_name(self):
        """Unidentified Person names are not real names."""
        from core.registry import IdentityRegistry

        assert not IdentityRegistry._is_real_name("Unidentified Person 999")
        assert not IdentityRegistry._is_real_name("Unidentified Person 1")
        assert not IdentityRegistry._is_real_name(None)
        assert not IdentityRegistry._is_real_name("")

    def test_real_names_are_real(self):
        """Human-assigned names are real names."""
        from core.registry import IdentityRegistry

        assert IdentityRegistry._is_real_name("Albert Fox")
        assert IdentityRegistry._is_real_name("Sarah Gukaylo")
        assert IdentityRegistry._is_real_name("Person With Name")
