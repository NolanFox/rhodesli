"""Tests for enhanced community landing page empty states (PRD-036)."""

import app.main  # noqa: F401 — must import first to avoid circular import

from unittest.mock import patch


class TestCommunityLandingEmptyStates:
    """Tests for the enhanced empty state on community landing pages."""

    def _render(self, community, slug):
        """Helper to render _community_landing_page with mocked data loaders."""
        from app.page_routes import _community_landing_page

        with patch("app.supabase_data.load_photos_for_community", return_value=[]):
            with patch("app.supabase_data.load_identities_for_community", return_value=[]):
                return _community_landing_page(community, slug)

    def test_empty_community_renders(self):
        """Community landing page renders for empty community."""
        community = {
            "id": "test-id",
            "slug": "test-archive",
            "name": "Test Archive",
        }
        result = self._render(community, "test-archive")
        assert len(result) == 2
        html = repr(result[1])
        assert "just getting started" in html

    def test_empty_community_has_upload_cta(self):
        """Community landing page has upload CTA button."""
        community = {
            "id": "test-id",
            "slug": "my-family",
            "name": "My Family Archive",
        }
        result = self._render(community, "my-family")
        html = repr(result[1])
        assert "upload-cta" in html
        assert "Upload Photos" in html

    def test_empty_community_shows_name(self):
        """Community landing page shows community name."""
        community = {
            "id": "test-id",
            "slug": "cohen-family",
            "name": "Cohen Family Archive",
            "landing_title": "The Cohen Family",
        }
        result = self._render(community, "cohen-family")
        html = repr(result[1])
        assert "The Cohen Family" in html

    def test_empty_community_has_data_testid(self):
        """Community landing page has data-testid='community-landing'."""
        community = {
            "id": "test-id",
            "slug": "new-archive",
            "name": "New Archive",
        }
        result = self._render(community, "new-archive")
        html = repr(result[1])
        assert "community-landing" in html

    def test_empty_community_has_tools_links(self):
        """Community landing page links to standalone tools."""
        community = {
            "id": "test-id",
            "slug": "empty-archive",
            "name": "Empty Archive",
        }
        result = self._render(community, "empty-archive")
        html = repr(result[1])
        assert "/tools/estimate" in html
        assert "/tools/compare" in html

    def test_empty_community_shows_description(self):
        """Community landing page shows default description when none set."""
        community = {
            "id": "test-id",
            "slug": "no-desc",
            "name": "No Description",
        }
        result = self._render(community, "no-desc")
        html = repr(result[1])
        assert "community-description" in html
        assert "community photo archive" in html

    def test_community_with_custom_description(self):
        """Community landing page shows custom description when set."""
        community = {
            "id": "test-id",
            "slug": "custom",
            "name": "Custom",
            "description": "A very special archive of historical photos.",
        }
        result = self._render(community, "custom")
        html = repr(result[1])
        assert "A very special archive of historical photos" in html
