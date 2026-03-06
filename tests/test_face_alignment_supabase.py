"""Tests for face alignment Supabase migration (AD-152).

Tests that alignment data can be saved/loaded from Supabase,
with JSON fallback when Supabase is unavailable.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_face_alignment_caches():
    """Keep module-level alignment caches isolated between tests."""
    import app.face_alignment as face_alignment

    face_alignment._ALIGNMENT_CACHE.clear()
    face_alignment._ALIGNMENTS_BULK_CACHE = None
    face_alignment._ALIGNMENTS_BULK_CACHE_LOADED_AT = 0.0
    face_alignment._ALIGNMENTS_BULK_CACHE_FAILED_AT = 0.0
    yield
    face_alignment._ALIGNMENT_CACHE.clear()
    face_alignment._ALIGNMENTS_BULK_CACHE = None
    face_alignment._ALIGNMENTS_BULK_CACHE_LOADED_AT = 0.0
    face_alignment._ALIGNMENTS_BULK_CACHE_FAILED_AT = 0.0


class TestFaceAlignmentSupabaseSave:
    """Tests for save_face_alignment_to_supabase."""

    def test_saves_to_supabase_when_available(self):
        """Successful save returns True."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import save_face_alignment_to_supabase
            result = save_face_alignment_to_supabase(
                photo_id="test123",
                alignment_data={"faces_detected": 3},
                model_used="gemini-3.1-pro-preview",
                cost=0.028,
                tokens=1500,
            )

        assert result is True
        mock_sb.table.assert_called_with("face_gemini_alignments")

    def test_returns_false_when_supabase_unavailable(self):
        """Returns False when Supabase client is None."""
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            from app.supabase_data import save_face_alignment_to_supabase
            result = save_face_alignment_to_supabase(
                photo_id="test123",
                alignment_data={"faces_detected": 3},
            )

        assert result is False

    def test_returns_false_on_supabase_error(self):
        """Returns False on Supabase network exception (degraded mode)."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.side_effect = ConnectionError("timeout")

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import save_face_alignment_to_supabase
            result = save_face_alignment_to_supabase(
                photo_id="test123",
                alignment_data={"faces_detected": 3},
            )

        assert result is False

    def test_omits_none_values(self):
        """None values are stripped from the row before upsert."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import save_face_alignment_to_supabase
            save_face_alignment_to_supabase(
                photo_id="test123",
                alignment_data={"x": 1},
                model_used=None,
                cost=None,
                tokens=None,
            )

        call_args = mock_sb.table.return_value.upsert.call_args[0][0]
        assert "model_used" not in call_args
        assert "cost" not in call_args
        assert "tokens_used" not in call_args


class TestFaceAlignmentSupabaseLoad:
    """Tests for load_face_alignment_from_supabase."""

    def test_loads_single_alignment(self):
        """Returns alignment_data dict for matching photo_id."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"alignment_data": {"faces_detected": 3}, "model_used": "pro"}]
        )

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import load_face_alignment_from_supabase
            result = load_face_alignment_from_supabase("test123")

        assert result == {"faces_detected": 3}

    def test_returns_none_when_not_found(self):
        """Returns None for non-existent photo_id."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import load_face_alignment_from_supabase
            result = load_face_alignment_from_supabase("nonexistent")

        assert result is None

    def test_returns_none_when_supabase_unavailable(self):
        """Returns None when Supabase client is None."""
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            from app.supabase_data import load_face_alignment_from_supabase
            result = load_face_alignment_from_supabase("test123")

        assert result is None


class TestFaceAlignmentBulkLoad:
    """Tests for load_all_face_alignments_from_supabase."""

    def test_loads_all_alignments(self):
        """Returns dict mapping photo_id to alignment_data."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[
                {"photo_id": "p1", "alignment_data": {"faces": 2}},
                {"photo_id": "p2", "alignment_data": {"faces": 5}},
            ]
        )

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import load_all_face_alignments_from_supabase
            result = load_all_face_alignments_from_supabase()

        assert result == {"p1": {"faces": 2}, "p2": {"faces": 5}}

    def test_returns_none_when_unavailable(self):
        """Returns None when Supabase client is None."""
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            from app.supabase_data import load_all_face_alignments_from_supabase
            result = load_all_face_alignments_from_supabase()

        assert result is None

    def test_returns_empty_dict_when_no_data(self):
        """Returns empty dict when table has no rows."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import load_all_face_alignments_from_supabase
            result = load_all_face_alignments_from_supabase()

        assert result == {}


class TestAlignmentSaveFunction:
    """Tests for the unified save_alignment function in face_alignment.py."""

    def test_save_alignment_tries_supabase_first(self, tmp_path):
        """save_alignment writes to Supabase first, then JSON."""
        from app.face_alignment import AlignmentResult, save_alignment

        result = AlignmentResult(
            photo_id="test_photo",
            faces_detected=2,
            faces_described=2,
            model_used="gemini-3.1-pro-preview",
            cost=0.028,
            input_tokens=1000,
            output_tokens=500,
        )

        with patch("app.supabase_data.save_face_alignment_to_supabase", return_value=True) as mock_sb:
            saved_to_sb = save_alignment(result, output_dir=tmp_path)

        assert saved_to_sb is True
        mock_sb.assert_called_once()
        # JSON should also be written as cache
        json_file = tmp_path / "face_alignments.json"
        assert json_file.exists()

    def test_save_alignment_falls_back_to_json(self, tmp_path):
        """When Supabase fails, still writes JSON."""
        from app.face_alignment import AlignmentResult, save_alignment

        result = AlignmentResult(
            photo_id="test_photo",
            faces_detected=1,
        )

        with patch("app.supabase_data.save_face_alignment_to_supabase", return_value=False):
            saved_to_sb = save_alignment(result, output_dir=tmp_path)

        assert saved_to_sb is False
        json_file = tmp_path / "face_alignments.json"
        assert json_file.exists()
        with open(json_file) as f:
            data = json.load(f)
        assert "test_photo" in data


class TestLoadAlignmentsFunction:
    """Tests for the unified load_alignments function."""

    def test_caches_supabase_bulk_load_within_ttl(self, tmp_path):
        """Repeated page loads should not re-query Supabase within the TTL."""
        import app.face_alignment as face_alignment

        face_alignment._ALIGNMENTS_BULK_CACHE = None
        face_alignment._ALIGNMENTS_BULK_CACHE_LOADED_AT = 0.0
        face_alignment._ALIGNMENTS_BULK_CACHE_FAILED_AT = 0.0

        supabase_data = {"p1": {"faces": 3}}
        with patch("app.supabase_data.load_all_face_alignments_from_supabase", return_value=supabase_data) as mock_load:
            result1 = face_alignment.load_alignments(tmp_path)
            result2 = face_alignment.load_alignments(tmp_path)

        assert result1 == supabase_data
        assert result2 == supabase_data
        assert mock_load.call_count == 1

    def test_prefers_supabase_data(self, tmp_path):
        """Returns Supabase data when available."""
        from app.face_alignment import load_alignments

        supabase_data = {"p1": {"faces": 3}}
        with patch("app.supabase_data.load_all_face_alignments_from_supabase", return_value=supabase_data):
            result = load_alignments(tmp_path)

        assert result == supabase_data

    def test_falls_back_to_json(self, tmp_path):
        """Returns JSON data when Supabase returns None."""
        from app.face_alignment import load_alignments

        # Write JSON file
        json_file = tmp_path / "face_alignments.json"
        json_file.write_text('{"p2": {"faces": 5}}')

        with patch("app.supabase_data.load_all_face_alignments_from_supabase", return_value=None):
            result = load_alignments(tmp_path)

        assert result == {"p2": {"faces": 5}}

    def test_falls_back_when_supabase_empty(self, tmp_path):
        """Returns JSON when Supabase returns empty dict."""
        from app.face_alignment import load_alignments

        json_file = tmp_path / "face_alignments.json"
        json_file.write_text('{"p3": {"faces": 1}}')

        with patch("app.supabase_data.load_all_face_alignments_from_supabase", return_value={}):
            result = load_alignments(tmp_path)

        assert result == {"p3": {"faces": 1}}

    def test_failure_backoff_avoids_repeat_supabase_queries(self, tmp_path):
        """After a failed bulk load, reuse fallback data during the backoff window."""
        import app.face_alignment as face_alignment

        face_alignment._ALIGNMENTS_BULK_CACHE = None
        face_alignment._ALIGNMENTS_BULK_CACHE_LOADED_AT = 0.0
        face_alignment._ALIGNMENTS_BULK_CACHE_FAILED_AT = 0.0

        json_file = tmp_path / "face_alignments.json"
        json_file.write_text('{"p4": {"faces": 2}}')

        with patch("app.supabase_data.load_all_face_alignments_from_supabase", return_value=None) as mock_load:
            result1 = face_alignment.load_alignments(tmp_path)
            result2 = face_alignment.load_alignments(tmp_path)

        assert result1 == {"p4": {"faces": 2}}
        assert result2 == {"p4": {"faces": 2}}
        assert mock_load.call_count == 1


class TestAlignmentDataSchema:
    """Tests that alignment data schema is valid for Supabase storage."""

    def test_alignment_result_serializes_to_valid_json(self):
        """AlignmentResult.to_dict() produces JSON-serializable output."""
        from app.face_alignment import AlignedFaceDescription, AlignmentResult

        result = AlignmentResult(
            photo_id="test",
            faces_detected=1,
            faces_described=1,
            aligned_faces=[
                AlignedFaceDescription(
                    face_id="face0",
                    bbox=[10, 20, 100, 200],
                    face_index=0,
                    gemini_description="Test face",
                    estimated_age=30,
                )
            ],
            model_used="gemini-3.1-pro-preview",
        )

        d = result.to_dict()
        # Should be JSON-serializable
        serialized = json.dumps(d)
        assert '"photo_id": "test"' in serialized
        assert '"face_id": "face0"' in serialized
