"""Tests for enhanced community landing page empty states (PRD-036)."""

import app.main  # noqa: F401 — must import first to avoid circular import

from fasthtml.common import to_xml
from unittest.mock import patch


class TestCommunityLandingEmptyStates:
    """Tests for the enhanced empty state on community landing pages."""

    def _render(self, community, slug):
        """Helper to render _community_landing_page with mocked data loaders."""
        from app.page_routes import _community_landing_page

        with patch("app.supabase_data.load_photos_for_community", return_value=[]):
            with patch("app.supabase_data.load_identities_for_community", return_value=[]):
                return _community_landing_page(community, slug)

    def _html(self, result):
        return " ".join(to_xml(item) for item in result)

    def test_empty_community_renders(self):
        """Community landing page renders for empty community."""
        community = {
            "id": "test-id",
            "slug": "test-archive",
            "name": "Test Archive",
        }
        result = self._render(community, "test-archive")
        assert len(result) > 2
        html = self._html(result)
        assert "just getting started" in html

    def test_empty_community_has_upload_cta(self):
        """Community landing page has upload CTA button."""
        community = {
            "id": "test-id",
            "slug": "my-family",
            "name": "My Family Archive",
        }
        result = self._render(community, "my-family")
        html = self._html(result)
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
        html = self._html(result)
        assert "The Cohen Family" in html

    def test_empty_community_has_data_testid(self):
        """Community landing page has data-testid='community-landing'."""
        community = {
            "id": "test-id",
            "slug": "new-archive",
            "name": "New Archive",
        }
        result = self._render(community, "new-archive")
        html = self._html(result)
        assert "community-landing" in html

    def test_empty_community_has_tools_links(self):
        """Community landing page links to standalone tools."""
        community = {
            "id": "test-id",
            "slug": "empty-archive",
            "name": "Empty Archive",
        }
        result = self._render(community, "empty-archive")
        html = self._html(result)
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
        html = self._html(result)
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
        html = self._html(result)
        assert "A very special archive of historical photos" in html

    def test_non_rhodes_community_copy_and_og_use_community_scope(self):
        """Community landing page copy and OG metadata should use the community, not Rhodes."""
        from app.page_routes import _community_landing_page

        community = {
            "id": "fox-id",
            "slug": "fox-family",
            "name": "Fox Family Archive",
            "landing_subtitle": "A family photo archive",
        }

        with (
            patch("app.main._get_community_photo_ids", return_value={"photo-fox-1"}),
            patch("app.main._get_community_identity_ids", return_value=set()),
            patch("app.main.get_photo_metadata", return_value={"filename": "fox-photo.jpg"}),
            patch("app.main.storage.get_photo_url", side_effect=lambda path: f"/photos/{path}"),
        ):
            result = _community_landing_page(community, "fox-family")

        html = self._html(result)
        assert "Fox Family Archive" in html
        assert "Jewish Community of Rhodes" not in html
        assert "Select an archive below" not in html
        assert 'property="og:title"' in html
        assert 'property="og:description"' in html
        assert 'property="og:image"' in html
        assert "/photos/fox-photo.jpg" in html
