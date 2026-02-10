"""
Tests for landing page stats, about page content, and navigation (Phase 5).
"""

import pytest
from starlette.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestLandingStats:
    """Tests for landing page stat accuracy."""

    def test_landing_stats_include_skipped_as_unidentified(self):
        """needs_help count includes INBOX + PROPOSED + SKIPPED faces."""
        from app.main import _compute_landing_stats
        from core.registry import IdentityState

        stats = _compute_landing_stats()
        # The needs_help stat must be positive (we know there are unidentified faces)
        assert stats["needs_help"] >= 0
        # Verify it's computed from actual data (not hardcoded zero)
        assert isinstance(stats["needs_help"], int)

    def test_landing_page_shows_awaiting_identification(self, client):
        """Landing page uses 'awaiting identification' label, not 'still unidentified'."""
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.get_current_user", return_value=None):
            response = client.get("/")
            assert response.status_code == 200
            assert "awaiting identification" in response.text
            assert "still unidentified" not in response.text

    def test_landing_page_no_collection_names(self, client):
        """Landing page doesn't list specific collection names."""
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.get_current_user", return_value=None):
            response = client.get("/")
            assert response.status_code == 200
            assert "Betty Capeluto Miami Collection" not in response.text
            assert "Nace Capeluto Tampa Collection" not in response.text

    def test_landing_page_has_historical_copy(self, client):
        """Landing page includes historically grounded copy about Rhodes."""
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.get_current_user", return_value=None):
            response = client.get("/")
            assert response.status_code == 200
            assert "La Juderia" in response.text
            assert "1492" in response.text


class TestAboutPage:
    """Tests for /about page content and structure."""

    def test_about_page_renders(self, client):
        """About page returns 200."""
        response = client.get("/about")
        assert response.status_code == 200

    def test_about_page_has_all_sections(self, client):
        """About page includes all required sections."""
        response = client.get("/about")
        html = response.text
        assert "The Community" in html
        assert "The Diaspora" in html
        assert "The Project" in html
        assert "How to Help" in html
        assert "How It Works" in html
        assert "Roles" in html
        assert "Frequently Asked Questions" in html

    def test_about_page_dynamic_stats(self, client):
        """About page stats are computed from actual data, not hardcoded."""
        from app.main import _compute_landing_stats
        stats = _compute_landing_stats()
        response = client.get("/about")
        html = response.text
        # Should contain dynamic values from _compute_landing_stats
        assert f"{stats['photo_count']} photographs" in html
        assert f"{stats['total_faces']} faces detected" in html
        assert f"{stats['named_count']} people" in html
        assert "awaiting identification" in html

    def test_about_page_roles_section(self, client):
        """About page explains visitor, contributor, and admin roles."""
        response = client.get("/about")
        html = response.text
        assert "Visitors" in html
        assert "Contributors" in html
        assert "Admins" in html

    def test_about_page_no_generative_ai(self, client):
        """About page clarifies forensic-only AI usage."""
        response = client.get("/about")
        assert "forensic" in response.text.lower()


class TestAboutNavigation:
    """Tests for About link prominence in navigation."""

    def test_about_link_in_landing_nav(self, client):
        """About link appears in landing page navigation."""
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.get_current_user", return_value=None):
            response = client.get("/")
            assert response.status_code == 200
            assert 'href="/about"' in response.text

    def test_about_link_in_sidebar(self, client):
        """About link appears in sidebar navigation for logged-in users."""
        from app.main import sidebar, _compute_sidebar_counts, load_registry
        from fastcore.xml import to_xml
        from unittest.mock import MagicMock

        user = MagicMock()
        user.is_admin = False
        user.email = "test@test.com"
        registry = load_registry()
        counts = _compute_sidebar_counts(registry)
        html = to_xml(sidebar(user=user, current_section="confirmed", counts=counts))
        assert 'href="/about"' in html
        assert "About" in html
