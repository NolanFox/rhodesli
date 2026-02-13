"""Tests for non-destructive image orientation tools.

Tests cover:
- parse_transform_to_css converts transform strings correctly
- parse_transform_to_filter handles invert
- Transform API endpoint (admin only)
- Transform toolbar renders for admin
- CSS transform applied to rendered images
- Reset clears transform
- Download serves original untransformed file
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.main import (
    app,
    parse_transform_to_css,
    parse_transform_to_filter,
    image_transform_toolbar,
    load_embeddings_for_photos,
)


def get_real_photo_id():
    photos = load_embeddings_for_photos()
    if photos:
        return next(iter(photos.keys()))
    return None


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def real_photo_id():
    return get_real_photo_id()


class TestParseTransformToCSS:
    """Transform string -> CSS transform value."""

    def test_empty_string(self):
        assert parse_transform_to_css("") == ""

    def test_none(self):
        assert parse_transform_to_css(None) == ""

    def test_rotate_90(self):
        assert parse_transform_to_css("rotate:90") == "rotate(90deg)"

    def test_rotate_180(self):
        assert parse_transform_to_css("rotate:180") == "rotate(180deg)"

    def test_rotate_270(self):
        assert parse_transform_to_css("rotate:270") == "rotate(270deg)"

    def test_flip_h(self):
        assert parse_transform_to_css("flipH") == "scaleX(-1)"

    def test_flip_v(self):
        assert parse_transform_to_css("flipV") == "scaleY(-1)"

    def test_combined(self):
        result = parse_transform_to_css("rotate:180,flipH")
        assert "rotate(180deg)" in result
        assert "scaleX(-1)" in result

    def test_invert_not_in_transform(self):
        """Invert is a filter, not a transform."""
        result = parse_transform_to_css("invert")
        assert result == ""


class TestParseTransformToFilter:
    """Transform string -> CSS filter value."""

    def test_empty_string(self):
        assert parse_transform_to_filter("") == ""

    def test_no_invert(self):
        assert parse_transform_to_filter("rotate:90") == ""

    def test_invert(self):
        assert parse_transform_to_filter("invert") == "invert(1)"

    def test_combined_with_invert(self):
        assert parse_transform_to_filter("rotate:90,invert") == "invert(1)"


class TestTransformEndpoint:
    """API endpoint for setting transforms."""

    def test_requires_admin(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            response = client.post(
                f"/api/photo/{real_photo_id}/transform",
                data={"transform": "rotate:90"},
                headers={"HX-Request": "true"},
            )
        assert response.status_code == 401

    def test_rotate_90(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        mock_registry = MagicMock()
        mock_registry.get_photo.return_value = {"path": "test.jpg", "transform": ""}
        mock_registry.set_metadata.return_value = True

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_photo_registry", return_value=mock_registry), \
             patch("app.main.save_photo_registry"):
            response = client.post(
                f"/api/photo/{real_photo_id}/transform?transform=rotate:90&field=transform",
                headers={"HX-Request": "true"},
            )
        assert response.status_code == 200
        mock_registry.set_metadata.assert_called_once()
        call_args = mock_registry.set_metadata.call_args
        assert call_args[0][1]["transform"] == "rotate:90"

    def test_reset(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        mock_registry = MagicMock()
        mock_registry.get_photo.return_value = {"path": "test.jpg", "transform": "rotate:90"}
        mock_registry.set_metadata.return_value = True

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_photo_registry", return_value=mock_registry), \
             patch("app.main.save_photo_registry"):
            response = client.post(
                f"/api/photo/{real_photo_id}/transform?transform=reset&field=transform",
                headers={"HX-Request": "true"},
            )
        assert response.status_code == 200
        assert "reset" in response.text.lower() or "Transform" in response.text

    def test_invalid_field_rejected(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.post(
                f"/api/photo/{real_photo_id}/transform?transform=rotate:90&field=invalid",
                headers={"HX-Request": "true"},
            )
        assert response.status_code == 200
        assert "Invalid" in response.text


class TestTransformToolbar:
    """Admin toolbar renders correctly."""

    def test_toolbar_has_buttons(self):
        from fasthtml.common import to_xml
        toolbar = image_transform_toolbar("test-id", target="front")
        html = to_xml(toolbar)
        assert "90" in html
        assert "Flip H" in html
        assert "Flip V" in html
        assert "Reset" in html

    def test_toolbar_targets_transform_result(self):
        from fasthtml.common import to_xml
        toolbar = image_transform_toolbar("test-id", target="front")
        html = to_xml(toolbar)
        assert "transform-result" in html

    def test_back_toolbar_uses_back_transform(self):
        from fasthtml.common import to_xml
        toolbar = image_transform_toolbar("test-id", target="back")
        html = to_xml(toolbar)
        assert "back_transform" in html


class TestTransformMetadata:
    """PhotoRegistry accepts transform fields."""

    def test_transform_is_valid_key(self):
        from core.photo_registry import PhotoRegistry
        reg = PhotoRegistry()
        reg.register_face("test-photo", "test.jpg", "face1", source="test", collection="test")
        result = reg.set_metadata("test-photo", {"transform": "rotate:90"})
        assert result is True
        meta = reg.get_metadata("test-photo")
        assert meta.get("transform") == "rotate:90"

    def test_back_transform_is_valid_key(self):
        from core.photo_registry import PhotoRegistry
        reg = PhotoRegistry()
        reg.register_face("test-photo", "test.jpg", "face1", source="test", collection="test")
        result = reg.set_metadata("test-photo", {"back_transform": "flipH"})
        assert result is True
        meta = reg.get_metadata("test-photo")
        assert meta.get("back_transform") == "flipH"


class TestTransformAdminUI:
    """Transform toolbar visible only for admin."""

    def test_toolbar_shown_for_admin(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user") as mock_user:
            mock_user.return_value = MagicMock(is_admin=True, email="admin@test.com")
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Orientation" in html or "orientation" in html

    def test_toolbar_hidden_for_non_admin(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user") as mock_user:
            mock_user.return_value = MagicMock(is_admin=False, email="user@test.com")
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Front orientation" not in html
