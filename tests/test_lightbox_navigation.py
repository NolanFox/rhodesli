"""Regression tests for BUG-001: Lightbox arrows disappear after HTMX content swaps.

The root cause was that arrow buttons used inline onclick handlers and keyboard
listeners were re-registered per HTMX swap. When HTMX replaces DOM content, the
inline handlers die. The fix uses event delegation: ONE global listener on
document dispatches clicks based on data-action attributes. Arrows use
data-action="lightbox-prev" / "lightbox-next" instead of onclick.

These tests verify the event delegation pattern survives HTMX swaps.
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Photo modal navigation (Photos grid -> photo_view_content)
# ---------------------------------------------------------------------------

class TestPhotoModalArrowsUseDataAction:
    """Arrow buttons in photo modal must use data-action, not onclick."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_prev_button_has_data_action(self, mock_reg, mock_dim, mock_meta):
        """Prev arrow uses data-action='photo-nav-prev' instead of onclick."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=5
        )
        html = to_xml(result)

        assert 'data-action="photo-nav-prev"' in html
        # Must NOT use inline onclick for navigation
        assert 'onclick="if(typeof photoNavTo' not in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_next_button_has_data_action(self, mock_reg, mock_dim, mock_meta):
        """Next arrow uses data-action='photo-nav-next' instead of onclick."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=5
        )
        html = to_xml(result)

        assert 'data-action="photo-nav-next"' in html
        assert 'onclick="if(typeof photoNavTo' not in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_prev_button_has_nav_index_data(self, mock_reg, mock_dim, mock_meta):
        """Prev button carries data-nav-idx so delegation knows where to go."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=5
        )
        html = to_xml(result)

        # Prev button navigates to nav_idx - 1 = 0
        assert 'data-nav-idx="0"' in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_next_button_has_nav_index_data(self, mock_reg, mock_dim, mock_meta):
        """Next button carries data-nav-idx so delegation knows where to go."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=5
        )
        html = to_xml(result)

        # Next button navigates to nav_idx + 1 = 2
        assert 'data-nav-idx="2"' in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_prev_button_has_fallback_url(self, mock_reg, mock_dim, mock_meta):
        """Prev button has data-nav-url for fallback when photoNavTo is unavailable."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=5
        )
        html = to_xml(result)

        assert 'data-nav-url="/photo/p0/partial' in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_next_button_has_fallback_url(self, mock_reg, mock_dim, mock_meta):
        """Next button has data-nav-url for fallback when photoNavTo is unavailable."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=5
        )
        html = to_xml(result)

        assert 'data-nav-url="/photo/p2/partial' in html


class TestNoPerSwapKeyboardScript:
    """The photo modal must NOT inject per-swap keyboard listeners.

    Instead, there should be a single global event delegation listener that
    never needs rebinding.
    """

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_no_per_swap_keyboard_rebinding(self, mock_reg, mock_dim, mock_meta):
        """Photo partial must not rebind keyboard listeners on every swap."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=3
        )
        html = to_xml(result)

        # Must NOT have the old per-swap pattern of removeEventListener + addEventListener
        assert "removeEventListener('keydown',window._pmKb)" not in html
        assert "window._pmKb=pmkh" not in html


# ---------------------------------------------------------------------------
# Global event delegation script (in page layout)
# ---------------------------------------------------------------------------

class TestGlobalEventDelegation:
    """The main page must include ONE global event delegation script."""

    def test_page_includes_event_delegation_script(self, client):
        """Main page includes the global lightbox event delegation script."""
        response = client.get("/?section=to_review")
        assert response.status_code == 200
        html = response.text

        # Must include the global delegation handler
        assert "data-action" in html
        assert "photo-nav-prev" in html
        assert "photo-nav-next" in html

    def test_page_delegation_handles_keyboard(self, client):
        """Global delegation script handles ArrowLeft/ArrowRight."""
        response = client.get("/?section=to_review")
        html = response.text

        assert "ArrowLeft" in html
        assert "ArrowRight" in html


# ---------------------------------------------------------------------------
# Identity lightbox navigation (identity photos viewer)
# ---------------------------------------------------------------------------

class TestIdentityLightboxArrows:
    """Identity lightbox prev/next buttons must also use event delegation."""

    @patch("app.main.load_registry")
    @patch("app.main.get_photo_id_for_face", return_value="test-photo")
    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.get_identity_for_face", return_value=None)
    def test_lightbox_prev_uses_data_action(self, mock_ident, mock_dim, mock_meta,
                                             mock_face_photo, mock_reg):
        """Lightbox prev button uses data-action, not per-swap keyboard script."""
        from app.main import to_xml
        from starlette.testclient import TestClient
        from app.main import app

        identity_id = "test-identity"
        mock_reg.return_value = MagicMock()
        mock_reg.return_value.get_identity.return_value = {
            "identity_id": identity_id,
            "name": "Test Person",
            "anchor_ids": ["face1", "face2", "face3"],
            "candidate_ids": [],
        }
        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
        }

        client = TestClient(app)
        response = client.get(f"/api/identity/{identity_id}/photos?index=1")
        html = response.text

        # Lightbox prev button should use data-action
        assert 'data-action="lightbox-prev"' in html

    @patch("app.main.load_registry")
    @patch("app.main.get_photo_id_for_face", return_value="test-photo")
    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.get_identity_for_face", return_value=None)
    def test_lightbox_next_uses_data_action(self, mock_ident, mock_dim, mock_meta,
                                             mock_face_photo, mock_reg):
        """Lightbox next button uses data-action, not per-swap keyboard script."""
        from app.main import to_xml
        from starlette.testclient import TestClient
        from app.main import app

        identity_id = "test-identity"
        mock_reg.return_value = MagicMock()
        mock_reg.return_value.get_identity.return_value = {
            "identity_id": identity_id,
            "name": "Test Person",
            "anchor_ids": ["face1", "face2"],
            "candidate_ids": [],
        }
        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
        }

        client = TestClient(app)
        # index=0 should have a next button (not at last)
        response = client.get(f"/api/identity/{identity_id}/photos?index=0")
        html = response.text

        assert 'data-action="lightbox-next"' in html

    @patch("app.main.load_registry")
    @patch("app.main.get_photo_id_for_face", return_value="test-photo")
    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.get_identity_for_face", return_value=None)
    def test_lightbox_no_per_swap_keyboard_rebind(self, mock_ident, mock_dim, mock_meta,
                                                    mock_face_photo, mock_reg):
        """Lightbox must NOT rebind keyboard listeners per HTMX swap."""
        from starlette.testclient import TestClient
        from app.main import app

        identity_id = "test-identity"
        mock_reg.return_value = MagicMock()
        mock_reg.return_value.get_identity.return_value = {
            "identity_id": identity_id,
            "name": "Test Person",
            "anchor_ids": ["face1", "face2"],
            "candidate_ids": [],
        }
        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
        }

        client = TestClient(app)
        response = client.get(f"/api/identity/{identity_id}/photos?index=0")
        html = response.text

        # Must NOT have per-swap pattern
        assert "removeEventListener('keydown',window._lbKb)" not in html
        assert "window._lbKb=kh" not in html


# ---------------------------------------------------------------------------
# Photo modal close button
# ---------------------------------------------------------------------------

class TestModalCloseButton:
    """Close button must render correctly."""

    def test_photo_modal_close_button(self):
        """Photo modal has a close button."""
        from app.main import photo_modal, to_xml
        html = to_xml(photo_modal())

        assert 'aria-label="Close modal"' in html
        assert "photo-modal" in html

    def test_lightbox_close_button(self):
        """Photo lightbox has a close button."""
        from app.main import photo_lightbox, to_xml
        html = to_xml(photo_lightbox())

        assert 'aria-label="Close lightbox"' in html
        assert "photo-lightbox" in html


# ---------------------------------------------------------------------------
# Lightbox HTMX buttons carry navigation URLs as data attributes
# ---------------------------------------------------------------------------

class TestLightboxButtonNavData:
    """Lightbox buttons must carry hx-get URLs as data attributes for delegation."""

    @patch("app.main.load_registry")
    @patch("app.main.get_photo_id_for_face", return_value="test-photo")
    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.get_identity_for_face", return_value=None)
    def test_lightbox_prev_has_hx_get(self, mock_ident, mock_dim, mock_meta,
                                       mock_face_photo, mock_reg):
        """Lightbox prev button has hx-get for HTMX navigation."""
        from starlette.testclient import TestClient
        from app.main import app

        identity_id = "test-identity"
        mock_reg.return_value = MagicMock()
        mock_reg.return_value.get_identity.return_value = {
            "identity_id": identity_id,
            "name": "Test Person",
            "anchor_ids": ["face1", "face2", "face3"],
            "candidate_ids": [],
        }
        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
        }

        client = TestClient(app)
        response = client.get(f"/api/identity/{identity_id}/photos?index=1")
        html = response.text

        # Prev button should navigate to index 0
        assert f"/api/identity/{identity_id}/photos?index=0" in html

    @patch("app.main.load_registry")
    @patch("app.main.get_photo_id_for_face", return_value="test-photo")
    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.get_identity_for_face", return_value=None)
    def test_lightbox_next_has_hx_get(self, mock_ident, mock_dim, mock_meta,
                                       mock_face_photo, mock_reg):
        """Lightbox next button has hx-get for HTMX navigation."""
        from starlette.testclient import TestClient
        from app.main import app

        identity_id = "test-identity"
        mock_reg.return_value = MagicMock()
        mock_reg.return_value.get_identity.return_value = {
            "identity_id": identity_id,
            "name": "Test Person",
            "anchor_ids": ["face1", "face2", "face3"],
            "candidate_ids": [],
        }
        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
        }

        client = TestClient(app)
        response = client.get(f"/api/identity/{identity_id}/photos?index=1")
        html = response.text

        # Next button should navigate to index 2
        assert f"/api/identity/{identity_id}/photos?index=2" in html
