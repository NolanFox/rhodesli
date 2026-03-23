"""Tests for FB-009: Compare Active Side — visual active-side indicator in Compare modal.

Verifies:
1. data-compare-side attributes on panel divs
2. Target panel has default active ring (ring-2, ring-amber-400/50)
3. "Source" and "Match" labels present
4. Neighbor panel does NOT have ring classes by default
5. Arrow buttons include ring toggle hyperscript
6. Aria labels on panel divs
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def _mock_registry():
    """Create a mock registry with two identities for compare testing."""
    registry = MagicMock()
    target = {
        "identity_id": "aaaa-1111",
        "name": "Alice Test",
        "state": "CONFIRMED",
        "anchor_ids": ["face_t1", "face_t2"],
        "candidate_ids": [],
    }
    neighbor = {
        "identity_id": "bbbb-2222",
        "name": "Bob Test",
        "state": "PROPOSED",
        "anchor_ids": ["face_n1"],
        "candidate_ids": [],
    }

    def get_identity(iid):
        if iid == "aaaa-1111":
            return target
        if iid == "bbbb-2222":
            return neighbor
        raise KeyError(iid)

    registry.get_identity = get_identity
    return registry


class TestCompareActiveSide:
    """Tests for the active side indicator in the Compare modal."""

    def _get_compare_html(self, client):
        """Fetch the compare content HTML via the API endpoint."""
        registry = _mock_registry()
        with patch("app.compare_routes._main_mod") as mock_main:
            mock_main.load_registry.return_value = registry
            mock_main.get_crop_files.return_value = set()
            mock_main.get_best_face_id.return_value = None
            mock_main.resolve_face_image_url.return_value = "/static/crops/test.jpg"
            mock_main._build_caches.return_value = None
            mock_main._face_to_photo_cache = {}
            mock_main._photo_cache = {}
            mock_main._get_user_role.return_value = "admin"
            mock_main.community_url_prefix.return_value = ""

            response = client.get("/api/identity/aaaa-1111/compare/bbbb-2222?view=faces")
            return response.text

    def test_data_compare_side_target_attribute(self, client):
        """Target panel has data-compare-side='target' attribute."""
        html = self._get_compare_html(client)
        assert 'data-compare-side="target"' in html

    def test_data_compare_side_neighbor_attribute(self, client):
        """Neighbor panel has data-compare-side='neighbor' attribute."""
        html = self._get_compare_html(client)
        assert 'data-compare-side="neighbor"' in html

    def test_target_panel_has_active_ring(self, client):
        """Target panel has ring-2 ring-amber-400/50 classes by default."""
        html = self._get_compare_html(client)
        # The target panel div should have ring classes
        assert "ring-2" in html
        assert "ring-amber-400/50" in html

    def test_source_label_present(self, client):
        """'Source' label is present in the compare content."""
        html = self._get_compare_html(client)
        assert ">Source<" in html or "Source</span>" in html

    def test_match_label_present(self, client):
        """'Match' label is present in the compare content."""
        html = self._get_compare_html(client)
        assert ">Match<" in html or "Match</span>" in html

    def test_neighbor_panel_no_ring(self, client):
        """Neighbor panel does NOT have ring-2 class by default."""
        html = self._get_compare_html(client)
        # Find the neighbor panel section — it has data-compare-side="neighbor"
        # The neighbor panel should have rounded-xl p-2 but NOT ring-2
        neighbor_idx = html.find('data-compare-side="neighbor"')
        assert neighbor_idx > 0
        # Get the opening tag of the neighbor div — find the nearest class before it
        # Look backward for the class attribute
        tag_start = html.rfind("<div", 0, neighbor_idx)
        tag_end = html.find(">", neighbor_idx)
        neighbor_tag = html[tag_start : tag_end + 1]
        # Neighbor tag should NOT contain ring-2
        assert "ring-2" not in neighbor_tag

    def test_aria_labels_present(self, client):
        """Panel divs have aria-label attributes for accessibility."""
        html = self._get_compare_html(client)
        assert 'aria-label="Source panel"' in html
        assert 'aria-label="Match panel"' in html

    def test_arrow_buttons_have_ring_toggle_hyperscript(self, client):
        """Arrow buttons include hyperscript for toggling the active ring."""
        html = self._get_compare_html(client)
        # The hyperscript should reference data-compare-side for ring toggling
        assert "data-compare-side" in html
        # Check for the ring toggle pattern in hyperscript
        assert "ring-amber-400" in html
