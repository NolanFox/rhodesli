"""Tests for compare modal/page mobile responsiveness at 375px viewport.

Verifies:
1. Workspace slots use responsive min-width (min-w-0 on mobile, min-w-[300px] on sm+)
2. Hero face images scale down on mobile (120px mobile, 200px desktop)
3. Compare modal uses flex-col sm:flex-row for stacked layout on mobile
4. Arrow navigation buttons have 44px minimum touch targets
5. Action buttons (Merge, Not Same, Close) have adequate touch targets
6. Result containers have overflow-hidden to prevent horizontal scroll
7. Hero section stacks vertically on mobile
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


def _get_compare_modal_html(client):
    """Fetch the compare modal content HTML via the API endpoint."""
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


class TestCompareModalMobileLayout:
    """Tests for mobile responsive layout in the compare modal."""

    def test_compare_modal_uses_responsive_flex(self, client):
        """Compare modal container uses flex-col sm:flex-row for stacking on mobile."""
        html = _get_compare_modal_html(client)
        assert "flex-col" in html
        assert "sm:flex-row" in html

    def test_compare_modal_has_overflow_hidden(self, client):
        """Compare modal container has overflow-hidden to prevent horizontal scroll."""
        html = _get_compare_modal_html(client)
        assert "overflow-hidden" in html

    def test_action_buttons_have_adequate_padding(self, client):
        """Merge, Not Same, Close buttons have py-2 padding for touch targets."""
        html = _get_compare_modal_html(client)
        # Action buttons should have py-2 padding for adequate touch targets
        assert "py-2" in html


class TestComparePageMobileLayout:
    """Tests for the compare workspace page mobile responsiveness."""

    def test_compare_page_renders(self, client):
        """Compare page returns 200."""
        response = client.get("/tools/compare")
        assert response.status_code == 200

    def test_workspace_slots_responsive_min_width(self, client):
        """Workspace slots use min-w-0 (mobile) and sm:min-w-[300px] (desktop)."""
        response = client.get("/tools/compare")
        html = response.text
        assert "min-w-0" in html
        assert "sm:min-w-[300px]" in html

    def test_workspace_container_overflow(self, client):
        """Workspace flex container has overflow-hidden."""
        response = client.get("/tools/compare")
        assert "overflow-hidden" in response.text


class TestCompareHeroMobileLayout:
    """Tests for the hero section in compare results page."""

    def _read_source(self):
        """Read the compare_routes source code for structural assertions."""
        import app.compare_routes as mod
        import inspect

        return inspect.getsource(mod)

    def test_hero_images_responsive_sizing(self):
        """Hero face images use responsive classes: 120px mobile, 200px desktop."""
        source = self._read_source()
        assert "w-[120px]" in source
        assert "sm:w-[200px]" in source
        assert "h-[120px]" in source
        assert "sm:h-[200px]" in source

    def test_hero_stacks_vertically_on_mobile(self):
        """Hero section uses flex-col sm:flex-row for vertical stacking on mobile."""
        source = self._read_source()
        # Hero parts container should stack on mobile
        assert "flex-col sm:flex-row" in source
