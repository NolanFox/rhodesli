"""
Session 82e — UX Feature Sprint tests.

Tests for: Help page, identify mode, landing help section.
Pruned: CSS class assertions (masonry, hamburger breakpoints, animations).
"""

import pytest
from unittest.mock import patch
from starlette.testclient import TestClient
from app.main import app, _public_nav_links


def get_real_photo_id():
    """Get a real photo_id from photo_index for testing."""
    try:
        from app.main import _photo_cache

        if _photo_cache:
            for pid, pdata in _photo_cache.items():
                if pdata.get("faces") and pdata.get("width"):
                    return pid
            return next(iter(_photo_cache))
    except Exception:
        pass
    return None


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def real_photo_id():
    return get_real_photo_id()


class TestHelpNeededPage:
    """Phase 3A: Help Needed page with unidentified faces."""

    def test_help_page_returns_200(self, client):
        """/help should be a public route that returns 200."""
        response = client.get("/help")
        assert response.status_code == 200

    def test_help_in_navigation(self):
        """Navigation should include Help Identify link to /help."""
        with patch("app.main.is_auth_enabled", return_value=False):
            links = _public_nav_links(active="")
            hrefs = [link.attrs.get("href", "") for link in links]
            assert "/help" in hrefs


class TestIdentifyModeFocusState:
    """Phase 4: Identify Mode focus state on photo pages."""

    def test_identify_mode_toggle_on_photo_page(self, client, real_photo_id):
        """Photo page with faces should have Identify Mode toggle."""
        if not real_photo_id:
            pytest.skip("No photos available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        assert "identify-mode-toggle" in response.text

    def test_404_page_no_identify_mode(self, client):
        """Non-existent photo should not show identify mode toggle."""
        response = client.get("/photo/nonexistent-id-xyz")
        assert response.status_code == 404
        assert "identify-mode-toggle" not in response.text


class TestLandingPageHelpSection:
    """Phase 3C: Landing page Help Us Identify section."""

    def test_landing_page_has_help_section(self, client):
        """Landing page should have Help Identify section."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Help" in response.text and "Identify" in response.text

    def test_landing_page_links_to_help(self, client):
        """Landing page should link to /help."""
        response = client.get("/")
        assert response.status_code == 200
        assert "/help" in response.text
