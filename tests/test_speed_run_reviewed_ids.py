"""Tests for FB-161: Speed-run reviewed_ids wiring."""

import re
from pathlib import Path


def _find_route_handler(source, route_path):
    """Find the @rt decorator + handler for a route, not button references."""
    # Look for @rt("route_path") pattern
    pattern = rf'@rt\("{re.escape(route_path)}"\)'
    match = re.search(pattern, source)
    if not match:
        return ""
    return source[match.start() : match.start() + 800]


class TestReviewedIdsWiring:
    """Verify reviewed_ids is wired through all speed-run endpoints."""

    def test_skip_accepts_reviewed_ids(self):
        source = Path("app/cluster_review_routes.py").read_text()
        handler = _find_route_handler(source, "/api/cluster-review/skip")
        assert "reviewed_ids" in handler

    def test_confirm_all_accepts_reviewed_ids(self):
        source = Path("app/cluster_review_routes.py").read_text()
        handler = _find_route_handler(source, "/api/cluster-review/confirm-all")
        assert "reviewed_ids" in handler

    def test_reject_all_accepts_reviewed_ids(self):
        source = Path("app/cluster_review_routes.py").read_text()
        handler = _find_route_handler(source, "/api/cluster-review/reject-all")
        assert "reviewed_ids" in handler

    def test_dismiss_accepts_reviewed_ids(self):
        source = Path("app/cluster_review_routes.py").read_text()
        handler = _find_route_handler(source, "/api/cluster-review/dismiss")
        assert "reviewed_ids" in handler

    def test_next_card_accepts_reviewed_ids(self):
        source = Path("app/cluster_review_routes.py").read_text()
        handler = _find_route_handler(source, "/admin/cluster-review/next")
        assert "reviewed_ids" in handler

    def test_js_reviewed_ids_injection_exists(self):
        """JS must intercept htmx:configRequest to inject reviewed_ids."""
        source = Path("app/cluster_review_routes.py").read_text()
        assert "window._reviewedIds" in source
        assert "htmx:configRequest" in source

    def test_speed_run_next_card_filters_reviewed(self):
        """_speed_run_next_card must filter out reviewed_ids."""
        source = Path("app/cluster_review_routes.py").read_text()
        idx = source.index("def _speed_run_next_card")
        handler = source[idx : idx + 500]
        assert "reviewed_ids" in handler
        assert "reviewed_set" in handler
