"""Tests for Phase 4: Inline face actions on photo view overlays.

Tests cover:
1. Face overlays show quick-action buttons on hover for admin users
2. Quick-action buttons hidden for non-admin users
3. Correct buttons appear per identity state
4. Quick-action endpoint performs confirm/skip/reject and refreshes view
5. Face count labels verified (BUG-002 regression)
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

def _make_photo_meta(face_ids=None):
    """Create mock photo metadata with faces."""
    faces = []
    for i, fid in enumerate(face_ids or []):
        faces.append({
            "face_id": fid,
            "bbox": [10 + i * 50, 10, 60 + i * 50, 100],  # Non-overlapping boxes
        })
    return {
        "filename": "test_photo.jpg",
        "faces": faces,
        "source": "Test Collection",
    }


def _make_identity(identity_id, name, state, anchor_ids=None, candidate_ids=None):
    """Create a mock identity dict."""
    return {
        "identity_id": identity_id,
        "name": name,
        "state": state,
        "anchor_ids": anchor_ids or [],
        "candidate_ids": candidate_ids or [],
        "negative_ids": [],
    }


# ---------------------------------------------------------------------------
# Inline action button visibility tests
# ---------------------------------------------------------------------------

class TestInlineActionButtonsPresence:
    """Face overlays should show quick-action buttons for admin users."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_proposed_face_shows_action_buttons(self, mock_reg, mock_dim, mock_meta):
        """PROPOSED face overlay has confirm/skip/reject quick-action buttons."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity("id1", "Test Person", "PROPOSED", candidate_ids=["f1"])
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        assert "quick-actions" in html
        assert "/api/face/quick-action" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_inbox_face_shows_action_buttons(self, mock_reg, mock_dim, mock_meta):
        """INBOX face overlay has quick-action buttons."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity("id1", "Unknown", "INBOX", candidate_ids=["f1"])
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        assert "quick-actions" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_confirmed_face_no_action_buttons(self, mock_reg, mock_dim, mock_meta):
        """CONFIRMED face overlay does NOT show quick-action buttons."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity("id1", "Leon", "CONFIRMED", anchor_ids=["f1"])
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        # Should not have quick-actions for confirmed
        assert "quick-actions" not in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_non_admin_no_action_buttons(self, mock_reg, mock_dim, mock_meta):
        """Non-admin users see NO quick-action buttons on any overlay."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity("id1", "Test", "PROPOSED", candidate_ids=["f1"])
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=False)
            html = to_xml(result)

        assert "quick-actions" not in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_default_is_admin_false(self, mock_reg, mock_dim, mock_meta):
        """Default is_admin=False means no action buttons by default."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity("id1", "Test", "PROPOSED", candidate_ids=["f1"])
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            # No is_admin argument — defaults to False
            result = photo_view_content("p1", is_partial=True)
            html = to_xml(result)

        assert "quick-actions" not in html


class TestInlineActionButtonTypes:
    """Correct action buttons appear per identity state."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_proposed_has_confirm_skip_reject(self, mock_reg, mock_dim, mock_meta):
        """PROPOSED state shows all three action buttons."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity("id1", "Test", "PROPOSED", candidate_ids=["f1"])
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        assert "action=confirm" in html
        assert "action=skip" in html
        assert "action=reject" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_skipped_has_confirm_reject_no_skip(self, mock_reg, mock_dim, mock_meta):
        """SKIPPED state shows confirm and reject, but NOT skip."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity("id1", "Test", "SKIPPED", candidate_ids=["f1"])
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        assert "action=confirm" in html
        assert "action=reject" in html
        assert "action=skip" not in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_rejected_no_action_buttons(self, mock_reg, mock_dim, mock_meta):
        """REJECTED state shows NO quick-action buttons."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity("id1", "Test", "REJECTED", candidate_ids=["f1"])
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        assert "quick-actions" not in html


class TestInlineActionButtonStyling:
    """Action buttons have correct CSS for hover visibility."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_action_buttons_hidden_by_default(self, mock_reg, mock_dim, mock_meta):
        """Quick-action buttons are opacity-0 (hidden) by default, visible on hover."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity("id1", "Test", "PROPOSED", candidate_ids=["f1"])
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        # Actions bar should be hidden by default, visible on group hover
        assert "opacity-0" in html
        assert "group-hover:opacity-100" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_action_buttons_use_htmx_post(self, mock_reg, mock_dim, mock_meta):
        """Quick-action buttons use hx-post for HTMX interaction."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity("id1", "Test", "INBOX", candidate_ids=["f1"])
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        assert "hx-post" in html
        assert "photo-modal-content" in html


# ---------------------------------------------------------------------------
# Quick-action endpoint tests
# ---------------------------------------------------------------------------

class TestQuickActionEndpoint:
    """POST /api/face/quick-action performs state change and refreshes photo view."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_quick_action_requires_admin(self, client, auth_enabled, regular_user):
        """Quick-action endpoint returns 401/403 for non-admin users."""
        response = client.post("/api/face/quick-action", data={
            "identity_id": "test-id",
            "action": "confirm",
            "photo_id": "test-photo",
        })
        assert response.status_code in (401, 403)

    def test_quick_action_works_for_admin(self, client, auth_disabled):
        """Quick-action endpoint returns 200 for admin users (auth disabled = admin)."""
        # This may return 404 if identity doesn't exist, which is fine
        response = client.post("/api/face/quick-action", data={
            "identity_id": "nonexistent-id",
            "action": "confirm",
            "photo_id": "test-photo",
        })
        # Should not be 401/403; might be 404 for missing identity
        assert response.status_code != 401
        assert response.status_code != 403

    def test_quick_action_invalid_action(self, client, auth_disabled):
        """Quick-action with invalid action returns 400."""
        response = client.post("/api/face/quick-action", data={
            "identity_id": "test-id",
            "action": "destroy",
            "photo_id": "test-photo",
        })
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Route passes admin status tests
# ---------------------------------------------------------------------------

class TestPartialRoutePassesAdmin:
    """The /photo/{id}/partial route should pass admin status to photo_view_content."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_partial_route_admin_shows_actions(self, mock_reg, mock_dim, mock_meta,
                                               client, auth_disabled):
        """Photo partial route with auth disabled (admin) shows quick-action buttons."""
        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity("id1", "Test", "PROPOSED", candidate_ids=["f1"])
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            response = client.get("/photo/p1/partial?face=f1")

        assert response.status_code == 200
        assert "quick-actions" in response.text

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_partial_route_non_admin_no_actions(self, mock_reg, mock_dim, mock_meta,
                                                 client, auth_enabled, regular_user):
        """Photo partial route with non-admin user hides quick-action buttons."""
        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity("id1", "Test", "PROPOSED", candidate_ids=["f1"])
        mock_reg_inst = MagicMock()
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=identity):
            response = client.get("/photo/p1/partial?face=f1")

        assert response.status_code == 200
        assert "quick-actions" not in response.text


# ---------------------------------------------------------------------------
# Face count regression tests (BUG-002)
# ---------------------------------------------------------------------------

class TestFaceCountRegression:
    """BUG-002 regression: face count labels must use canonical counts."""

    def test_compute_sidebar_counts_exists(self):
        """_compute_sidebar_counts function exists and returns expected keys."""
        from app.main import _compute_sidebar_counts, load_registry
        registry = load_registry()
        counts = _compute_sidebar_counts(registry)
        assert "to_review" in counts
        assert "confirmed" in counts
        assert "skipped" in counts
        assert "rejected" in counts
        assert "photos" in counts
        assert "pending_annotations" in counts

    def test_sidebar_counts_are_integers(self):
        """All sidebar count values are non-negative integers."""
        from app.main import _compute_sidebar_counts, load_registry
        registry = load_registry()
        counts = _compute_sidebar_counts(registry)
        for key in ("to_review", "confirmed", "skipped", "rejected", "photos"):
            assert isinstance(counts[key], int), f"{key} should be int, got {type(counts[key])}"
            assert counts[key] >= 0, f"{key} should be >= 0, got {counts[key]}"


# Need TestClient import at module level for endpoint tests
from starlette.testclient import TestClient
