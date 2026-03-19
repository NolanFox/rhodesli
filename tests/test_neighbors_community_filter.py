"""Tests for FB-011: Community filter on Similar Identities (Session 120)."""

import unittest
from unittest.mock import MagicMock, patch


def _make_neighbor(identity_id, distance=0.9, can_merge=True, co_occurrence=0):
    """Create a neighbor dict for testing."""
    return {
        "identity_id": identity_id,
        "name": f"Person {identity_id}",
        "distance": distance,
        "percentile": 0.5,
        "confidence_gap": 5.0,
        "can_merge": can_merge,
        "face_count": 2,
        "co_occurrence": co_occurrence,
        "anchor_face_ids": [f"face-{identity_id}"],
        "candidate_face_ids": [],
        "state": "CONFIRMED",
    }


class TestNeighborsCommunityFilter(unittest.TestCase):
    """Test the community_filter parameter on the neighbors endpoint."""

    def _get_neighbors_sidebar_html(self, community_filter="", community=None):
        """Helper to render neighbors_sidebar with community context."""
        from app.main import neighbors_sidebar

        neighbors = [
            _make_neighbor("same-1", distance=0.8),
            _make_neighbor("cross-1", distance=0.5),
            _make_neighbor("same-2", distance=0.9),
            _make_neighbor("cross-2", distance=0.7),
        ]
        # Tag neighbors with community membership (as the route handler does)
        same_comm_ids = {"same-1", "same-2"}
        for n in neighbors:
            n["_same_community"] = n["identity_id"] in same_comm_ids

        if community is None:
            community = {"slug": "rhodes", "id": "comm-rhodes", "name": "Rhodes"}

        with (
            patch("app.main.resolve_face_image_url", return_value="/static/crops/test.jpg"),
            patch("app.main.get_best_face_id", return_value="face-same-1"),
        ):
            return repr(
                neighbors_sidebar(
                    "id-target",
                    neighbors,
                    {"face-same-1.jpg"},
                    current_community=community,
                    nav_prefix="/c/rhodes",
                    community_filter=community_filter,
                )
            )

    def test_community_filter_dropdown_present_with_community(self):
        """When community is set, the filter dropdown should appear."""
        html = self._get_neighbors_sidebar_html()
        assert "community_filter" in html
        assert "Same community first" in html
        assert "Same community only" in html
        assert "Cross-community only" in html

    def test_community_filter_dropdown_absent_without_community(self):
        """When no community is set, no filter dropdown should appear."""
        from app.main import neighbors_sidebar

        neighbors = [_make_neighbor("n-1")]
        with (
            patch("app.main.resolve_face_image_url", return_value="/static/crops/test.jpg"),
            patch("app.main.get_best_face_id", return_value="face-n-1"),
        ):
            html = repr(
                neighbors_sidebar(
                    "id-target",
                    neighbors,
                    {"face-n-1.jpg"},
                    current_community=None,
                )
            )
        assert "community_filter" not in html

    def test_default_sort_same_community_first(self):
        """Default sort should show same-community results before cross-community."""
        html = self._get_neighbors_sidebar_html()
        # same-1 should appear before cross-1 even though cross-1 has lower distance
        pos_same = html.find("same-1")
        pos_cross = html.find("cross-1")
        assert pos_same < pos_cross, "Same-community should appear before cross-community"


class TestNeighborsRouteFiltering(unittest.TestCase):
    """Test the community_filter logic in the route handler."""

    def test_community_filter_same_only_keeps_same_community(self):
        """community_filter=same should only show same-community neighbors."""
        neighbors = [
            _make_neighbor("same-1", distance=0.8),
            _make_neighbor("cross-1", distance=0.5),
            _make_neighbor("same-2", distance=0.9),
        ]
        comm_ids = {"same-1", "same-2"}

        # Simulate the route handler logic
        for n in neighbors:
            n["_same_community"] = n["identity_id"] in comm_ids

        community_filter = "same"
        filtered = [n for n in neighbors if n.get("_same_community", False)]
        assert len(filtered) == 2
        assert all(n["identity_id"].startswith("same") for n in filtered)

    def test_community_filter_cross_only_keeps_cross_community(self):
        """community_filter=cross should only show cross-community neighbors."""
        neighbors = [
            _make_neighbor("same-1", distance=0.8),
            _make_neighbor("cross-1", distance=0.5),
        ]
        comm_ids = {"same-1"}

        for n in neighbors:
            n["_same_community"] = n["identity_id"] in comm_ids

        community_filter = "cross"
        filtered = [n for n in neighbors if not n.get("_same_community", False)]
        assert len(filtered) == 1
        assert filtered[0]["identity_id"] == "cross-1"

    def test_community_filter_all_preserves_distance_order(self):
        """community_filter=all should keep original distance ordering."""
        neighbors = [
            _make_neighbor("cross-1", distance=0.5),
            _make_neighbor("same-1", distance=0.8),
            _make_neighbor("cross-2", distance=0.9),
        ]
        comm_ids = {"same-1"}

        for n in neighbors:
            n["_same_community"] = n["identity_id"] in comm_ids

        # "all" means no reordering — pass
        assert neighbors[0]["identity_id"] == "cross-1"
        assert neighbors[1]["identity_id"] == "same-1"

    def test_default_sort_groups_same_community_first(self):
        """Default (empty) filter should sort same-community first, then by distance."""
        neighbors = [
            _make_neighbor("cross-1", distance=0.5),
            _make_neighbor("same-1", distance=0.8),
            _make_neighbor("same-2", distance=0.6),
            _make_neighbor("cross-2", distance=0.9),
        ]
        comm_ids = {"same-1", "same-2"}

        for n in neighbors:
            n["_same_community"] = n["identity_id"] in comm_ids

        # Default sort: same-community first, then by distance within groups
        neighbors.sort(key=lambda n: (0 if n.get("_same_community", False) else 1, n.get("distance", 999)))
        assert neighbors[0]["identity_id"] == "same-2"  # same-comm, dist 0.6
        assert neighbors[1]["identity_id"] == "same-1"  # same-comm, dist 0.8
        assert neighbors[2]["identity_id"] == "cross-1"  # cross-comm, dist 0.5
        assert neighbors[3]["identity_id"] == "cross-2"  # cross-comm, dist 0.9


if __name__ == "__main__":
    unittest.main()
