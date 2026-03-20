"""Tests for face crop fallback placeholder on image load errors.

Session 127 Phase 2E: When face crop images fail to load (404 or broken),
show a placeholder silhouette instead of a broken image icon.
"""

import pytest
from core.storage import CROP_FALLBACK_SVG, CROP_FALLBACK_ONERROR


class TestCropFallbackConstants:
    """Test that crop fallback constants are properly defined."""

    def test_fallback_svg_is_data_uri(self):
        """SVG placeholder must be a valid data URI."""
        assert CROP_FALLBACK_SVG.startswith("data:image/svg+xml,")

    def test_fallback_svg_contains_silhouette_elements(self):
        """SVG must contain head (circle) and body (ellipse) for silhouette."""
        assert "circle" in CROP_FALLBACK_SVG
        assert "ellipse" in CROP_FALLBACK_SVG

    def test_fallback_svg_has_dark_background(self):
        """SVG background should use slate-800 (#1e293b) for dark theme."""
        # URL-encoded #1e293b = %231e293b
        assert "%231e293b" in CROP_FALLBACK_SVG

    def test_fallback_onerror_prevents_loop(self):
        """onerror handler must set this.onerror=null to prevent infinite loop."""
        assert "this.onerror=null" in CROP_FALLBACK_ONERROR

    def test_fallback_onerror_sets_src(self):
        """onerror handler must set src to the fallback SVG."""
        assert "this.src=" in CROP_FALLBACK_ONERROR
        assert "data:image/svg+xml" in CROP_FALLBACK_ONERROR

    def test_fallback_onerror_sets_alt(self):
        """onerror handler must set alt text for accessibility."""
        assert "this.alt='Photo unavailable'" in CROP_FALLBACK_ONERROR


class TestGlobalCropFallbackScript:
    """Test that the global JS error handler is present in page headers."""

    @pytest.fixture
    def app_headers_source(self):
        """Read the main.py source to check for the global script."""
        import pathlib

        main_py = pathlib.Path(__file__).parent.parent / "app" / "main.py"
        return main_py.read_text()

    def test_global_error_handler_exists(self, app_headers_source):
        """main.py must include a global error event listener for crop fallback."""
        assert "document.addEventListener('error'" in app_headers_source

    def test_global_handler_checks_img_tag(self, app_headers_source):
        """Global handler must only act on IMG elements."""
        assert "e.target.tagName !== 'IMG'" in app_headers_source

    def test_global_handler_checks_crops_path(self, app_headers_source):
        """Global handler must only act on crop image URLs (containing /crops/)."""
        assert "'/crops/'" in app_headers_source

    def test_global_handler_prevents_infinite_loop(self, app_headers_source):
        """Global handler must set onerror=null before changing src."""
        assert "e.target.onerror = null" in app_headers_source

    def test_global_handler_sets_svg_fallback(self, app_headers_source):
        """Global handler must set src to an inline SVG data URI."""
        assert "data:image/svg+xml" in app_headers_source

    def test_global_handler_uses_capture_phase(self, app_headers_source):
        """Error event must use capture phase (true) since error doesn't bubble."""
        # The addEventListener call should end with , true);
        assert "}, true)" in app_headers_source

    def test_global_handler_sets_alt_text(self, app_headers_source):
        """Global handler must set alt text for accessibility."""
        assert "Photo unavailable" in app_headers_source
