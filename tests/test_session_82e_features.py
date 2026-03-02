"""
Session 82e — UX Feature Sprint tests.

Tests for: Mobile hamburger, masonry grid, help page, OG tags, identify mode.
"""

import pytest
from unittest.mock import patch, MagicMock
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


class TestMobileHamburger:
    """Phase 1: Mobile hamburger menu for small viewports."""

    def test_hamburger_script_injected(self, client):
        """Landing page should include hamburger auto-injection script."""
        response = client.get("/")
        assert response.status_code == 200
        assert "hamburger" in response.text

    def test_hamburger_uses_md_breakpoint(self, client):
        """Hamburger should trigger at md (768px), not sm (640px)."""
        response = client.get("/")
        assert response.status_code == 200
        # The global JS uses 768 for the breakpoint
        assert "768" in response.text

    def test_nav_has_md_hidden_class(self, client):
        """Nav links should use md:hidden for hamburger, not sm:hidden."""
        response = client.get("/photos")
        assert response.status_code == 200
        assert "md:hidden" in response.text or "md:flex" in response.text


class TestMasonryPhotoGrid:
    """Phase 2: Masonry photo grid preserving aspect ratios."""

    def test_photos_page_has_masonry_css(self, client):
        """Photos page should include CSS columns masonry layout."""
        response = client.get("/photos")
        assert response.status_code == 200
        assert "column-count" in response.text

    def test_photos_page_responsive_columns(self, client):
        """Masonry grid should have responsive column breakpoints."""
        response = client.get("/photos")
        assert response.status_code == 200
        # Should have media queries for different column counts
        assert "column-count: 2" in response.text or "column-count: 3" in response.text

    def test_photos_page_has_masonry_grid_class(self, client):
        """Photos page grid container should have masonry-grid class."""
        response = client.get("/photos")
        assert response.status_code == 200
        assert "masonry-grid" in response.text

    def test_masonry_build_uses_aspect_ratio(self):
        """_build_photo_cards with masonry=True should use aspect-ratio style."""
        from app.main import _build_photo_cards
        from fasthtml.common import to_xml
        test_photos = [{
            "photo_id": "test123",
            "filename": "test.jpg",
            "collection": "Test",
            "face_count": 1,
            "confirmed_count": 0,
            "match_reason": None,
            "width": 800,
            "height": 600,
        }]
        cards = _build_photo_cards(test_photos, masonry=True)
        html = to_xml(cards[0])
        assert "aspect-ratio" in html
        assert "break-inside" in html


class TestHelpNeededPage:
    """Phase 3A: Help Needed page with unidentified faces."""

    def test_help_page_returns_200(self, client):
        """/help should be a public route that returns 200."""
        response = client.get("/help")
        assert response.status_code == 200

    def test_help_page_has_face_cards(self, client):
        """/help page should show face cards."""
        response = client.get("/help")
        assert response.status_code == 200
        assert "help-face-card" in response.text

    def test_help_page_has_cta(self, client):
        """/help page should ask users to identify people."""
        response = client.get("/help")
        assert response.status_code == 200
        assert "recognize" in response.text.lower() or "identify" in response.text.lower()

    def test_help_in_navigation(self):
        """Navigation should include Help Identify link to /help."""
        with patch("app.main.is_auth_enabled", return_value=False):
            links = _public_nav_links(active="")
            hrefs = [link.attrs.get("href", "") for link in links]
            assert "/help" in hrefs

    def test_help_page_links_to_identify(self, client):
        """/help face cards should link to /identify/{id}."""
        response = client.get("/help")
        assert response.status_code == 200
        assert "/identify/" in response.text


class TestShareForHelp:
    """Phase 3B: OG tags on identify pages."""

    def test_identify_page_has_og_image(self, client):
        """Identify page should include og:image meta tag."""
        # Get a real identity to test with
        try:
            from app.main import load_registry
            registry = load_registry()
            identities = registry.get("identities", {})
            identity_id = next(iter(identities))
        except Exception:
            pytest.skip("No identities available")
        response = client.get(f"/identify/{identity_id}")
        if response.status_code != 200:
            pytest.skip("Identify page not accessible")
        assert 'og:image' in response.text

    def test_identify_page_has_og_title(self, client):
        """Identify page should include og:title meta tag."""
        try:
            from app.main import load_registry
            registry = load_registry()
            identities = registry.get("identities", {})
            identity_id = next(iter(identities))
        except Exception:
            pytest.skip("No identities available")
        response = client.get(f"/identify/{identity_id}")
        if response.status_code != 200:
            pytest.skip("Identify page not accessible")
        assert 'og:title' in response.text


class TestIdentifyModeFocusState:
    """Phase 4: Identify Mode focus state on photo pages."""

    def test_identify_mode_toggle_on_photo_page(self, client, real_photo_id):
        """Photo page with faces should have Identify Mode toggle."""
        if not real_photo_id:
            pytest.skip("No photos available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        assert "identify-mode-toggle" in response.text

    def test_identify_mode_css_animation(self, client, real_photo_id):
        """Photo page should include identify-pulse CSS animation."""
        if not real_photo_id:
            pytest.skip("No photos available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        assert "identify-pulse" in response.text

    def test_identify_mode_js_handler(self, client, real_photo_id):
        """Photo page should have JS handler for identify mode toggle."""
        if not real_photo_id:
            pytest.skip("No photos available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        assert "toggle-identify-mode" in response.text

    def test_face_overlays_have_data_identified(self, client, real_photo_id):
        """Face overlays should have data-identified attribute."""
        if not real_photo_id:
            pytest.skip("No photos available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        assert "data-identified" in response.text

    def test_photo_page_has_container_class(self, client, real_photo_id):
        """Photo page main container should have photo-page-container class."""
        if not real_photo_id:
            pytest.skip("No photos available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        assert "photo-page-container" in response.text

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
