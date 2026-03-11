"""Tests for recalibration_hooks module.

Covers cosine similarity, canonical pair ordering, async merge/reject hooks,
and missing-embedding warning behavior.

Session: 63
"""

import asyncio
import logging
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from rhodesli_ml.calibration_lineage import (
    LABEL_TYPE_EXPLICIT_NEGATIVE,
    LABEL_TYPE_EXPLICIT_POSITIVE,
)
from rhodesli_ml.recalibration_hooks import (
    _compute_similarity,
    _insert_pair,
    on_face_merge,
    on_match_reject,
)


# ---------------------------------------------------------------------------
# 1. _compute_similarity returns correct value for known vectors
# ---------------------------------------------------------------------------

class TestComputeSimilarity:
    def test_known_vectors(self):
        """Identical unit vectors should yield similarity 1.0."""
        v = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        assert _compute_similarity(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should yield similarity 0.0."""
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        assert _compute_similarity(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors(self):
        """Opposite vectors should yield similarity -1.0."""
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([-1.0, 0.0], dtype=np.float32)
        assert _compute_similarity(a, b) == pytest.approx(-1.0, abs=1e-6)

    def test_realistic_512d(self):
        """Non-trivial 512-d vectors produce a float in [-1, 1]."""
        rng = np.random.default_rng(42)
        a = rng.standard_normal(512).astype(np.float32)
        b = rng.standard_normal(512).astype(np.float32)
        sim = _compute_similarity(a, b)
        assert -1.0 <= sim <= 1.0

    # -------------------------------------------------------------------
    # 2. _compute_similarity with zero vector returns 0.0
    # -------------------------------------------------------------------

    def test_zero_vector_a(self):
        """Zero vector for emb_a returns 0.0 (no division error)."""
        zero = np.zeros(512, dtype=np.float32)
        nonzero = np.ones(512, dtype=np.float32)
        assert _compute_similarity(zero, nonzero) == 0.0

    def test_zero_vector_b(self):
        """Zero vector for emb_b returns 0.0 (no division error)."""
        nonzero = np.ones(512, dtype=np.float32)
        zero = np.zeros(512, dtype=np.float32)
        assert _compute_similarity(nonzero, zero) == 0.0

    def test_both_zero_vectors(self):
        """Both zero vectors return 0.0."""
        zero = np.zeros(512, dtype=np.float32)
        assert _compute_similarity(zero, zero) == 0.0


# ---------------------------------------------------------------------------
# 3. on_face_merge with mock supabase inserts a match pair
# ---------------------------------------------------------------------------

class TestOnFaceMerge:
    def test_inserts_match_pair(self):
        """on_face_merge creates a match pair via supabase upsert."""
        fake_emb_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        fake_emb_b = np.array([0.9, 0.1, 0.0], dtype=np.float32)

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        with patch(
            "rhodesli_ml.recalibration_hooks._get_embedding",
            side_effect=lambda fid, **kw: fake_emb_a if fid == "face_aaa" else fake_emb_b,
        ):
            asyncio.run(on_face_merge(
                "face_aaa", "face_bbb", merged_by="admin",
                supabase_client=mock_client,
            ))

        mock_client.table.assert_called_with("calibration_pairs")
        upsert_call = mock_table.upsert.call_args
        row = upsert_call[0][0]
        assert row["is_match"] is True
        assert row["source"] == "merge_admin"
        assert row["weight"] == 1.0
        assert row["label_type"] == LABEL_TYPE_EXPLICIT_POSITIVE
        assert row["state_event_action"] == "merge"
        assert row["active"] is True
        assert -1.0 <= row["similarity_score"] <= 1.0

    def test_merge_hook_never_recalibrates_inline(self):
        """Merge hook only writes labels; it never retrains inline."""
        fake_emb_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        fake_emb_b = np.array([0.9, 0.1, 0.0], dtype=np.float32)

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        with patch(
            "rhodesli_ml.recalibration_hooks._get_embedding",
            side_effect=lambda fid, **kw: fake_emb_a if fid == "face_aaa" else fake_emb_b,
        ), patch(
            "rhodesli_ml.similarity_calibration.SimilarityCalibrator.recalibrate_if_needed"
        ) as mock_recalibrate:
            asyncio.run(on_face_merge("face_aaa", "face_bbb", supabase_client=mock_client))

        mock_recalibrate.assert_not_called()

    # -------------------------------------------------------------------
    # 5. on_face_merge with missing embeddings logs warning (not error)
    # -------------------------------------------------------------------

    def test_missing_embedding_logs_warning(self, caplog):
        """When an embedding is missing, on_face_merge logs WARNING and returns early."""
        mock_client = MagicMock()

        with patch(
            "rhodesli_ml.recalibration_hooks._get_embedding",
            return_value=None,
        ), caplog.at_level(logging.WARNING, logger="rhodesli_ml.recalibration_hooks"):
            asyncio.run(on_face_merge(
                "face_xxx", "face_yyy", supabase_client=mock_client,
            ))

        # Should log a warning, not an error
        assert any("missing embedding" in r.message for r in caplog.records)
        assert all(r.levelno <= logging.WARNING for r in caplog.records)

        # Should NOT attempt to insert
        mock_client.table.assert_not_called()

    def test_no_supabase_client_skips_insert(self):
        """When supabase_client is None, no insert is attempted."""
        fake_emb = np.ones(3, dtype=np.float32)

        with patch(
            "rhodesli_ml.recalibration_hooks._get_embedding",
            return_value=fake_emb,
        ):
            # Should not raise even without a client
            asyncio.run(on_face_merge("face_a", "face_b", supabase_client=None))


# ---------------------------------------------------------------------------
# 4. on_match_reject with mock supabase inserts non-match with weight 1.5
# ---------------------------------------------------------------------------

class TestOnMatchReject:
    def test_inserts_non_match_with_weight(self):
        """on_match_reject creates a non-match pair with weight=1.5."""
        fake_emb_a = np.array([1.0, 0.0], dtype=np.float32)
        fake_emb_b = np.array([0.0, 1.0], dtype=np.float32)

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        with patch(
            "rhodesli_ml.recalibration_hooks._get_embedding",
            side_effect=lambda fid, **kw: fake_emb_a if fid == "face_p" else fake_emb_b,
        ):
            asyncio.run(on_match_reject(
                "face_p", "face_q", rejected_by="admin",
                supabase_client=mock_client,
            ))

        mock_client.table.assert_called_with("calibration_pairs")
        upsert_call = mock_table.upsert.call_args
        row = upsert_call[0][0]
        assert row["is_match"] is False
        assert row["weight"] == 1.5
        assert row["source"] == "reject_admin"
        assert row["label_type"] == LABEL_TYPE_EXPLICIT_NEGATIVE
        assert row["state_event_action"] == "reject"

    def test_missing_embedding_logs_warning(self, caplog):
        """on_match_reject also logs WARNING on missing embedding."""
        mock_client = MagicMock()

        with patch(
            "rhodesli_ml.recalibration_hooks._get_embedding",
            return_value=None,
        ), caplog.at_level(logging.WARNING, logger="rhodesli_ml.recalibration_hooks"):
            asyncio.run(on_match_reject(
                "face_x", "face_y", supabase_client=mock_client,
            ))

        assert any("missing embedding" in r.message for r in caplog.records)
        mock_client.table.assert_not_called()


# ---------------------------------------------------------------------------
# 6. _insert_pair canonical ordering (a < b always)
# ---------------------------------------------------------------------------

class TestInsertPairCanonicalOrdering:
    def test_already_ordered(self):
        """When face_id_a < face_id_b, order is preserved."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        _insert_pair(
            mock_client,
            "aaa",
            "zzz",
            0.85,
            True,
            "test",
            label_type=LABEL_TYPE_EXPLICIT_POSITIVE,
            state_event_action="merge",
            actor_id="admin",
            source_surface="test",
        )

        row = mock_table.upsert.call_args[0][0]
        assert row["face_id_a"] == "aaa"
        assert row["face_id_b"] == "zzz"

    def test_reversed_order_is_corrected(self):
        """When face_id_a > face_id_b, they are swapped to canonical order."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        _insert_pair(
            mock_client,
            "zzz",
            "aaa",
            0.75,
            False,
            "test",
            label_type=LABEL_TYPE_EXPLICIT_NEGATIVE,
            state_event_action="reject",
            actor_id="admin",
            source_surface="test",
        )

        row = mock_table.upsert.call_args[0][0]
        assert row["face_id_a"] == "aaa"
        assert row["face_id_b"] == "zzz"

    def test_same_ids_no_crash(self):
        """Degenerate case: identical face_ids still produces a valid row."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        _insert_pair(
            mock_client,
            "same",
            "same",
            1.0,
            True,
            "test",
            label_type=LABEL_TYPE_EXPLICIT_POSITIVE,
            state_event_action="merge",
            actor_id="admin",
            source_surface="test",
        )

        row = mock_table.upsert.call_args[0][0]
        assert row["face_id_a"] == "same"
        assert row["face_id_b"] == "same"

    def test_upsert_conflict_key(self):
        """Upsert uses the correct conflict columns."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        _insert_pair(
            mock_client,
            "a",
            "b",
            0.9,
            True,
            "test",
            label_type=LABEL_TYPE_EXPLICIT_POSITIVE,
            state_event_action="merge",
            actor_id="admin",
            source_surface="test",
            weight=2.0,
        )

        upsert_kwargs = mock_table.upsert.call_args[1]
        assert upsert_kwargs["on_conflict"] == "face_id_a,face_id_b"

        row = mock_table.upsert.call_args[0][0]
        assert row["weight"] == 2.0
        assert row["similarity_score"] == 0.9
        assert row["pair_key"] == "a::b"

    def test_insert_exception_logs_warning(self, caplog):
        """If supabase upsert throws, _insert_pair logs WARNING (not crash)."""
        mock_client = MagicMock()
        mock_client.table.side_effect = Exception("connection refused")

        with caplog.at_level(logging.WARNING, logger="rhodesli_ml.recalibration_hooks"):
            _insert_pair(
                mock_client,
                "a",
                "b",
                0.5,
                False,
                "test",
                label_type=LABEL_TYPE_EXPLICIT_NEGATIVE,
                state_event_action="reject",
                actor_id="admin",
                source_surface="test",
            )

        assert any("Failed to insert calibration pair" in r.message for r in caplog.records)
