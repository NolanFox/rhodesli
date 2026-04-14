"""Tests for photo page mobile responsiveness at 375px viewport.

Verifies that the photo page source code includes responsive classes and
mobile-friendly patterns for face overlays, person cards, and touch targets.
These are source-level structural tests -- they verify the code emits the
correct CSS classes and media queries, not rendered pixel output.
"""

import inspect

import pytest


def _get_photo_page_source():
    """Read the public_photo_page function source from page_routes.py."""
    from app.page_routes import public_photo_page

    return inspect.getsource(public_photo_page)


class TestPhotoPageMobileCSS:
    """Verify the photo page CSS includes mobile-responsive rules."""

    def test_photo_img_has_max_w_full(self):
        """Photo image must have max-w-full to scale within mobile viewport."""
        src = _get_photo_page_source()
        assert "max-w-full" in src, "Photo image should have max-w-full class"

    def test_photo_hero_container_max_width(self):
        """Photo hero container CSS must constrain to 100% width."""
        src = _get_photo_page_source()
        assert "max-width: 100%" in src, "Photo hero container should have max-width: 100%"

    def test_face_overlay_labels_have_viewport_constraint(self):
        """Face overlay labels must include calc(100vw-2rem) to prevent overflow on mobile."""
        src = _get_photo_page_source()
        assert "100vw - 2rem" in src, "Face overlay labels should constrain max-width to viewport on mobile via CSS"

    def test_face_overlay_labels_have_mobile_text_size(self):
        """Face overlay labels should use smaller text on mobile."""
        src = _get_photo_page_source()
        assert "text-[10px]" in src, "Face overlay labels should have text-[10px] for mobile"
        assert "sm:text-[11px]" in src, "Face overlay labels should scale to sm:text-[11px] on desktop"

    def test_face_overlay_labels_have_label_class(self):
        """Face overlay labels should have face-overlay-label class for CSS targeting."""
        src = _get_photo_page_source()
        assert "face-overlay-label" in src, "Face overlay labels should have face-overlay-label CSS class"

    def test_person_cards_grid_responsive(self):
        """Person cards grid must use responsive columns."""
        src = _get_photo_page_source()
        assert "grid-cols-2" in src, "Person cards should use 2 columns as base"
        assert "sm:grid-cols-3" in src, "Person cards should use 3 columns on sm+"

    def test_mobile_css_single_column_narrow(self):
        """CSS should include single-column rule for very narrow viewports."""
        src = _get_photo_page_source()
        assert "max-width: 400px" in src, "Should have CSS media query for narrow viewports"
        assert "grid-template-columns: 1fr" in src, "Should switch to single column at narrow widths"

    def test_mobile_css_touch_targets(self):
        """CSS should enforce 44px minimum touch targets on mobile."""
        src = _get_photo_page_source()
        assert "min-height: 44px" in src, "Should enforce 44px min-height for touch targets"

    def test_action_bar_has_responsive_class(self):
        """Action bar should have photo-action-bar class for mobile stacking."""
        src = _get_photo_page_source()
        assert "photo-action-bar" in src, "Action bar should have photo-action-bar class"

    def test_mobile_css_action_bar_stacks(self):
        """CSS should stack action bar vertically on mobile."""
        src = _get_photo_page_source()
        assert ".photo-action-bar" in src, "CSS should target .photo-action-bar"
        assert "flex-direction: column" in src, "Action bar should stack vertically on mobile"

    def test_metadata_overlay_compact_padding(self):
        """Metadata overlay should use compact padding on mobile, not oversized."""
        src = _get_photo_page_source()
        lines = [line for line in src.split("\n") if "photo-info-overlay" in line and "left-3" in line]
        assert len(lines) >= 1, "Should have photo-info-overlay metadata overlay"
        for line in lines:
            assert "px-5 py-4" not in line, (
                f"Metadata overlay should not have oversized px-5 py-4 padding: {line.strip()}"
            )

    def test_face_overlay_overflow_hidden_mobile_css(self):
        """Mobile CSS should set overflow hidden on photo-hero-container for mobile."""
        src = _get_photo_page_source()
        assert "overflow: hidden" in src, "Mobile CSS should hide overflow on photo-hero-container"

    def test_no_inverted_padding_on_photo_page_badges(self):
        """Photo page badges should not have inverted px-4 py-3 sm:px-2 sm:py-1 pattern."""
        src = _get_photo_page_source()
        lines = src.split("\n")
        violations = []
        for i, line in enumerate(lines):
            if "px-4 py-3" in line and "sm:px-2" in line:
                stripped = line.strip()
                if "photo-info-overlay" in stripped or "rounded-full backdrop-blur" in stripped:
                    violations.append(f"Line {i}: {stripped[:100]}")
        assert len(violations) == 0, f"Found inverted padding (large mobile, small desktop): {violations}"

    def test_photo_page_renders_via_route(self):
        """Smoke test: /photo/nonexistent returns 404 (page still renders)."""
        from starlette.testclient import TestClient
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/photo/nonexistent_id_12345")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        assert "photo" in resp.text.lower() or "not found" in resp.text.lower()
