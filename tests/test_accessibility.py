"""Tests for structural accessibility: skip link, main landmark, focus indicators."""

import pytest


class TestSkipToContentLink:
    """The skip-to-content link must be present on all pages."""

    def test_landing_page_has_skip_link(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "Skip to main content" in response.text

    def test_community_landing_has_skip_link(self, client):
        response = client.get("/c/rhodes/")
        assert response.status_code == 200
        assert "Skip to main content" in response.text

    def test_photos_page_has_skip_link(self, client):
        response = client.get("/photos")
        assert response.status_code == 200
        assert "Skip to main content" in response.text

    def test_people_page_has_skip_link(self, client):
        response = client.get("/people")
        assert response.status_code == 200
        assert "Skip to main content" in response.text

    def test_compare_page_has_skip_link(self, client):
        response = client.get("/tools/compare")
        assert response.status_code == 200
        assert "Skip to main content" in response.text

    def test_estimate_page_has_skip_link(self, client):
        response = client.get("/tools/estimate")
        assert response.status_code == 200
        assert "Skip to main content" in response.text

    def test_about_page_has_skip_link(self, client):
        response = client.get("/about")
        assert response.status_code == 200
        assert "Skip to main content" in response.text

    def test_skip_link_targets_main_content(self, client):
        """The skip link href must point to #main-content."""
        response = client.get("/")
        assert "#main-content" in response.text


class TestMainContentLandmark:
    """Every page must have a <main> element that gets id='main-content'."""

    def test_landing_page_has_main_element(self, client):
        response = client.get("/")
        assert "<main" in response.text

    def test_community_landing_has_main_element(self, client):
        response = client.get("/c/rhodes/")
        assert "<main" in response.text

    def test_photos_page_has_main_element(self, client):
        response = client.get("/photos")
        assert "<main" in response.text

    def test_people_page_has_main_element(self, client):
        response = client.get("/people")
        assert "<main" in response.text

    def test_compare_page_has_main_element(self, client):
        response = client.get("/tools/compare")
        assert "<main" in response.text

    def test_estimate_page_has_main_element(self, client):
        response = client.get("/tools/estimate")
        assert "<main" in response.text

    def test_main_content_id_injection_script_present(self, client):
        """JS that sets id='main-content' on the first <main> must be in the page."""
        response = client.get("/")
        assert "main-content" in response.text
        # Verify the script sets the id on the main element
        assert "querySelector('main')" in response.text


class TestFocusIndicators:
    """Global CSS must include visible focus indicators."""

    def test_focus_visible_styles_present(self, client):
        response = client.get("/")
        assert "focus-visible" in response.text

    def test_focus_visible_outline_style(self, client):
        """Focus outline must use indigo color (#818cf8)."""
        response = client.get("/")
        assert "#818cf8" in response.text

    def test_focus_visible_on_buttons(self, client):
        response = client.get("/")
        assert "button:focus-visible" in response.text

    def test_focus_visible_on_links(self, client):
        response = client.get("/")
        assert "a:focus-visible" in response.text

    def test_focus_visible_on_inputs(self, client):
        response = client.get("/")
        assert "input:focus-visible" in response.text

    def test_focus_visible_on_multiple_pages(self, client):
        """Focus styles must be global (present on all pages via hdrs)."""
        for path in ["/", "/photos", "/tools/compare", "/tools/estimate", "/about"]:
            response = client.get(path)
            assert "focus-visible" in response.text, f"focus-visible missing on {path}"


class TestSkipLinkStyling:
    """The skip link must have sr-only styling that reveals on focus."""

    def test_skip_link_has_sr_only_class(self, client):
        """Skip link should be visually hidden but focusable."""
        response = client.get("/")
        # The JS creates a link with sr-only class
        assert "sr-only" in response.text

    def test_skip_link_has_focus_reveal(self, client):
        """Skip link must become visible on focus (focus:not-sr-only)."""
        response = client.get("/")
        assert "focus:not-sr-only" in response.text
