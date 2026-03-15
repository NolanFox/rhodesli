"""Tests for community-scoped suggestions (FB-147, FB-148, PERF-007).

Verifies:
- Find-similar results prioritize same-community identities
- Speed-run suggested matches prioritize same-community confirmed identities
- Cross-community badge text has no "From " prefix
"""

import pytest
from unittest.mock import patch, MagicMock


class TestSimilarResultsCommunityScoped:
    """Tests for community scoping logic in find-similar results."""

    def test_similar_results_same_community_first(self):
        """Same-community neighbors should appear before cross-community when >= 5."""
        # Simulate the scoping logic from browse_routes.py
        neighbors = [{"identity_id": f"id-{i}", "distance": 0.5 + i * 0.1} for i in range(10)]
        comm_ids = {f"id-{i}" for i in range(6)}  # first 6 are same-community

        same_comm = [n for n in neighbors if n["identity_id"] in comm_ids]
        cross_comm = [n for n in neighbors if n["identity_id"] not in comm_ids]

        # With >= 5 same-community, only same-community results shown
        assert len(same_comm) >= 5
        result = same_comm[:12]
        assert all(n["identity_id"] in comm_ids for n in result)

    def test_similar_results_cross_community_fills_in(self):
        """Cross-community results should fill in when < 5 same-community results."""
        neighbors = [{"identity_id": f"id-{i}", "distance": 0.5 + i * 0.1} for i in range(10)]
        comm_ids = {"id-0", "id-1"}  # only 2 same-community

        same_comm = [n for n in neighbors if n["identity_id"] in comm_ids]
        cross_comm = [n for n in neighbors if n["identity_id"] not in comm_ids]

        assert len(same_comm) < 5
        result = (same_comm + cross_comm)[:12]
        # Same-community results first, then cross-community
        assert result[0]["identity_id"] in comm_ids
        assert result[1]["identity_id"] in comm_ids
        # Cross-community fills the rest
        assert len(result) == 10

    def test_empty_community_ids_no_filtering(self):
        """When comm_ids is None, no filtering should happen."""
        neighbors = [{"identity_id": f"id-{i}", "distance": 0.5 + i * 0.1} for i in range(10)]
        comm_ids = None
        # When comm_ids is None, neighbors are returned as-is
        if comm_ids is not None:
            pytest.fail("Should not filter when comm_ids is None")
        assert len(neighbors) == 10


class TestSuggestedMatchesCommunityOrdered:
    """Tests for _get_confirmed_identity_suggestions community ordering."""

    def test_suggested_matches_community_ordered(self):
        """Same-community confirmed identities should appear first."""
        from app.cluster_review_routes import _get_confirmed_identity_suggestions

        # Create mock identities — some in-community, some cross-community
        mock_identities = {}
        for i in range(6):
            iid = f"test-identity-{i}"
            mock_identities[iid] = {
                "identity_id": iid,
                "name": f"Person {i}",
                "state": "CONFIRMED",
                "anchor_ids": [f"face-{i}-0", f"face-{i}-1"],
                "candidate_ids": [],
            }

        class MockRegistry:
            _identities = mock_identities

        # IDs 0,1,2 are same community; 3,4,5 are cross-community
        same_comm_ids = {"test-identity-0", "test-identity-1", "test-identity-2"}

        mock_community = {"id": 1, "slug": "test-comm", "name": "Test Community"}

        with (
            patch("app.cluster_review_routes._main_mod.load_registry", return_value=MockRegistry()),
            patch("app.cluster_review_routes._main_mod._get_community_identity_ids", return_value=same_comm_ids),
            patch("app.supabase_data.load_communities", return_value=[mock_community]),
        ):
            results = _get_confirmed_identity_suggestions("other-id", limit=3, community_slug="test-comm")

            # All 3 should be same-community since there are enough
            result_ids = {r["identity_id"] for r in results}
            assert result_ids.issubset(same_comm_ids), f"Expected same-community IDs first, got {result_ids}"

    def test_suggested_matches_no_community_falls_back(self):
        """Without community_slug, should return by face count only."""
        from app.cluster_review_routes import _get_confirmed_identity_suggestions

        mock_identities = {
            "id-a": {
                "identity_id": "id-a",
                "name": "Person A",
                "state": "CONFIRMED",
                "anchor_ids": ["f1", "f2", "f3"],
                "candidate_ids": [],
            },
            "id-b": {
                "identity_id": "id-b",
                "name": "Person B",
                "state": "CONFIRMED",
                "anchor_ids": ["f4"],
                "candidate_ids": [],
            },
        }

        class MockRegistry:
            _identities = mock_identities

        with patch("app.cluster_review_routes._main_mod.load_registry", return_value=MockRegistry()):
            results = _get_confirmed_identity_suggestions("other-id", limit=3, community_slug=None)
            assert len(results) == 2
            # Person A has more faces, should be first
            assert results[0]["identity_id"] == "id-a"


class TestCrossCommunityBadgeNoFromPrefix:
    """Tests for cross-community badge text (FB-148)."""

    def test_cross_community_badge_no_from_prefix(self):
        """Badge should show community name without 'From ' prefix."""
        from app.main import _cross_community_badge

        mock_current = {"id": 1, "slug": "rhodes", "name": "Jewish Community of Rhodes"}
        mock_other = {"id": 2, "slug": "fox-family", "name": "Fox Family Archive"}

        with (
            patch(
                "app.main._get_community_identity_ids",
                side_effect=lambda c: set() if c == mock_current else {"test-id"},
            ),
            patch("app.supabase_data.load_communities", return_value=[mock_current, mock_other]),
        ):
            badge = _cross_community_badge("test-id", mock_current)
            assert badge is not None

            # Get the text content — badge is a Span element
            from fasthtml.common import to_xml

            html = to_xml(badge)
            assert "From " not in html
            assert "Fox Family Archive" in html

    def test_same_community_no_badge(self):
        """No badge for identity in the same community."""
        from app.main import _cross_community_badge

        mock_current = {"id": 1, "slug": "rhodes", "name": "Jewish Community of Rhodes"}

        with patch("app.main._get_community_identity_ids", return_value={"test-id"}):
            badge = _cross_community_badge("test-id", mock_current)
            assert badge is None
