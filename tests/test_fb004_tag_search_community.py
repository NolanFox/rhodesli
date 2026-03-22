"""Tests for FB-004: Community-scoped Quick Identify name dropdown.

Tag search should filter results by current community by default,
with a "Show all communities" option to see cross-community names.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestTagSearchCommunityFiltering:
    """Tag search filters results to current community by default."""

    def _make_search_results(self):
        """Create mock search results from two communities."""
        return [
            {
                "identity_id": "rhodes-1",
                "name": "Abraham Almaleh",
                "face_count": 3,
                "preview_face_id": "f1",
                "state": "CONFIRMED",
            },
            {
                "identity_id": "rhodes-2",
                "name": "Anita Capeluto Franco",
                "face_count": 2,
                "preview_face_id": "f2",
                "state": "CONFIRMED",
            },
            {
                "identity_id": "fox-1",
                "name": "Albert Fox",
                "face_count": 5,
                "preview_face_id": "f3",
                "state": "CONFIRMED",
            },
            {
                "identity_id": "fox-2",
                "name": "Harry Fox",
                "face_count": 4,
                "preview_face_id": "f4",
                "state": "CONFIRMED",
            },
        ]

    def test_tag_search_filters_by_community(self, client, auth_disabled):
        """When community context is active, only community identities are shown."""
        fox_community = {"id": 2, "slug": "fox-family", "name": "Fox Family"}

        with (
            patch("app.supabase_data.get_community_by_slug", return_value=fox_community),
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face", return_value=None),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
            patch("app.main._get_community_identity_ids", return_value={"fox-1", "fox-2"}),
        ):
            registry = MagicMock()
            registry.search_identities.return_value = self._make_search_results()
            mock_reg.return_value = registry

            # Use /c/fox-family/ prefix to trigger community middleware
            resp = client.get("/c/fox-family/api/face/tag-search?face_id=test-face&q=al")
            html = resp.text

            # Fox family names should appear
            assert "Albert Fox" in html
            # Rhodes names should be filtered out
            assert "Abraham Almaleh" not in html
            assert "Anita Capeluto Franco" not in html
            # "Show all communities" link should appear (2 hidden results)
            assert "Show all communities" in html

    def test_tag_search_show_all_returns_all_communities(self, client, auth_disabled):
        """When show_all=1, results from all communities are returned."""
        fox_community = {"id": 2, "slug": "fox-family", "name": "Fox Family"}

        with (
            patch("app.supabase_data.get_community_by_slug", return_value=fox_community),
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face", return_value=None),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
            patch("app.main._get_community_identity_ids", return_value={"fox-1", "fox-2"}),
        ):
            registry = MagicMock()
            registry.search_identities.return_value = self._make_search_results()
            mock_reg.return_value = registry

            resp = client.get("/c/fox-family/api/face/tag-search?face_id=test-face&q=al&show_all=1")
            html = resp.text

            # All names should appear
            assert "Albert Fox" in html
            assert "Abraham Almaleh" in html
            # "Show all communities" should NOT appear when already showing all
            assert "Show all communities" not in html

    def test_tag_search_no_community_shows_all(self, client, auth_disabled):
        """Without community context, all identities are shown (no filtering)."""
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face", return_value=None),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
        ):
            registry = MagicMock()
            registry.search_identities.return_value = self._make_search_results()
            mock_reg.return_value = registry

            # No /c/ prefix = no community context
            resp = client.get("/api/face/tag-search?face_id=test-face&q=al")
            html = resp.text

            # All names should appear (no community filtering)
            assert "Albert Fox" in html
            assert "Abraham Almaleh" in html
            assert "Show all communities" not in html

    def test_tag_search_community_no_hidden_results_no_show_all(self, client, auth_disabled):
        """When all results are in the community, no 'Show all' button appears."""
        fox_community = {"id": 2, "slug": "fox-family", "name": "Fox Family"}

        with (
            patch("app.supabase_data.get_community_by_slug", return_value=fox_community),
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face", return_value=None),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
            patch("app.main._get_community_identity_ids", return_value={"fox-1", "fox-2"}),
        ):
            registry = MagicMock()
            # Only Fox family results
            registry.search_identities.return_value = [
                {
                    "identity_id": "fox-1",
                    "name": "Albert Fox",
                    "face_count": 5,
                    "preview_face_id": "f3",
                    "state": "CONFIRMED",
                },
            ]
            mock_reg.return_value = registry

            resp = client.get("/c/fox-family/api/face/tag-search?face_id=test-face&q=al")
            html = resp.text

            assert "Albert Fox" in html
            assert "Show all communities" not in html
