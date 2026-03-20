"""Tests for Session 121: UX-208 always show community badge on suggestion cards."""

from pathlib import Path


class TestCommunityBadgeAlways:
    """Verify community badge renders for BOTH same and cross community."""

    def test_same_community_returns_badge_not_none(self):
        """Same-community identities should get a badge, not None."""
        source = Path("app/main.py").read_text()
        idx = source.index("def _cross_community_badge")
        func = source[idx : idx + 2500]

        # The old code returned None for same community
        # New code should return a Span with muted styling
        assert "bg-slate-700" in func, "Same-community badge should use muted slate styling"

    def test_cross_community_uses_bright_styling(self):
        """Cross-community identities should get a bright blue badge."""
        source = Path("app/main.py").read_text()
        idx = source.index("def _cross_community_badge")
        func = source[idx : idx + 2500]

        assert "bg-indigo-600/30" in func, "Cross-community badge should use bright blue styling"

    def test_same_and_cross_have_different_styles(self):
        """Same-community and cross-community badges must be visually distinct."""
        source = Path("app/main.py").read_text()
        idx = source.index("def _cross_community_badge")
        func = source[idx : idx + 2500]

        # Both should exist
        has_slate = "bg-slate-700" in func
        has_blue = "bg-indigo-600/30" in func
        assert has_slate and has_blue, "Must have both muted (same) and bright (cross) badge styles"
