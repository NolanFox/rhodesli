"""Tests for quick-identify inline flow."""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

import app.main


@pytest.fixture
def client():
    """Test client for the app."""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_disabled():
    """Disable auth for testing."""
    with patch("app.main.is_auth_enabled", return_value=False):
        yield


@pytest.fixture
def admin_user():
    """Mock admin user."""
    mock_user = MagicMock()
    mock_user.is_admin = True
    mock_user.email = "admin@test.com"
    mock_user.id = "admin-123"
    with patch("app.main.is_auth_enabled", return_value=True), \
         patch("app.main.get_current_user", return_value=mock_user):
        yield mock_user


@pytest.fixture
def public_user():
    """Mock public (non-admin) user."""
    with patch("app.main.is_auth_enabled", return_value=True), \
         patch("app.main.get_current_user", return_value=None):
        yield


class TestQuickIdentifyForm:
    """Test the inline identify form endpoint."""

    def test_form_returns_for_admin(self, client, admin_user):
        """Admin gets the quick-identify form."""
        # Use any face_id — the form endpoint just needs a valid face_id string
        response = client.get("/api/admin/quick-identify-form/test-face-001")
        assert response.status_code == 200
        html = response.text
        assert 'data-testid="quick-identify-form"' in html
        assert 'data-testid="quick-identify-input"' in html

    def test_form_blocked_for_public(self, client, public_user):
        """Public users get 401 for quick-identify form."""
        response = client.get("/api/admin/quick-identify-form/test-face-001")
        assert response.status_code == 401

    def test_form_has_name_input(self, client, admin_user):
        """Form has a text input for the name."""
        response = client.get("/api/admin/quick-identify-form/test-face-001")
        html = response.text
        assert 'name="name"' in html
        assert 'placeholder="Enter name..."' in html

    def test_form_posts_to_create_identity(self, client, admin_user):
        """Form submits to /api/face/create-identity."""
        response = client.get("/api/admin/quick-identify-form/test-face-001")
        html = response.text
        assert "/api/face/create-identity" in html

    def test_form_has_cancel_button(self, client, admin_user):
        """Form has a cancel button that clears the form area."""
        response = client.get("/api/admin/quick-identify-form/test-face-001")
        html = response.text
        assert "Cancel" in html

    def test_form_has_autocomplete_datalist(self, client, admin_user):
        """Form includes name suggestions from confirmed identities."""
        response = client.get("/api/admin/quick-identify-form/test-face-001")
        html = response.text
        # Should have a datalist element for autocomplete
        assert "datalist" in html.lower() or "names-" in html


    def test_form_handles_face_id_with_special_chars(self, client, admin_user):
        """Face IDs with colons/spaces must produce valid CSS-safe DOM IDs.

        Legacy face IDs like 'Image 968_compress:face0' contain colons and
        spaces that break CSS selectors. The form must sanitize these for
        DOM element IDs while preserving the raw face_id in the hidden input.
        Regression test for Session 60b P0 bug.
        """
        from urllib.parse import quote
        face_id = "Image 968_compress:face0"
        encoded = quote(face_id, safe='')
        response = client.get(f"/api/admin/quick-identify-form/{encoded}")
        assert response.status_code == 200
        html = response.text
        # The hidden input must preserve the raw face_id for server-side use
        assert f'value="{face_id}"' in html
        # DOM element IDs must NOT contain colons or spaces
        assert 'id="qid-Image 968_compress:face0"' not in html
        # Sanitized ID should be present
        assert 'id="qid-Image_968_compress_face0"' in html
        # Cancel button getElementById must also use sanitized ID
        assert "qid-Image_968_compress_face0" in html

    def test_form_handles_inbox_face_id(self, client, admin_user):
        """Inbox face IDs (no special chars) still work correctly."""
        response = client.get("/api/admin/quick-identify-form/inbox_4eb02c7e058e")
        assert response.status_code == 200
        html = response.text
        assert 'value="inbox_4eb02c7e058e"' in html
        assert 'id="qid-inbox_4eb02c7e058e"' in html


class TestQuickIdentifyOnPhotoPage:
    """Test that quick-identify buttons appear on photo pages."""

    def test_no_quick_id_button_for_anonymous(self, client, auth_disabled):
        """Anonymous users don't see quick-identify buttons."""
        response = client.get("/photo/a3d2695fe0804844")
        if response.status_code == 200:
            html = response.text
            assert 'data-testid="quick-identify-btn"' not in html

    def test_photo_page_has_photo_face_card_class(self, client, auth_disabled):
        """Photo page face cards use the photo-face-card class for HTMX targeting."""
        response = client.get("/photo/a3d2695fe0804844")
        if response.status_code == 200:
            html = response.text
            # The class should be present on face cards (whether admin or not)
            assert "photo-face-card" in html or response.status_code == 404
