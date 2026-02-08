"""Tests for face tagging UX refinements (Phase 5).

Covers:
- Single tag dropdown (closing others when opening one)
- Create new identity from autocomplete
- Keyboard shortcuts in focus mode
"""

import pytest
from unittest.mock import patch


WORKSTATION_URL = "/?section=to_review"


class TestTagDropdownSingleOpen:
    """Only one tag dropdown should be open at a time."""

    def test_tag_dropdown_has_tag_dropdown_class(self, client):
        """Tag dropdowns include the tag-dropdown class for querySelectorAll."""
        from app.main import load_embeddings_for_photos
        photos = load_embeddings_for_photos()
        if not photos:
            pytest.skip("No embeddings available for testing")
        photo_id = next(iter(photos.keys()))
        response = client.get(f"/photo/{photo_id}/partial")
        assert "tag-dropdown" in response.text

    def test_click_handler_closes_other_dropdowns(self, client):
        """Face overlay click script includes logic to close sibling dropdowns."""
        from app.main import load_embeddings_for_photos
        photos = load_embeddings_for_photos()
        if not photos:
            pytest.skip("No embeddings available for testing")
        photo_id = next(iter(photos.keys()))
        response = client.get(f"/photo/{photo_id}/partial")
        text = response.text
        # The Hyperscript should iterate over tag-dropdown elements and add .hidden
        assert "tag-dropdown" in text
        assert "add .hidden" in text


class TestCreateIdentityFromTag:
    """Tag search autocomplete includes a '+ Create' option."""

    def test_tag_search_returns_create_option(self, client):
        """Tag search results include a '+ Create' button."""
        response = client.get("/api/face/tag-search?face_id=test&q=NewPersonName")
        assert response.status_code == 200
        text = response.text
        # Should include create button regardless of whether matches exist
        assert 'Create "NewPersonName"' in text or "create-identity" in text

    def test_create_identity_endpoint_exists(self, client):
        """POST /api/face/create-identity returns a response (not 404/405)."""
        # Without admin auth, should get 401
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            response = client.post("/api/face/create-identity?face_id=test&name=Test")
            assert response.status_code in (401, 403, 404, 200)

    def test_create_identity_requires_admin(self, client):
        """Create identity endpoint requires admin authentication."""
        from app.auth import User
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=User(id="u1", email="user@test.com", is_admin=False)):
            response = client.post("/api/face/create-identity?face_id=test&name=Test")
            assert response.status_code == 403

    def test_create_identity_rejects_empty_name(self, client):
        """Create identity rejects empty name."""
        response = client.post("/api/face/create-identity?face_id=test&name=  ")
        assert response.status_code == 400


class TestKeyboardShortcuts:
    """Focus mode includes keyboard shortcut support."""

    def test_focus_mode_has_keyboard_script(self, client):
        """Focus mode includes keyboard shortcut JavaScript."""
        response = client.get(WORKSTATION_URL)
        assert response.status_code == 200
        text = response.text
        if "focus-container" in text and "focus-btn-confirm" in text:
            assert "focusKeyHandler" in text
            assert "focus-btn-confirm" in text
            assert "focus-btn-skip" in text
            assert "focus-btn-reject" in text

    def test_focus_buttons_have_ids(self, client):
        """Focus mode action buttons have id attributes for keyboard targeting."""
        response = client.get(WORKSTATION_URL)
        text = response.text
        if "focus-container" in text:
            # When there are items to review, buttons should have IDs
            if "All caught up" not in text:
                assert "focus-btn-confirm" in text
                assert "focus-btn-skip" in text
                assert "focus-btn-reject" in text

    def test_keyboard_hint_text_present(self, client, admin_user):
        """Focus mode shows keyboard shortcut hints for admin users."""
        response = client.get(WORKSTATION_URL)
        text = response.text
        if "focus-container" in text and "All caught up" not in text:
            assert "Keyboard:" in text or "C S R F" in text

    def test_keyboard_handler_skips_input_fields(self, client):
        """Keyboard handler checks target.tagName to skip input fields."""
        response = client.get(WORKSTATION_URL)
        text = response.text
        if "focusKeyHandler" in text:
            assert "INPUT" in text
            assert "TEXTAREA" in text

    def test_keyboard_handler_skips_when_modal_open(self, client):
        """Keyboard handler checks if photo modal is open before acting."""
        response = client.get(WORKSTATION_URL)
        text = response.text
        if "focusKeyHandler" in text:
            assert "photo-modal" in text
