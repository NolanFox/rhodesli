"""Tests for confirm button behavior.

Session 138 FB-006: Confirm is now ENABLED for all persons, including unidentified.
User workflow: confirm cluster as real person first, identify (name) later.

Previous behavior (FB-009, Session 120) disabled confirm for unidentified persons.
That was reversed in Session 138 per user feedback.

Covers:
1. review_action_buttons() — confirm active for ALL names
2. Photo modal quick-action confirm — active for all
3. _is_real_name() — still classifies names correctly (used elsewhere)
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 1. review_action_buttons() — main.py
# ---------------------------------------------------------------------------


class TestReviewActionButtonsConfirm:
    """review_action_buttons should render active confirm for all persons."""

    def test_confirm_active_for_unidentified(self):
        """Unidentified Person should get an active confirm button (Session 138 FB-006)."""
        from app.main import review_action_buttons, to_xml

        result = review_action_buttons(
            "id1", "PROPOSED", is_admin=True, nav_prefix="", identity_name="Unidentified Person 1234"
        )
        html = to_xml(result)
        assert "bg-emerald-600" in html
        assert "confirm/id1" in html
        # Should NOT be disabled
        assert "bg-gray-400" not in html
        assert "cursor-not-allowed" not in html

    def test_confirm_active_for_named_person(self):
        """Named person should get an active green confirm button."""
        from app.main import review_action_buttons, to_xml

        result = review_action_buttons("id1", "PROPOSED", is_admin=True, nav_prefix="", identity_name="Albert Fox")
        html = to_xml(result)
        assert "bg-emerald-600" in html
        assert "confirm/id1" in html
        assert "bg-gray-400" not in html

    def test_confirm_active_for_empty_name(self):
        """Empty name should also get active confirm button (Session 138 FB-006)."""
        from app.main import review_action_buttons, to_xml

        result = review_action_buttons("id1", "INBOX", is_admin=True, nav_prefix="", identity_name="")
        html = to_xml(result)
        assert "bg-emerald-600" in html
        assert "confirm" in html.lower()

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


class TestPhotoModalConfirm:
    """Photo modal quick-action confirm should be active for all persons."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_unidentified_face_confirm_active_in_photo_modal(self, mock_reg, mock_dim, mock_meta):
        """Unidentified person's confirm button in photo modal should be active (Session 138 FB-006)."""
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

        # The confirm button should be active (emerald, not gray)
        assert "action=confirm" in html
        assert "bg-emerald-600" in html

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

        assert "action=confirm" in html
        assert "bg-emerald-600" in html


# ---------------------------------------------------------------------------
# 3. _is_real_name — still works correctly (used for display, not blocking)
# ---------------------------------------------------------------------------


class TestIsRealName:
    """_is_real_name correctly classifies names (used for display logic, not confirm blocking)."""

    def test_unidentified_person_is_not_real_name(self):
        from core.registry import IdentityRegistry

        assert not IdentityRegistry._is_real_name("Unidentified Person 999")
        assert not IdentityRegistry._is_real_name("Unidentified Person 1")
        assert not IdentityRegistry._is_real_name(None)
        assert not IdentityRegistry._is_real_name("")

    def test_real_names_are_real(self):
        from core.registry import IdentityRegistry

        assert IdentityRegistry._is_real_name("Albert Fox")
        assert IdentityRegistry._is_real_name("Sarah Gukaylo")
        assert IdentityRegistry._is_real_name("Person With Name")
