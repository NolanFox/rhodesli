"""Tests for Session 127 UX quick wins: button ordering + confidence tier labels."""

import pytest


@pytest.fixture(autouse=True)
def _patch_env(monkeypatch):
    """Ensure DATA_SOURCE=json so we don't need Supabase."""
    monkeypatch.setenv("DATA_SOURCE", "json")


# ---------------------------------------------------------------------------
# 1. Focus / View All / Match button ordering
# ---------------------------------------------------------------------------


class TestButtonOrdering:
    """Focus should appear before View All, which appears before Match."""

    def _get_section_header_html(self):
        """Import and render section_header for to_review."""
        from app.main import section_header

        header = section_header(
            "New Matches",
            "test subtitle",
            view_mode="browse",
            section="to_review",
            nav_prefix="/c/test",
        )
        return repr(header)

    def test_focus_before_view_all(self):
        html = self._get_section_header_html()
        focus_pos = html.find(">Focus<")
        view_all_pos = html.find(">View All<")
        assert focus_pos != -1, "Focus button not found"
        assert view_all_pos != -1, "View All button not found"
        assert focus_pos < view_all_pos, "Focus must appear before View All"

    def test_view_all_before_match(self):
        html = self._get_section_header_html()
        view_all_pos = html.find(">View All<")
        match_pos = html.find(">Match<")
        assert view_all_pos != -1, "View All button not found"
        assert match_pos != -1, "Match button not found"
        assert view_all_pos < match_pos, "View All must appear before Match"

    def test_all_three_buttons_present(self):
        html = self._get_section_header_html()
        assert ">Focus<" in html
        assert ">View All<" in html
        assert ">Match<" in html


# ---------------------------------------------------------------------------
# 2. Confidence tier labels
# ---------------------------------------------------------------------------


class TestConfidenceTierLabels:
    """Distance values should produce the correct human-readable tier label."""

    def _get_tier_text(self, distance: float) -> str:
        from app.main import _confidence_tier_label

        span = _confidence_tier_label(distance)
        return repr(span)

    def test_strong_match_below_080(self):
        html = self._get_tier_text(0.72)
        assert "Strong match" in html

    def test_good_match_080_to_099(self):
        html = self._get_tier_text(0.85)
        assert "Good match" in html

    def test_possible_match_100_to_119(self):
        html = self._get_tier_text(1.05)
        assert "Possible match" in html

    def test_weak_match_120_plus(self):
        html = self._get_tier_text(1.35)
        assert "Weak match" in html

    def test_boundary_080_is_good(self):
        html = self._get_tier_text(0.80)
        assert "Good match" in html

    def test_boundary_100_is_possible(self):
        html = self._get_tier_text(1.00)
        assert "Possible match" in html

    def test_boundary_120_is_weak(self):
        html = self._get_tier_text(1.20)
        assert "Weak match" in html

    def test_tier_has_testid(self):
        from app.main import _confidence_tier_label

        span = _confidence_tier_label(0.90)
        html = repr(span)
        assert 'data-testid="confidence-tier"' in html

    def test_match_info_bar_includes_tier(self):
        """match_info_bar should include a confidence tier label."""
        from app.main import match_info_bar

        bar = match_info_bar(distance=0.85, show_distance=True)
        html = repr(bar)
        assert "Good match" in html
        assert 'data-testid="confidence-tier"' in html

    def test_match_info_bar_strong(self):
        from app.main import match_info_bar

        bar = match_info_bar(distance=0.65, show_distance=True)
        html = repr(bar)
        assert "Strong match" in html

    def test_match_info_bar_weak(self):
        from app.main import match_info_bar

        bar = match_info_bar(distance=1.30, show_distance=True)
        html = repr(bar)
        assert "Weak match" in html

    def test_match_info_bar_no_distance_no_tier(self):
        """When show_distance=False, no tier label should appear."""
        from app.main import match_info_bar

        bar = match_info_bar(distance=0.85, show_distance=False)
        html = repr(bar)
        assert "confidence-tier" not in html
