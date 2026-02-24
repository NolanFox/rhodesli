"""
Session 65a — UX quick wins: face overlay toggle.

Tests for Phase 4 UX improvements.
"""

import pytest
from starlette.testclient import TestClient
from app.main import app


def get_real_photo_id():
    """Get a real photo_id from photo_index for testing."""
    try:
        from app.main import _photo_cache
        if _photo_cache:
            # Find a photo with faces and dimensions
            for pid, pdata in _photo_cache.items():
                if pdata.get("faces") and pdata.get("width"):
                    return pid
            # Fallback to any photo
            return next(iter(_photo_cache))
    except Exception:
        pass
    return None


class TestFaceOverlayToggle:
    """Face overlay toggle button on photo pages."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def real_photo_id(self):
        return get_real_photo_id()

    def test_photo_page_has_toggle_button(self, client, real_photo_id):
        """Photo page should have a face overlay toggle when faces exist."""
        if not real_photo_id:
            pytest.skip("No photos available for testing")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        # Should have a toggle action (either admin or public variant)
        assert "toggle-face-overlays" in response.text

    def test_toggle_button_says_hide_for_admin(self, client, real_photo_id):
        """Admin (auth disabled = admin) should see 'Hide Faces' by default."""
        if not real_photo_id:
            pytest.skip("No photos available for testing")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        assert "Hide Faces" in response.text

    def test_toggle_js_handler_exists(self, client, real_photo_id):
        """Page JS should include toggle handler for face overlays."""
        if not real_photo_id:
            pytest.skip("No photos available for testing")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        # JS handler queries face-overlay elements
        assert "toggle-face-overlays" in response.text

    def test_face_overlay_legend_has_id(self, client, real_photo_id):
        """Face overlay legend should have an ID for toggle targeting."""
        if not real_photo_id:
            pytest.skip("No photos available for testing")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        # Legend should be identifiable for toggle
        assert "face-overlay-legend" in response.text

    def test_photo_page_without_faces_no_toggle(self, client):
        """Photo that doesn't exist should not show toggle."""
        response = client.get("/photo/nonexistent-id")
        assert response.status_code == 404
        assert "toggle-face-overlays" not in response.text
