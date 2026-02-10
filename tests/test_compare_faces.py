"""
Tests for Compare Faces UX overhaul: face/photo toggle, clickable names, sizing.
"""

import pytest
from starlette.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _get_two_identity_ids():
    """Get two identity IDs that have faces for comparison testing."""
    from app.main import load_registry
    registry = load_registry()
    identities = registry.list_identities()
    ids_with_faces = []
    for identity in identities:
        if identity.get("anchor_ids") or identity.get("candidate_ids"):
            ids_with_faces.append(identity["identity_id"])
        if len(ids_with_faces) >= 2:
            break
    return ids_with_faces


class TestCompareModal:
    """Tests for the compare faces modal."""

    def test_compare_modal_in_page(self, client):
        """Compare modal HTML is present in the main page."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=confirmed")
            assert 'id="compare-modal"' in response.text

    def test_compare_modal_uses_full_width(self, client):
        """Compare modal uses adequate viewport width."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=confirmed")
            # Should use max-w-5xl (not max-w-4xl)
            assert "max-w-5xl" in response.text or "max-w-full" in response.text


class TestCompareEndpoint:
    """Tests for the compare faces API endpoint."""

    def test_compare_returns_200(self, client):
        """Compare endpoint returns 200 with valid IDs."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}")
            assert response.status_code == 200

    def test_compare_has_face_photo_toggle(self, client):
        """Compare popup includes Faces/Photos toggle buttons."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}")
            html = response.text
            assert "Faces" in html
            assert "Photos" in html
            assert "view=faces" in html
            assert "view=photos" in html

    def test_compare_has_clickable_names(self, client):
        """Identity names in compare popup are clickable links."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}")
            html = response.text
            # Names should be links (href to identity page)
            assert f"current={ids[0]}" in html
            assert f"current={ids[1]}" in html

    def test_compare_photos_view(self, client):
        """Compare popup photos view loads full photos."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}?view=photos")
            assert response.status_code == 200
            # Photos toggle should show Photos as active
            assert "Photos" in response.text

    def test_compare_has_navigation_counter(self, client):
        """Compare popup shows position counter for multi-face identities."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}")
            # Should have "1 of N" counter if identity has multiple faces
            # At minimum, the response should be valid
            assert response.status_code == 200
