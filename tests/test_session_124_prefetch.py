"""Tests for speed-run prefetch cascade fix (Session 124).

The initial speed-run card should have a prefetch div (hx-trigger="load")
to prefetch the next card. But the prefetched card itself should NOT have
a nested prefetch div, preventing cascading prefetch of ALL remaining cards.
"""

from contextlib import ExitStack
from unittest.mock import patch


def _make_identity(num_faces=3):
    """Create a minimal identity dict for testing."""
    face_ids = [f"face_{i}" for i in range(num_faces)]
    return {
        "identity_id": "test-id",
        "name": "Unidentified Person 42",
        "state": "PROPOSED",
        "anchor_ids": [],
        "candidate_ids": face_ids,
        "negative_ids": [],
    }


def _render_card(prefetched=False):
    """Render a speed-run cluster card with standard mocks."""
    from app.cluster_review_routes import _speed_run_cluster_card

    identity = _make_identity(num_faces=2)
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "app.cluster_review_routes._get_crop_url_for_face",
                return_value="/static/crops/test.jpg",
            )
        )
        stack.enter_context(
            patch(
                "app.cluster_review_routes._get_photo_url_for_face",
                return_value="/photo/test-photo",
            )
        )
        card = _speed_run_cluster_card("test-id", identity, 0, 5, "rhodes", prefetched=prefetched)
        return repr(card)


class TestPrefetchCascadePrevention:
    """Verify that prefetch does not cascade beyond one level."""

    def test_initial_card_has_prefetch_div(self):
        """The initial card (prefetched=False) should contain a prefetch div."""
        html = _render_card(prefetched=False)
        assert 'id="speed-run-prefetch"' in html
        assert 'hx-trigger="load"' in html
        assert "/admin/cluster-review/next" in html

    def test_prefetched_card_has_no_prefetch_div(self):
        """A prefetched card (prefetched=True) should NOT contain a nested prefetch div."""
        html = _render_card(prefetched=True)
        assert 'id="speed-run-prefetch"' not in html
        # The card itself should still have the main content
        assert 'id="speed-run-card"' in html
        assert "Confirm All" in html

    def test_prefetched_card_still_has_action_buttons(self):
        """Prefetched cards should retain all action buttons."""
        html = _render_card(prefetched=True)
        assert "Confirm All" in html
        assert "Reject All" in html
        assert "Skip" in html
        assert "Dismiss" in html

    def test_next_endpoint_passes_prefetched_true(self):
        """The /admin/cluster-review/next route passes prefetched=True to prevent cascade."""
        import inspect

        # Read the source of cluster_review_routes to verify the route handler
        # passes prefetched=True when calling _speed_run_next_card
        import app.cluster_review_routes as mod

        source = inspect.getsource(mod)
        # The /admin/cluster-review/next handler should call with prefetched=True
        assert "prefetched=True" in source, (
            "The /admin/cluster-review/next handler must pass prefetched=True "
            "to _speed_run_next_card to prevent cascading prefetch"
        )
