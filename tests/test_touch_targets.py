"""Tests for touch target sizing (>=36px) on interactive elements.

Session 127 Phase 1A: Ensure all interactive badges, pagination links,
and status indicators have adequate padding for mobile touch targets.
"""

import unittest


class TestClusterReviewTouchTargets(unittest.TestCase):
    """Verify cluster_review_routes badges use py-1 (not py-0.5)."""

    def test_confidence_badge_has_adequate_padding(self):
        from app.cluster_review_routes import _confidence_badge

        for distance in [0.75, 0.90, 1.00, 1.10]:
            badge = _confidence_badge(distance)
            html = repr(badge)
            assert "py-1" in html, f"Confidence badge at {distance} missing py-1: {html}"
            assert "py-0.5" not in html, f"Confidence badge at {distance} still has py-0.5"

    def test_active_learning_reason_badges_adequate_padding(self):
        from app.cluster_review_routes import _active_learning_reason_badges

        # Test with no reasons (general coverage badge)
        badge = _active_learning_reason_badges([])
        html = repr(badge)
        assert "py-1" in html, f"General coverage badge missing py-1: {html}"
        assert "py-0.5" not in html, "General coverage badge still has py-0.5"

        # Test with specific reasons
        badge = _active_learning_reason_badges(["boundary_distance", "tail_identity"])
        html = repr(badge)
        assert "py-1" in html, f"Reason badges missing py-1: {html}"
        assert "py-0.5" not in html, "Reason badges still have py-0.5"

    def test_state_badge_adequate_padding(self):
        """State badges in _unresolved_review_group_card use py-1."""
        from app.cluster_review_routes import _unresolved_review_group_card

        # We can't easily call _state_badge directly (it's nested),
        # but we can verify through the module source that py-0.5 is gone.
        import inspect

        source = inspect.getsource(_unresolved_review_group_card)
        # The _state_badge function is defined inside _unresolved_review_group_card
        assert "py-0.5" not in source, "State badges in _unresolved_review_group_card still have py-0.5"
        assert "py-1" in source, "State badges in _unresolved_review_group_card missing py-1"

    def test_gedcom_triage_card_badges_adequate_padding(self):
        """GEDCOM linked/not-linked badges use py-1."""
        from app.cluster_review_routes import _gedcom_triage_card
        import inspect

        source = inspect.getsource(_gedcom_triage_card)
        assert "py-0.5" not in source, "GEDCOM badges still have py-0.5"
        assert "py-1" in source, "GEDCOM badges missing py-1"


class TestEngagementTouchTargets(unittest.TestCase):
    """Verify engagement_routes pagination and status badges have adequate padding."""

    def test_pagination_has_adequate_padding(self):
        """Pagination elements should use px-3 py-1.5."""
        from app import engagement_routes
        import inspect

        # Check the function that renders proposed matches (contains pagination)
        source = inspect.getsource(engagement_routes)
        # Pagination spans and links should have py-1.5, not py-1 or py-0.5
        assert "px-3 py-1.5 bg-indigo-600" in source, "Active page indicator missing px-3 py-1.5"
        assert "px-3 py-1.5 bg-slate-700" in source, "Page link missing px-3 py-1.5"

    def test_proposal_confidence_label_adequate_padding(self):
        """Proposal confidence label should have px-3 py-1.5."""
        from app import engagement_routes
        import inspect

        source = inspect.getsource(engagement_routes)
        assert "px-3 py-1.5 rounded-full border" in source, "Proposal confidence label missing adequate padding"

    def test_status_badges_adequate_padding(self):
        """Annotation and upload status badges should not use py-0.5."""
        from app import engagement_routes
        import inspect

        source = inspect.getsource(engagement_routes)
        # Status badges (annotations + uploads) should use py-1, not py-0.5
        assert "py-0.5 rounded ml-2" not in source, "Status badges still have py-0.5"


class TestNoRemainingSmallTouchTargets(unittest.TestCase):
    """Regression: no py-0.5 on interactive elements in these route files."""

    def test_cluster_review_no_interactive_py_half(self):
        """cluster_review_routes should have no py-0.5 on badges (kbd elements excluded)."""
        from app import cluster_review_routes
        import inspect

        source = inspect.getsource(cluster_review_routes)
        # Split by lines and check non-kbd lines for py-0.5
        for i, line in enumerate(source.split("\n"), 1):
            if "py-0.5" in line and "<kbd" not in line and "kbd" not in line:
                assert False, f"Line {i} in cluster_review_routes.py still has py-0.5: {line.strip()}"

    def test_engagement_no_interactive_py_half(self):
        """engagement_routes should have no py-0.5 on any element."""
        from app import engagement_routes
        import inspect

        source = inspect.getsource(engagement_routes)
        for i, line in enumerate(source.split("\n"), 1):
            if "py-0.5" in line:
                assert False, f"Line {i} in engagement_routes.py still has py-0.5: {line.strip()}"


if __name__ == "__main__":
    unittest.main()
