"""Tests for FE-004: Consistent lightbox component across sections.

There must be exactly ONE modal system (#photo-modal) for displaying photos.
The old #photo-lightbox must be removed. All photo viewing — whether triggered
by clicking a face or by "View All Photos" — routes through #photo-modal.
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Page layout: only #photo-modal exists, NOT #photo-lightbox
# ---------------------------------------------------------------------------

class TestSingleModalInPage:
    """The page must contain only ONE photo modal (#photo-modal)."""

    def test_page_has_photo_modal(self, client):
        """The page layout includes #photo-modal."""
        response = client.get("/?section=to_review")
        html = response.text
        assert 'id="photo-modal"' in html

    def test_page_has_photo_modal_content(self, client):
        """The page layout includes #photo-modal-content container."""
        response = client.get("/?section=to_review")
        html = response.text
        assert 'id="photo-modal-content"' in html

    def test_page_does_not_have_photo_lightbox(self, client):
        """The old #photo-lightbox must be removed from the page layout."""
        response = client.get("/?section=to_review")
        html = response.text
        assert 'id="photo-lightbox"' not in html

    def test_page_does_not_have_lightbox_content(self, client):
        """The old #lightbox-content container must be removed."""
        response = client.get("/?section=to_review")
        html = response.text
        assert 'id="lightbox-content"' not in html


# ---------------------------------------------------------------------------
# "View All Photos" button targets #photo-modal, not #photo-lightbox
# ---------------------------------------------------------------------------

class TestViewAllPhotosButton:
    """The View All Photos button on identity cards must target #photo-modal."""

    def test_view_all_photos_targets_photo_modal_content(self):
        """View All Photos button's hx-target is #photo-modal-content."""
        from app.main import identity_card, to_xml

        identity = {
            "identity_id": "test-id-1",
            "name": "Test Person",
            "state": "CONFIRMED",
            "anchor_ids": ["face1"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
        }
        crop_files = set()
        html = to_xml(identity_card(identity, crop_files, is_admin=True))

        # Must target the unified modal
        assert '#photo-modal-content' in html
        # Must NOT target the old lightbox
        assert '#lightbox-content' not in html

    def test_view_all_photos_opens_photo_modal(self):
        """View All Photos button shows #photo-modal (not #photo-lightbox)."""
        from app.main import identity_card, to_xml

        identity = {
            "identity_id": "test-id-1",
            "name": "Test Person",
            "state": "CONFIRMED",
            "anchor_ids": ["face1"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
        }
        crop_files = set()
        html = to_xml(identity_card(identity, crop_files, is_admin=True))

        # The hyperscript should show #photo-modal
        assert '#photo-modal' in html
        # Must NOT reference #photo-lightbox
        assert '#photo-lightbox' not in html


# ---------------------------------------------------------------------------
# Identity photos endpoint returns content compatible with #photo-modal
# ---------------------------------------------------------------------------

class TestIdentityPhotosEndpointTargetsModal:
    """The /api/identity/{id}/photos endpoint content must target #photo-modal."""

    @patch("app.main.load_registry")
    @patch("app.main.get_photo_id_for_face", return_value="test-photo")
    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.get_identity_for_face", return_value=None)
    def test_lightbox_nav_targets_photo_modal_content(self, mock_ident, mock_dim,
                                                        mock_meta, mock_face_photo,
                                                        mock_reg):
        """Prev/next buttons in identity photos target #photo-modal-content."""
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

        # Nav buttons must target #photo-modal-content
        assert '#photo-modal-content' in html
        # Must NOT reference #lightbox-content
        assert '#lightbox-content' not in html

    @patch("app.main.load_registry")
    @patch("app.main.get_photo_id_for_face", return_value="test-photo")
    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.get_identity_for_face", return_value=None)
    def test_lightbox_touch_swipe_targets_photo_modal_content(self, mock_ident,
                                                                mock_dim, mock_meta,
                                                                mock_face_photo,
                                                                mock_reg):
        """Touch swipe JS in identity photos targets #photo-modal-content."""
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

        # Touch swipe target must be #photo-modal-content
        assert '#photo-modal-content' in html
        assert '#lightbox-content' not in html


# ---------------------------------------------------------------------------
# Global event delegation uses only #photo-modal (no #photo-lightbox)
# ---------------------------------------------------------------------------

class TestGlobalDelegationUnified:
    """Global JS event delegation must reference only #photo-modal."""

    def test_no_photo_lightbox_in_global_script(self, client):
        """Global event delegation script does not reference photo-lightbox."""
        response = client.get("/?section=to_review")
        html = response.text

        # The global script should NOT reference the old lightbox
        assert "getElementById('photo-lightbox')" not in html

    def test_keyboard_escape_targets_photo_modal(self, client):
        """Keyboard Escape handler targets #photo-modal."""
        response = client.get("/?section=to_review")
        html = response.text

        assert "getElementById('photo-modal')" in html


# ---------------------------------------------------------------------------
# photo_lightbox() function must not exist
# ---------------------------------------------------------------------------

class TestPhotoLightboxRemoved:
    """The photo_lightbox() function should no longer be exported."""

    def test_photo_lightbox_function_removed(self):
        """photo_lightbox() should not exist as a public function."""
        import app.main as m
        assert not hasattr(m, 'photo_lightbox'), \
            "photo_lightbox() function should be removed — use photo_modal() only"
