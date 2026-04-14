"""Tests for mobile responsive fixes on the landing page (UX-134).

Verifies that the landing page HTML structure prevents horizontal overflow
at 375px mobile viewport width. Uses source code analysis to avoid
Supabase dependency issues in test environment.
"""

import re
from pathlib import Path
from unittest.mock import patch

from fasthtml.common import Div


class TestLandingMobileOverflowCSS:
    """Landing page CSS must prevent horizontal overflow on mobile."""

    def _get_landing_source(self):
        """Read the landing page source code."""
        return Path("app/page_routes.py").read_text()

    def test_body_overflow_hidden_in_css(self):
        """Body CSS must include overflow-x: hidden."""
        source = self._get_landing_source()
        # Find the landing_style Style block
        style_start = source.find("landing_style = Style(")
        assert style_start > 0, "landing_style must exist"
        style_section = source[style_start : style_start + 3000]
        assert "overflow-x: hidden" in style_section

    def test_body_max_width_100vw(self):
        """Body CSS must constrain max-width to 100vw."""
        source = self._get_landing_source()
        style_start = source.find("landing_style = Style(")
        style_section = source[style_start : style_start + 3000]
        assert "max-width: 100vw" in style_section

    def test_landing_container_overflow_hidden_in_css(self):
        """The .landing-container CSS must clip overflow."""
        source = self._get_landing_source()
        style_start = source.find("landing_style = Style(")
        style_section = source[style_start : style_start + 3000]
        assert ".landing-container" in style_section
        # Extract the .landing-container rule
        lc_start = style_section.find(".landing-container {")
        assert lc_start > 0
        lc_rule = style_section[lc_start : lc_start + 200]
        assert "overflow-x: hidden" in lc_rule
        assert "max-width: 100vw" in lc_rule

    def test_landing_container_box_sizing(self):
        """All landing container children must use border-box."""
        source = self._get_landing_source()
        assert ".landing-container * { box-sizing: border-box; }" in source

    def test_mobile_media_query_exists(self):
        """Mobile breakpoint media query must exist for landing styles."""
        source = self._get_landing_source()
        style_start = source.find("landing_style = Style(")
        style_end = source.find('""")', style_start)
        style_section = source[style_start:style_end]
        assert "@media (max-width: 767px)" in style_section

    def test_mobile_section_overflow_constraint(self):
        """Mobile CSS must constrain sections, nav, and footer."""
        source = self._get_landing_source()
        style_start = source.find("landing_style = Style(")
        style_end = source.find('""")', style_start)
        style_section = source[style_start:style_end]
        assert ".landing-container section" in style_section
        assert ".landing-container nav" in style_section
        assert ".landing-container footer" in style_section

    def test_mobile_title_font_size_override(self):
        """Mobile CSS must override the hero title font-size."""
        source = self._get_landing_source()
        style_start = source.find("landing_style = Style(")
        style_end = source.find('""")', style_start)
        style_section = source[style_start:style_end]
        assert ".ui99-landing-title" in style_section
        assert "font-size: 1.75rem" in style_section

    def test_mobile_button_sizing(self):
        """Mobile CSS must resize CTA buttons for small screens."""
        source = self._get_landing_source()
        style_start = source.find("landing_style = Style(")
        style_end = source.find('""")', style_start)
        style_section = source[style_start:style_end]
        assert ".btn-ui99-primary" in style_section
        # Should have a mobile-specific width: 100%
        assert "width: 100%" in style_section

    def test_names_track_hidden_on_mobile(self):
        """The names ticker track must be hidden on mobile."""
        source = self._get_landing_source()
        style_start = source.find("landing_style = Style(")
        style_end = source.find('""")', style_start)
        style_section = source[style_start:style_end]
        assert ".names-track" in style_section
        assert "display: none" in style_section


class TestLandingMobileHTMLStructure:
    """Landing page HTML structure must support mobile responsiveness."""

    def _get_landing_source(self):
        return Path("app/page_routes.py").read_text()

    def test_outer_container_has_overflow_class(self):
        """The outermost Div must have overflow-x-hidden class."""
        source = self._get_landing_source()
        # Find the landing_page function's return Div
        fn_start = source.find("def landing_page(")
        fn_section = source[fn_start:]
        assert "overflow-x-hidden" in fn_section
        assert "landing-container" in fn_section

    def test_outer_container_has_w_full(self):
        """The outermost Div must have w-full class."""
        source = self._get_landing_source()
        fn_start = source.find("def landing_page(")
        fn_section = source[fn_start:]
        # The landing-container line should have w-full
        for line in fn_section.split("\n"):
            if "landing-container" in line and "cls=" in line:
                assert "w-full" in line, "landing-container div must have w-full class"
                break

    def test_cta_buttons_flex_col_on_mobile(self):
        """CTA button containers must use flex-col for mobile stacking."""
        source = self._get_landing_source()
        fn_start = source.find("def landing_page(")
        fn_section = source[fn_start:]
        assert "flex-col" in fn_section, "CTA buttons must stack vertically on mobile (flex-col)"

    def test_hero_images_max_width(self):
        """Hero mosaic images must have max-width constraint in CSS."""
        source = self._get_landing_source()
        assert ".landing-container img { max-width: 100%; }" in source

    def test_no_hardcoded_wide_pixel_widths_in_landing(self):
        """No inline style in the landing function should set width > 375px."""
        source = self._get_landing_source()
        fn_start = source.find("def landing_page(")
        fn_end = source.find("\ndef ", fn_start + 1)
        fn_section = source[fn_start:fn_end]
        # Find width declarations in style= attributes
        width_pattern = re.compile(r'style=["\'].*?width:\s*(\d+)px', re.DOTALL)
        for match in width_pattern.finditer(fn_section):
            width_val = int(match.group(1))
            assert width_val <= 375, (
                f"Found inline width of {width_val}px in landing_page which exceeds 375px mobile viewport"
            )
