"""Tests for Session 125 Phase 4: cluster_review_routes improvements."""

from pathlib import Path
from unittest.mock import patch, MagicMock


class TestSurgicalInvalidation:
    """PERF #10: Confirm/reject use save_registry with changed_ids."""

    def test_confirm_uses_save_registry(self):
        """Confirm endpoint calls save_registry, not registry.save + invalidate."""
        source = Path("app/cluster_review_routes.py").read_text()

        # Find the confirm endpoint
        idx = source.index('@rt("/api/cluster-review/confirm")')
        end_idx = source.index('@rt("', idx + 10)
        confirm_func = source[idx:end_idx]

        assert "save_registry" in confirm_func, "Confirm must use save_registry"
        assert "changed_ids" in confirm_func, "Confirm must pass changed_ids"
        assert "_invalidate_all_caches" not in confirm_func, (
            "Confirm should NOT call _invalidate_all_caches (surgical only)"
        )

    def test_reject_uses_save_registry(self):
        """Reject endpoint calls save_registry, not registry.save + invalidate."""
        source = Path("app/cluster_review_routes.py").read_text()

        idx = source.index('@rt("/api/cluster-review/reject")')
        end_idx = source.index('@rt("', idx + 10)
        reject_func = source[idx:end_idx]

        assert "save_registry" in reject_func, "Reject must use save_registry"
        assert "changed_ids" in reject_func, "Reject must pass changed_ids"
        assert "_invalidate_all_caches" not in reject_func, (
            "Reject should NOT call _invalidate_all_caches (surgical only)"
        )


class TestReviewedIdsTracking:
    """FB-161: Speed-run skip tracks reviewed IDs to prevent reappearance."""

    def test_skip_passes_reviewed_ids(self):
        """Skip endpoint accepts and forwards reviewed_ids parameter."""
        source = Path("app/cluster_review_routes.py").read_text()

        idx = source.index('@rt("/api/cluster-review/skip")')
        end_idx = source.index('@rt("', idx + 10)
        skip_func = source[idx:end_idx]

        assert "reviewed_ids" in skip_func, "Skip must accept reviewed_ids parameter"

    def test_next_card_filters_reviewed(self):
        """_speed_run_next_card filters out reviewed identity IDs."""
        from app.cluster_review_routes import _speed_run_next_card

        # The function signature should accept reviewed_ids
        import inspect

        sig = inspect.signature(_speed_run_next_card)
        assert "reviewed_ids" in sig.parameters, "_speed_run_next_card must accept reviewed_ids parameter"


class TestSuggestionNameTruncation:
    """FB-151: Suggestion names show full name on hover."""

    def test_suggestion_name_has_title_attribute(self):
        """Suggestion name Span has title attribute for full name on hover."""
        source = Path("app/cluster_review_routes.py").read_text()

        # Find suggestion name rendering
        idx = source.index("sug_name_row")
        name_section = source[idx : idx + 500]
        assert 'title=sug["name"]' in name_section, "Suggestion name must have title attribute for full name"
        assert "truncate" in name_section, "Suggestion name must use truncate class"
