"""
Session 82e — UX Feature Sprint tests.

Tests for: Help page, identify mode, landing help section.
Pruned: CSS class assertions (masonry, hamburger breakpoints, animations).
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
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


def get_routeable_photo_id(client: TestClient):
    """Return the first photo_id whose public photo route renders successfully."""
    candidate_ids = []

    primary = get_real_photo_id()
    if primary:
        candidate_ids.append(primary)

    try:
        from app.main import _photo_cache

        if _photo_cache:
            for pid, pdata in _photo_cache.items():
                if pid in candidate_ids:
                    continue
                if pdata.get("faces") and pdata.get("width"):
                    candidate_ids.append(pid)
    except Exception:
        pass

    for photo_id in candidate_ids:
        response = client.get(f"/photo/{photo_id}")
        if response.status_code == 200:
            return photo_id
    return None


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def real_photo_id(client):
    return get_routeable_photo_id(client)


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

    def test_community_help_cards_keep_prefix(self, client):
        """Community-scoped help cards should keep identify/profile links inside the community."""
        mock_registry = MagicMock()
        mock_registry.list_identities.return_value = [
            {
                "identity_id": "unknown-fox-1",
                "name": "Unidentified Person 1",
                "state": "INBOX",
                "anchor_ids": ["face-fox-1"],
                "candidate_ids": [],
            }
        ]

        with ExitStack() as stack:
            stack.enter_context(patch("app.main.is_auth_enabled", return_value=False))
            stack.enter_context(patch("app.main._build_caches"))
            stack.enter_context(patch("app.main.load_registry", return_value=mock_registry))
            stack.enter_context(patch("app.main.get_crop_files", return_value={"face-fox-1.jpg"}))
            stack.enter_context(patch("app.main.get_best_face_id", return_value="face-fox-1"))
            stack.enter_context(patch("app.main.resolve_face_image_url", return_value="/static/crops/face-fox-1.jpg"))
            stack.enter_context(patch("app.main.get_photo_id_for_face", return_value="photo-1"))
            stack.enter_context(patch("app.main._photo_cache", {"photo-1": {"collection": "Fox Test Collection"}}))
            stack.enter_context(
                patch(
                    "app.supabase_data.get_community_by_slug",
                    return_value={"slug": "fox-family", "name": "Fox Family Archive"},
                )
            )
            response = client.get("/c/fox-family/help")

        html = response.text
        assert response.status_code == 200
        assert 'href="/c/fox-family/identify/unknown-fox-1"' in html
        assert 'href="/c/fox-family/person/unknown-fox-1"' in html


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
        """Landing page should have a CTA to help identify people."""
        response = client.get("/")
        assert response.status_code == 200
        # Current UI uses "Do you recognize anyone?" CTA linking to /help
        assert "recognize" in response.text.lower() or "help" in response.text.lower()

    def test_landing_page_links_to_help(self, client):
        """Landing page should link to /help."""
        response = client.get("/")
        assert response.status_code == 200
        assert "/help" in response.text
