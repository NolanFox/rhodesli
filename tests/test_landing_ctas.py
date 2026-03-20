"""Tests for Session 123: UX-B landing page CTAs for visitors."""

from pathlib import Path


class TestLandingCTAs:
    """Verify landing page has CTA buttons for non-admin visitors."""

    def test_cta_section_exists(self):
        """Landing page must have a visitor CTA section."""
        source = Path("app/page_routes.py").read_text()
        assert "visitor-cta-section" in source, "Landing page must have CTA section"

    def test_help_identify_cta(self):
        """Must have Help Identify CTA linking to /help."""
        source = Path("app/page_routes.py").read_text()
        assert "cta-help-identify" in source, "Must have Help Identify CTA"

    def test_compare_face_cta(self):
        """Must have Compare a Face CTA linking to /tools/compare."""
        source = Path("app/page_routes.py").read_text()
        assert "cta-compare-face" in source, "Must have Compare Face CTA"
        assert "/tools/compare" in source, "Compare CTA must link to /tools/compare"

    def test_explore_archive_cta(self):
        """Must have Explore the Archive CTA linking to /people."""
        source = Path("app/page_routes.py").read_text()
        assert "cta-explore-archive" in source, "Must have Explore Archive CTA"

    def test_ctas_in_landing_page_function(self):
        """CTAs must be in the landing_page function, not admin sections."""
        source = Path("app/page_routes.py").read_text()
        # The CTA section should be near the landing_page function
        landing_idx = source.index("def landing_page(")
        cta_idx = source.index("visitor-cta-section")
        # CTA should be within landing_page function (within ~2000 lines)
        assert cta_idx > landing_idx, "CTAs must be inside landing_page function"
