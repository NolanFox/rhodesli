"""
Tests for bulk photo select mode and collection management.
"""

import json
import pytest
from starlette.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestPhotoSelectMode:
    """Photo grid should have a Select toggle and checkboxes."""

    def test_select_toggle_present(self, client):
        """Photo grid has a Select toggle button."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=photos")
            assert response.status_code == 200
            assert 'data-action="toggle-photo-select"' in response.text

    def test_photo_checkboxes_present(self, client):
        """Photo cards have checkbox elements (hidden by default)."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=photos")
            assert response.status_code == 200
            assert "photo-select-checkbox" in response.text

    def test_bulk_action_bar_present(self, client):
        """Bulk action bar is present (hidden by default)."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=photos")
            assert response.status_code == 200
            assert 'id="photo-bulk-bar"' in response.text

    def test_select_all_button_present(self, client):
        """Select All button is in the bulk action bar."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=photos")
            assert response.status_code == 200
            assert 'data-action="photo-select-all"' in response.text

    def test_bulk_move_button_present(self, client):
        """Move button is in the bulk action bar."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=photos")
            assert response.status_code == 200
            assert 'data-action="photo-bulk-move"' in response.text

    def test_select_mode_script_present(self, client):
        """JavaScript for select mode is included."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=photos")
            assert response.status_code == 200
            assert "updateSelectCount" in response.text


class TestBulkUpdateSource:
    """Tests for POST /api/photos/bulk-update-source endpoint."""

    def test_requires_admin(self, client):
        """Bulk update requires admin."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            response = client.post(
                "/api/photos/bulk-update-source",
                data={"photo_ids": "[]", "source": "Test"},
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 401

    def test_requires_at_least_one_field(self, client):
        """Empty collection/source/source_url returns warning."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.post(
                "/api/photos/bulk-update-source",
                data={"photo_ids": '["id1"]', "collection": "", "source": "", "source_url": ""},
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 200
            assert "provide collection" in response.text.lower()

    def test_requires_photo_ids(self, client):
        """Empty photo_ids returns warning."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.post(
                "/api/photos/bulk-update-source",
                data={"photo_ids": "[]", "source": "Test Collection"},
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 200
            assert "No photos" in response.text

    def test_updates_source_successfully(self, client):
        """Valid request updates photo sources."""
        # Get a real photo ID from the registry
        from app.main import load_photo_registry
        photo_registry = load_photo_registry()
        photo_ids = list(photo_registry._photos.keys())[:2]
        if not photo_ids:
            pytest.skip("No photos available")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.post(
                "/api/photos/bulk-update-source",
                data={"photo_ids": json.dumps(photo_ids), "source": "Test Collection"},
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 200
            assert "Updated" in response.text

    def test_invalid_json_returns_error(self, client):
        """Invalid JSON for photo_ids returns error."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.post(
                "/api/photos/bulk-update-source",
                data={"photo_ids": "not-json", "source": "Test"},
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 200
            assert "Invalid" in response.text


class TestUploadCollectionAutocomplete:
    """Upload page should have collection autocomplete."""

    def test_upload_has_source_field(self, client):
        """Upload page has source/collection input field."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/upload")
            assert response.status_code == 200
            assert 'name="source"' in response.text

    def test_upload_has_datalist_suggestions(self, client):
        """Upload page has datalist with existing collections."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/upload")
            assert response.status_code == 200
            assert 'id="source-suggestions"' in response.text
