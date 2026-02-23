"""Tests for recalibration hooks wiring into app endpoints (AD-150).

Verifies that merge/reject/confirm endpoints fire recalibration hooks.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestFireRecalibrationHook:
    """Test _fire_recalibration_hook dispatches correctly."""

    def test_fires_on_merge(self):
        """Merge action calls on_face_merge."""
        from app.main import _fire_recalibration_hook

        mock_sb = MagicMock()
        mock_merge = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb), \
             patch("rhodesli_ml.recalibration_hooks.on_face_merge", mock_merge):
            _fire_recalibration_hook("merge", "id_a", "id_b")

        mock_merge.assert_called_once()

    def test_fires_on_reject(self):
        """Reject action calls on_match_reject."""
        from app.main import _fire_recalibration_hook

        mock_sb = MagicMock()
        mock_reject = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb), \
             patch("rhodesli_ml.recalibration_hooks.on_match_reject", mock_reject):
            _fire_recalibration_hook("reject", "id_a", "id_b")

        mock_reject.assert_called_once()

    def test_fires_on_confirm(self):
        """Confirm action calls on_identity_confirm."""
        from app.main import _fire_recalibration_hook

        mock_sb = MagicMock()
        mock_confirm = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb), \
             patch("rhodesli_ml.recalibration_hooks.on_identity_confirm", mock_confirm):
            _fire_recalibration_hook("confirm", "id_x", anchor_face_ids=["f1", "f2"])

        mock_confirm.assert_called_once()

    def test_no_supabase_skips_gracefully(self):
        """When Supabase unavailable, hook silently returns."""
        from app.main import _fire_recalibration_hook

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            # Should not raise
            _fire_recalibration_hook("merge", "id_a", "id_b")

    def test_exception_does_not_propagate(self):
        """Any exception in hook is caught, never propagated."""
        from app.main import _fire_recalibration_hook

        mock_sb = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb), \
             patch("rhodesli_ml.recalibration_hooks.on_face_merge", side_effect=RuntimeError("boom")):
            # Should not raise
            _fire_recalibration_hook("merge", "id_a", "id_b")


class TestDistanceToCosineConversion:
    """Test Euclidean → cosine similarity conversion formula."""

    def test_identical_vectors(self):
        """Distance 0.0 → cosine similarity 1.0."""
        sim = max(0.0, 1.0 - (0.0 ** 2) / 2.0)
        assert sim == 1.0

    def test_moderate_distance(self):
        """Distance 1.0 → cosine similarity 0.5."""
        sim = max(0.0, 1.0 - (1.0 ** 2) / 2.0)
        assert sim == 0.5

    def test_orthogonal_vectors(self):
        """Distance sqrt(2) ≈ 1.414 → cosine similarity ≈ 0.0."""
        import math
        d = math.sqrt(2)
        sim = max(0.0, 1.0 - (d ** 2) / 2.0)
        assert abs(sim) < 0.01

    def test_opposite_vectors_clamped(self):
        """Distance 2.0 → cosine similarity clamped to 0.0 (not -1)."""
        sim = max(0.0, 1.0 - (2.0 ** 2) / 2.0)
        assert sim == 0.0

    def test_very_high_threshold_distance(self):
        """Distance 0.8 (VERY_HIGH threshold) → cosine 0.68."""
        sim = max(0.0, 1.0 - (0.8 ** 2) / 2.0)
        assert abs(sim - 0.68) < 0.01
